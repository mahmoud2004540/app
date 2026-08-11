"""
محرّك المخاطر المستقل (Risk Engine) — الترقية الاحترافية (Master Build).

Independent risk manager. Deliberately decoupled from the AI/strategy: it takes
plain numbers and enforces hard rules the AI can NEVER override:

  - risk per trade           = 0.5% of equity (default)
  - maximum daily loss       = 1.5% → stop opening new trades for the day
  - max consecutive losses   = 3   → stop the bot until a new trading day
  - minimum reward:risk      = 1:2 → reject anything worse
  - stop-loss may never be moved to INCREASE the original risk
  - position size accounts for fees + slippage and never exceeds the risk cap

Nothing here imports the AI or the strategy — that independence is the point.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class RiskConfig:
    risk_per_trade: float = 0.005        # 0.5%
    max_daily_loss_pct: float = 0.015    # 1.5%
    max_consecutive_losses: int = 3
    min_rr: float = 2.0
    max_open_positions: int = 5
    fee_rate: float = 0.001              # لكل جهة
    slippage_rate: float = 0.0005


@dataclass
class DailyState:
    """حالة اليوم — تُبنى من سجل الصفقات + رأس المال الحالي."""
    starting_equity: float
    current_equity: float
    trades_today: int = 0
    losses_today: int = 0
    consecutive_losses: int = 0
    open_positions: int = 0

    @property
    def daily_pnl(self) -> float:
        return self.current_equity - self.starting_equity

    @property
    def daily_loss_pct(self) -> float:
        """نسبة الخسارة اليومية (موجبة عند الخسارة)."""
        if self.starting_equity <= 0:
            return 0.0
        return max(0.0, -self.daily_pnl) / self.starting_equity


@dataclass
class RiskDecision:
    approved: bool
    reason: str


class RiskEngine:
    """محرّك مخاطر صارم ومستقل. لا يعرف شيئًا عن الـ AI."""

    def __init__(self, config: Optional[RiskConfig] = None):
        self.cfg = config or RiskConfig()

    # -------------------- بوّابات السماح بالتداول -------------------- #
    def can_open_new_trade(self, daily: DailyState) -> RiskDecision:
        """هل يُسمح بفتح صفقة جديدة الآن؟ (فحوص الأمان اليومية)."""
        if daily.daily_loss_pct >= self.cfg.max_daily_loss_pct:
            return RiskDecision(
                False,
                f"🛑 تجاوز حدّ الخسارة اليومية "
                f"({daily.daily_loss_pct*100:.2f}% ≥ {self.cfg.max_daily_loss_pct*100:.1f}%)"
                " — إيقاف فتح صفقات جديدة اليوم.",
            )
        if daily.consecutive_losses >= self.cfg.max_consecutive_losses:
            return RiskDecision(
                False,
                f"🛑 {daily.consecutive_losses} خسائر متتالية "
                f"(≥ {self.cfg.max_consecutive_losses}) — إيقاف البوت حتى يوم تداول جديد.",
            )
        if daily.open_positions >= self.cfg.max_open_positions:
            return RiskDecision(
                False,
                f"🛑 بلغت الحدّ الأقصى للصفقات المفتوحة ({self.cfg.max_open_positions}).",
            )
        return RiskDecision(True, "✅ محرّك المخاطر يسمح بفتح صفقة.")

    # -------------------- نسبة العائد/المخاطرة -------------------- #
    def reward_risk(self, entry: float, stop: float, target: float) -> float:
        risk = abs(entry - stop)
        reward = abs(target - entry)
        return (reward / risk) if risk > 0 else 0.0

    def check_reward_risk(self, entry: float, stop: float, target: float) -> RiskDecision:
        rr = self.reward_risk(entry, stop, target)
        if rr < self.cfg.min_rr:
            return RiskDecision(
                False, f"🛑 نسبة العائد/المخاطرة {rr:.2f} أقل من {self.cfg.min_rr:.1f} — رُفضت.",
            )
        return RiskDecision(True, f"✅ العائد/المخاطرة 1:{rr:.1f}")

    # -------------------- حجم المركز -------------------- #
    def position_size(
        self, equity: float, entry: float, stop: float, direction: str = "BUY",
    ) -> Tuple[float, float]:
        """
        احسب حجم المركز بحيث لا تتجاوز الخسارة عند الوقف نسبة المخاطرة، مع مراعاة
        الرسوم والانزلاق. يُرجع (الكمية, المبلغ المخاطَر به).

        Position size so that the loss at stop (including fees on both sides +
        expected slippage) never exceeds risk_per_trade × equity.
        """
        if equity <= 0 or entry <= 0:
            return 0.0, 0.0
        risk_amount = equity * self.cfg.risk_per_trade
        price_risk = abs(entry - stop)
        # تكلفة إضافية لكل وحدة: رسوم دخول+خروج + انزلاق
        cost_per_unit = entry * (2 * self.cfg.fee_rate + self.cfg.slippage_rate)
        risk_per_unit = price_risk + cost_per_unit
        if risk_per_unit <= 0:
            return 0.0, 0.0
        qty = risk_amount / risk_per_unit
        return round(qty, 8), round(risk_amount, 2)

    # -------------------- حماية وقف الخسارة -------------------- #
    def validate_stop_move(
        self, direction: str, entry: float, old_stop: float, new_stop: float,
    ) -> RiskDecision:
        """
        امنع تحريك الوقف إلى مكان يزيد المخاطرة الأصلية (ممنوع تمامًا).

        Only allow moving the stop in the risk-reducing direction (toward/beyond
        entry). Widening the stop is forbidden.
        """
        old_risk = abs(entry - old_stop)
        new_risk = abs(entry - new_stop)
        if new_risk > old_risk + 1e-12:
            return RiskDecision(
                False, "🛑 ممنوع تحريك وقف الخسارة لمكان يزيد المخاطرة الأصلية.",
            )
        # في صفقة شراء لا يجوز أن ينزل الوقف؛ وفي بيع لا يجوز أن يرتفع
        if direction == "BUY" and new_stop < old_stop - 1e-12:
            return RiskDecision(False, "🛑 في الشراء: لا يجوز خفض وقف الخسارة.")
        if direction == "SELL" and new_stop > old_stop + 1e-12:
            return RiskDecision(False, "🛑 في البيع: لا يجوز رفع وقف الخسارة.")
        return RiskDecision(True, "✅ تحريك الوقف مسموح (يقلّل المخاطرة).")


def daily_state_from_journal(equity: float, starting_equity: float, journal_summary_today: dict,
                             open_positions: int = 0) -> DailyState:
    """
    ابنِ حالة اليوم من ملخّص سجل الصفقات لليوم الحالي.

    journal_summary_today: {"trades": int, "losses": int, "consecutive_losses": int}
    """
    return DailyState(
        starting_equity=starting_equity,
        current_equity=equity,
        trades_today=int(journal_summary_today.get("trades", 0)),
        losses_today=int(journal_summary_today.get("losses", 0)),
        consecutive_losses=int(journal_summary_today.get("consecutive_losses", 0)),
        open_positions=open_positions,
    )

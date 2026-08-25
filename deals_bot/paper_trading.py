"""
محرّك التداول الورقي (Paper Trading Engine) — الترقية الاحترافية (Master Build).

Simulates real execution WITHOUT real money: applies fees + slippage on entry and
exit, tracks an equity account and open positions, and realizes P/L when a
position closes (stop or target hit). This is the ONLY execution path — there is
no live-money path here; live trading stays disabled by design.

State persists to a JSON file so it survives the ephemeral CI container (the repo
is the durable store). Pure logic is offline-testable via an injected price.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import List, Optional

DEFAULT_STATE = os.path.join("journal", "paper_account.json")


@dataclass
class PaperPosition:
    symbol: str
    market: str
    direction: str            # BUY | SELL
    entry: float
    stop: float
    target: float
    qty: float
    opened_ts: float
    fees_paid: float = 0.0
    ai_score: float = 0.0
    atr0: float = 0.0            # ATR عند الدخول (للوقف المتحرّك)
    risk0: float = 0.0           # مخاطرة الدخول الأصلية (entry-stop) للتفعيل
    peak: float = 0.0            # أعلى سعر لصالح الصفقة (للوقف المتحرّك)


@dataclass
class ClosedTrade:
    symbol: str
    direction: str
    entry: float
    exit: float
    qty: float
    pnl: float
    fees_paid: float
    result_r: float
    reason: str               # "target" | "stop" | "manual"
    opened_ts: float
    closed_ts: float


@dataclass
class PaperAccount:
    equity: float
    starting_equity: float
    positions: List[PaperPosition] = field(default_factory=list)
    closed: List[ClosedTrade] = field(default_factory=list)
    day: int = 0                      # رقم اليوم (ts // 86400) لإعادة ضبط الحدّ اليومي
    day_start_equity: float = 0.0     # رأس المال عند بداية اليوم


def roll_day(acc: PaperAccount, now_ts: float) -> bool:
    """أعِد ضبط أساس اليوم عند تغيّر التاريخ. يُرجع True إذا بدأ يوم جديد."""
    today = int(now_ts // 86400)
    if acc.day != today:
        acc.day = today
        acc.day_start_equity = acc.equity
        return True
    if acc.day_start_equity <= 0:
        acc.day_start_equity = acc.equity
    return False


def trailing_consecutive_losses(acc: PaperAccount) -> int:
    """عدد الخسائر المتتالية في ذيل الصفقات المغلقة."""
    n = 0
    for t in reversed(acc.closed):
        if t.pnl < 0:
            n += 1
        else:
            break
    return n


# --------------------------------------------------------------------------- #
# تخزين
# --------------------------------------------------------------------------- #
def load_account(equity: float = 1000.0, path: str = DEFAULT_STATE) -> PaperAccount:
    if not os.path.exists(path):
        return PaperAccount(equity=equity, starting_equity=equity)
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return PaperAccount(
        equity=raw["equity"],
        starting_equity=raw.get("starting_equity", raw["equity"]),
        positions=[PaperPosition(**p) for p in raw.get("positions", [])],
        closed=[ClosedTrade(**c) for c in raw.get("closed", [])],
        day=raw.get("day", 0),
        day_start_equity=raw.get("day_start_equity", raw["equity"]),
    )


def save_account(acc: PaperAccount, path: str = DEFAULT_STATE) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "equity": acc.equity,
                "starting_equity": acc.starting_equity,
                "day": acc.day,
                "day_start_equity": acc.day_start_equity,
                "positions": [asdict(p) for p in acc.positions],
                "closed": [asdict(c) for c in acc.closed],
            },
            f, ensure_ascii=False, indent=2,
        )


# --------------------------------------------------------------------------- #
# التنفيذ المُحاكى
# --------------------------------------------------------------------------- #
def _apply_slippage(price: float, direction: str, slippage_rate: float, entering: bool) -> float:
    """الانزلاق ضدّك دائمًا: شراء أغلى قليلًا، بيع أرخص قليلًا."""
    adverse = slippage_rate if (direction == "BUY") == entering else -slippage_rate
    return price * (1 + adverse)


def open_position(acc: PaperAccount, symbol: str, market: str, direction: str,
                  entry: float, stop: float, target: float, qty: float,
                  opened_ts: float, fee_rate: float = 0.001,
                  slippage_rate: float = 0.0005, ai_score: float = 0.0,
                  atr0: float = 0.0) -> PaperPosition:
    """افتح صفقة ورقية: طبّق الانزلاق على الدخول واخصم رسوم الدخول."""
    fill = _apply_slippage(entry, direction, slippage_rate, entering=True)
    entry_fee = fill * qty * fee_rate
    acc.equity -= entry_fee
    pos = PaperPosition(
        symbol=symbol, market=market, direction=direction, entry=fill,
        stop=stop, target=target, qty=qty, opened_ts=opened_ts,
        fees_paid=entry_fee, ai_score=ai_score,
        atr0=atr0, risk0=abs(fill - stop), peak=fill,
    )
    acc.positions.append(pos)
    return pos


def apply_trailing(pos: PaperPosition, high: float, low: float,
                   activate_r: float, trail_atr: float) -> bool:
    """
    حدّث الوقف المتحرّك: بعد ربح +activate_r نمشّي الوقف خلف القمة بـtrail_atr×ATR.

    Returns True if the stop was moved. Long only (the live bot is spot/long).
    The stop only ever tightens (never loosens), so it locks in trend gains.
    """
    if activate_r <= 0 or trail_atr <= 0 or pos.atr0 <= 0 or pos.risk0 <= 0:
        return False
    if pos.direction != "BUY":
        return False
    pos.peak = max(pos.peak or pos.entry, high)
    if pos.peak < pos.entry + activate_r * pos.risk0:
        return False                       # لم يتفعّل بعد
    new_stop = pos.peak - trail_atr * pos.atr0
    if new_stop > pos.stop:
        pos.stop = new_stop
        return True
    return False


def close_position(acc: PaperAccount, pos: PaperPosition, exit_price: float,
                   reason: str, closed_ts: float, fee_rate: float = 0.001,
                   slippage_rate: float = 0.0005) -> ClosedTrade:
    """أغلق صفقة ورقية: طبّق الانزلاق والرسوم واحسب الربح/الخسارة الصافي بالـR."""
    fill = _apply_slippage(exit_price, pos.direction, slippage_rate, entering=False)
    exit_fee = fill * pos.qty * fee_rate
    if pos.direction == "BUY":
        gross = (fill - pos.entry) * pos.qty
    else:
        gross = (pos.entry - fill) * pos.qty
    total_fees = pos.fees_paid + exit_fee
    pnl = gross - exit_fee
    acc.equity += pnl
    risk_per_unit = abs(pos.entry - pos.stop)
    result_r = (pnl / (risk_per_unit * pos.qty)) if risk_per_unit > 0 and pos.qty > 0 else 0.0
    trade = ClosedTrade(
        symbol=pos.symbol, direction=pos.direction, entry=pos.entry, exit=fill,
        qty=pos.qty, pnl=round(pnl, 4), fees_paid=round(total_fees, 4),
        result_r=round(result_r, 3), reason=reason,
        opened_ts=pos.opened_ts, closed_ts=closed_ts,
    )
    if pos in acc.positions:
        acc.positions.remove(pos)
    acc.closed.append(trade)
    return trade


def check_exit(pos: PaperPosition, high: float, low: float):
    """
    هل لمست الشمعة الوقف أم الهدف؟ يُرجع (exit_price, reason) أو None.
    الأسوأ أولًا: نفترض لمس الوقف قبل الهدف عند لمس الاثنين في نفس الشمعة.
    """
    if pos.direction == "BUY":
        if low <= pos.stop:
            return pos.stop, "stop"
        if high >= pos.target:
            return pos.target, "target"
    else:  # SELL
        if high >= pos.stop:
            return pos.stop, "stop"
        if low <= pos.target:
            return pos.target, "target"
    return None


def account_stats(acc: PaperAccount) -> dict:
    """إحصاءات الحساب الورقي: العائد، نسبة النجاح، عامل الربح."""
    closed = acc.closed
    n = len(closed)
    wins = sum(1 for t in closed if t.pnl > 0)
    gross_win = sum(t.pnl for t in closed if t.pnl > 0)
    gross_loss = -sum(t.pnl for t in closed if t.pnl < 0)
    return {
        "equity": round(acc.equity, 2),
        "starting_equity": acc.starting_equity,
        "return_pct": round((acc.equity / acc.starting_equity - 1.0) * 100.0, 2)
        if acc.starting_equity else 0.0,
        "open": len(acc.positions),
        "closed": n,
        "wins": wins,
        "win_rate": round(wins / n * 100.0, 1) if n else 0.0,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else (
            float("inf") if gross_win > 0 else 0.0
        ),
        "net_pnl": round(sum(t.pnl for t in closed), 2),
    }

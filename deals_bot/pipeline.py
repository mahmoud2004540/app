"""خط قرار التداول (Trade Decision Pipeline) — الترقية الاحترافية (Master Build)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
import config
from . import indicators as ind
from .analyzer import detect_trend_pullback
from .confirmation import confirm
from .models import Series
from .risk_engine import DailyState, RiskConfig, RiskEngine
NO_TRADE = "NO_TRADE"
WAIT = "WAIT"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
@dataclass
class Decision:
    status: str
    symbol: str
    reasons: List[str] = field(default_factory=list)
    direction: str = "BUY"
    ai_score: float = 0.0
    entry: float = 0.0
    stop: float = 0.0
    target: float = 0.0
    rr: float = 0.0
    qty: float = 0.0
    risk_amount: float = 0.0

def _passes_live_filters(base: Series, tp: dict, market_bullish=None):
    closes, highs, lows = base.closes(), base.highs(), base.lows()
    if getattr(config, "TREND_MARKET_REGIME", True) and market_bullish is False:
        return False, "⛔ السوق العام (BTC) هابط — لا شراء ضد التيار."
    min_dv = getattr(config, "MIN_DOLLAR_VOL", 0)
    if min_dv > 0 and base.candles:
        recent = base.candles[-20:]
        dv = sum(c.close * c.volume for c in recent) / len(recent)
        if dv < min_dv:
            return False, "⛔ سيولة ضعيفة (حجم دولاري منخفض)."
    if getattr(config, "TREND_REQUIRE_EMA200", False):
        e200 = ind.ema(closes, 200)
        if not e200 or closes[-1] <= e200:
            return False, "⛔ السعر تحت EMA200."
    rmax = getattr(config, "TREND_RSI_MAX", None)
    if rmax is not None and tp.get("rsi") is not None and tp["rsi"] > rmax:
        return False, f"⛔ RSI {tp['rsi']:.0f} > {rmax:.0f} (متمدّد)."
    if getattr(config, "TREND_REQUIRE_MACD", False) and not ind.macd_hist_rising(closes):
        return False, "⛔ هيستوجرام MACD ليس صاعدًا."
    smax = getattr(config, "TREND_STOCH_MAX", None)
    if smax is not None:
        st = ind.stochastic(highs, lows, closes, k=14)
        if st is not None and st > smax:
            return False, f"⛔ Stochastic {st:.0f} > {smax:.0f} (متشبّع)."
    vmin = getattr(config, "TREND_VOL_SURGE_MIN", None)
    if vmin is not None:
        vs = ind.volume_surge(base.volumes(), period=20)
        if vs is None or vs < vmin:
            return False, f"⛔ لا اندفاع حجم كافٍ (< {vmin:g}×) — حركة ضعيفة."
    if getattr(config, "TREND_REQUIRE_MOMENTUM", False) and len(base.closes()) >= 4:
        if not (base.closes()[-1] > base.closes()[-4]):
            return False, "⛔ الزخم السعري ليس مع الصفقة."
    if getattr(config, "TREND_ANTI_REVERSAL", False):
        from .confirmation import last_bar_holds
        if not last_bar_holds(base, "BUY"):
            return False, "⛔ آخر شمعة تنعكس ضد الصفقة."
    fmin = getattr(config, "TREND_FIB_MIN", None)
    fmax = getattr(config, "TREND_FIB_MAX", None)
    if fmin is not None or fmax is not None:
        ok = False
        ph, pl = ind.swing_points(highs, lows, 2, 2)
        if ph:
            sh_idx, sh = ph[-1]
            lows_before = [p for p in pl if p[0] < sh_idx]
            if lows_before:
                rng = sh - lows_before[-1][1]
                if rng > 0:
                    retr = (sh - lows[-1]) / rng
                    ok = (fmin is None or retr >= fmin) and (fmax is None or retr <= fmax)
        if not ok:
            return False, "⛔ الارتداد خارج منطقة فيبوناتشي المطلوبة."
    return True, "✅ اجتاز كل فلاتر البوت الحيّ."

def _risk_engine() -> RiskEngine:
    return RiskEngine(RiskConfig(
        risk_per_trade=getattr(config, "RISK_PER_TRADE_PRO", 0.005),
        max_daily_loss_pct=getattr(config, "MAX_DAILY_LOSS_PCT", 0.015),
        max_consecutive_losses=getattr(config, "MAX_CONSECUTIVE_LOSSES", 3),
        min_rr=getattr(config, "MIN_RISK_REWARD", 2.0),
        max_open_positions=getattr(config, "MAX_OPEN_POSITIONS", 5),
        fee_rate=getattr(config, "FEE_RATE", 0.001),
        slippage_rate=getattr(config, "SLIPPAGE_RATE", 0.0005),
        max_portfolio_heat=getattr(config, "MAX_PORTFOLIO_HEAT", 0.02),
        max_correlation=getattr(config, "MAX_CORRELATION", 0.85,
    )))

def evaluate(base: Series, equity: float, daily: DailyState, confirm_series: Optional[Series] = None, engine: Optional[RiskEngine] = None, market_bullish: Optional[bool] = None) -> Decision:
    eng = engine or _risk_engine()
    symbol = base.symbol
    reasons: List[str] = []
    gate = eng.can_open_new_trade(daily)
    reasons.append(gate.reason)
    if not gate.approved:
        return Decision(NO_TRADE, symbol, reasons)
    tp = detect_trend_pullback(base, rr=getattr(config, "TREND_RR", 2.0), stop_buffer_atr=getattr(config, "TREND_STOP_BUFFER_ATR", 0.0), target_at_resistance=getattr(config, "TREND_TARGET_AT_RESISTANCE", False))
    if not tp:
        reasons.append("⛔ لا يوجد اتجاه صاعد + ارتداد صالح — NO TRADE.")
        return Decision(NO_TRADE, symbol, reasons)
    ai_score = float(tp["score"])
    entry, stop, target = tp["price"], tp["stop"], tp["target"]
    reasons.append(f"📈 اتجاه صاعد + ارتداد (درجة AI = {ai_score:.0f}/100)")
    ok, why = _passes_live_filters(base, tp, market_bullish)
    reasons.append(why)
    if not ok:
        return Decision(NO_TRADE, symbol, reasons, ai_score=ai_score, entry=entry, stop=stop, target=target)
    approve = float(getattr(config, "TREND_MIN_SCORE", getattr(config, "AI_APPROVE_SCORE", 85.0)))
    wait = getattr(config, "AI_WAIT_SCORE", 60.0)
    if ai_score < wait:
        reasons.append(f"⛔ درجة AI < {wait:.0f} — NO TRADE.")
        return Decision(NO_TRADE, symbol, reasons, ai_score=ai_score)
    if ai_score < approve:
        reasons.append(f"⏳ درجة AI {ai_score:.0f} في نطاق الانتظار ({wait:.0f}–{approve:.0f}) — WAIT.")
        return Decision(WAIT, symbol, reasons, ai_score=ai_score, entry=entry, stop=stop, target=target)
    if confirm_series is not None:
        conf = confirm(confirm_series, "BUY", vol_mult=getattr(config, "CONFIRM_VOLUME_MULT", 1.3))
        reasons.extend(conf.reasons)
        if not conf.confirmed:
            return Decision(WAIT, symbol, reasons, ai_score=ai_score, entry=entry, stop=stop, target=target)
    rr_dec = eng.check_reward_risk(entry, stop, target)
    reasons.append(rr_dec.reason)
    rr = eng.reward_risk(entry, stop, target)
    if not rr_dec.approved:
        return Decision(REJECTED, symbol, reasons, ai_score=ai_score, entry=entry, stop=stop, target=target, rr=rr)
    qty, risk_amount = eng.position_size(equity, entry, stop, "BUY")
    if qty <= 0:
        reasons.append("🛑 حجم المركز صفر — رُفضت.")
        return Decision(REJECTED, symbol, reasons, ai_score=ai_score, entry=entry, stop=stop, target=target, rr=rr)
    reasons.append(f"✅ حجم مركز {qty:g} وحدة (مخاطرة {risk_amount:g})")
    reasons.append("✅ APPROVED — اجتازت كل بوّابات خط القرار.")
    return Decision(APPROVED, symbol, reasons, ai_score=ai_score, entry=entry, stop=stop, target=target, rr=rr, qty=qty, risk_amount=risk_amount)

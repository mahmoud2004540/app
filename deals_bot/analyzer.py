"""
محرّك التقييم: يحوّل سلسلة الأسعار إلى صفقة مقترحة بدرجة ثقة.

Scoring engine. Turns a price Series into a scored Deal by combining several
technical signals (trend, RSI, MACD, momentum, volume). The output score is
signed: positive = bullish/BUY, negative = bearish/SELL.

Nothing here is financial advice — it's a rules-based heuristic ranking.
"""

from __future__ import annotations

from typing import List

from . import indicators as ind
from .models import Deal, Series

# معاملات المخاطرة لحساب وقف الخسارة وجني الأرباح من الـ ATR
STOP_ATR_MULT = 1.5
TARGET_ATR_MULT = 2.5

# عتبة الحياد: أي درجة أقل من هذه (بالقيمة المطلقة) تُعتبر بلا إشارة واضحة
NEUTRAL_BAND = 20.0


def analyze_symbol(series: Series, momentum_lookback: int = 10) -> Deal:
    """
    حلّل سلسلة رمز واحد وأرجع صفقة مقترحة.

    Analyze one symbol's candle series and return a scored Deal. On insufficient
    data, returns a NEUTRAL Deal with an `error` message set.
    """
    closes = series.closes()
    highs = series.highs()
    lows = series.lows()
    volumes = series.volumes()

    if len(closes) < 60:
        return Deal(
            symbol=series.symbol,
            market=series.market,
            direction="NEUTRAL",
            score=0.0,
            confidence=0.0,
            price=closes[-1] if closes else 0.0,
            entry=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            risk_reward=0.0,
            error="بيانات غير كافية للتحليل (نحتاج 60 شمعة على الأقل).",
        )

    price = closes[-1]

    rsi_v = ind.rsi(closes, 14)
    ema_fast = ind.ema(closes, 9)
    ema_slow = ind.ema(closes, 21)
    ema_trend = ind.ema(closes, 50)
    macd_v = ind.macd(closes)          # (line, signal, hist) or None
    mom = ind.momentum_pct(closes, momentum_lookback)
    vsurge = ind.volume_surge(volumes, 20)
    atr_v = ind.atr(highs, lows, closes, 14)

    bull = 0.0
    bear = 0.0
    reasons: List[str] = []

    # 1) الاتجاه عبر ترتيب المتوسطات المتحركة (أقوى إشارة)
    uptrend = downtrend = False
    if ema_fast and ema_slow and ema_trend:
        if ema_fast > ema_slow > ema_trend:
            uptrend = True
            bull += 30
            reasons.append("اتجاه صاعد: EMA9 > EMA21 > EMA50")
        elif ema_fast < ema_slow < ema_trend:
            downtrend = True
            bear += 30
            reasons.append("اتجاه هابط: EMA9 < EMA21 < EMA50")
        elif ema_fast > ema_slow:
            bull += 12
            reasons.append("تقاطع قصير المدى صاعد: EMA9 > EMA21")
        elif ema_fast < ema_slow:
            bear += 12
            reasons.append("تقاطع قصير المدى هابط: EMA9 < EMA21")

    # 2) RSI — متوافق مع الاتجاه: لا نراهن على الارتداد عكس اتجاه راسخ
    if rsi_v is not None:
        if rsi_v < 30:
            if downtrend:
                # التشبّع البيعي داخل اتجاه هابط = استمرار الضعف لا ارتداد
                bear += 8
                reasons.append(f"RSI تشبّع بيعي ({rsi_v:.0f}) مع اتجاه هابط — ضعف مستمر")
            else:
                bull += 18
                reasons.append(f"RSI تشبّع بيعي ({rsi_v:.0f}) — ارتداد محتمل")
        elif 45 <= rsi_v <= 65:
            bull += 12
            reasons.append(f"RSI في منطقة صحية صاعدة ({rsi_v:.0f})")
        elif rsi_v > 70:
            if uptrend:
                # التشبّع الشرائي داخل اتجاه صاعد = استمرار القوة لا انعكاس
                bull += 8
                reasons.append(f"RSI تشبّع شرائي ({rsi_v:.0f}) مع اتجاه صاعد — قوة مستمرة")
            else:
                bear += 16
                reasons.append(f"RSI تشبّع شرائي ({rsi_v:.0f}) — تصحيح محتمل")
        elif 35 <= rsi_v < 45:
            bear += 8
            reasons.append(f"RSI ضعيف ({rsi_v:.0f})")

    # 3) MACD
    if macd_v is not None:
        line, signal, hist = macd_v
        rising = ind.macd_hist_rising(closes)
        if hist > 0 and rising:
            bull += 18
            reasons.append("MACD إيجابي وفي تصاعد")
        elif hist > 0:
            bull += 9
            reasons.append("MACD إيجابي")
        elif hist < 0 and not rising:
            bear += 18
            reasons.append("MACD سلبي وفي تراجع")
        elif hist < 0:
            bear += 9
            reasons.append("MACD سلبي")

    # 4) الزخم (Momentum)
    if mom is not None:
        if mom > 1.5:
            bull += 14
            reasons.append(f"زخم إيجابي (+{mom:.1f}%)")
        elif mom < -1.5:
            bear += 14
            reasons.append(f"زخم سلبي ({mom:.1f}%)")

    # 5) تدفّق الحجم — يعزّز الإشارة القائمة فقط
    if vsurge is not None and vsurge > 1.3:
        if bull >= bear:
            bull += 10
        else:
            bear += 10
        reasons.append(f"ارتفاع في حجم التداول (×{vsurge:.1f})")

    score = bull - bear                       # موجب = شراء، سالب = بيع
    score = max(-100.0, min(100.0, score))
    confidence = abs(score)

    if score >= NEUTRAL_BAND:
        direction = "BUY"
    elif score <= -NEUTRAL_BAND:
        direction = "SELL"
    else:
        direction = "NEUTRAL"

    # حساب الدخول / وقف الخسارة / الهدف من الـ ATR
    entry = price
    stop_loss = 0.0
    take_profit = 0.0
    risk_reward = 0.0
    if atr_v and atr_v > 0 and direction != "NEUTRAL":
        if direction == "BUY":
            stop_loss = price - STOP_ATR_MULT * atr_v
            take_profit = price + TARGET_ATR_MULT * atr_v
        else:  # SELL
            stop_loss = price + STOP_ATR_MULT * atr_v
            take_profit = price - TARGET_ATR_MULT * atr_v
        risk = abs(entry - stop_loss)
        reward = abs(take_profit - entry)
        risk_reward = (reward / risk) if risk > 0 else 0.0

    return Deal(
        symbol=series.symbol,
        market=series.market,
        direction=direction,
        score=round(score, 1),
        confidence=round(confidence, 1),
        price=price,
        entry=round(entry, 8),
        stop_loss=round(stop_loss, 8),
        take_profit=round(take_profit, 8),
        risk_reward=round(risk_reward, 2),
        reasons=reasons,
        indicators={
            "rsi": round(rsi_v, 1) if rsi_v is not None else None,
            "ema9": round(ema_fast, 6) if ema_fast else None,
            "ema21": round(ema_slow, 6) if ema_slow else None,
            "ema50": round(ema_trend, 6) if ema_trend else None,
            "macd_hist": round(macd_v[2], 6) if macd_v else None,
            "momentum_pct": round(mom, 2) if mom is not None else None,
            "volume_surge": round(vsurge, 2) if vsurge is not None else None,
            "atr": round(atr_v, 6) if atr_v else None,
        },
    )


def rank_deals(
    all_series: List[Series],
    top: int = 5,
    direction: str = "any",
    momentum_lookback: int = 10,
) -> List[Deal]:
    """
    حلّل عدة رموز ورتّبها لإرجاع أفضل الصفقات.

    Analyze many symbols and return the strongest `top` deals.
      direction = "buy"  → only BUY deals
      direction = "sell" → only SELL deals
      direction = "any"  → strongest signal in either direction
    """
    deals = [analyze_symbol(s, momentum_lookback=momentum_lookback) for s in all_series]
    actionable = [d for d in deals if d.is_actionable()]

    if direction == "buy":
        actionable = [d for d in actionable if d.direction == "BUY"]
        actionable.sort(key=lambda d: d.score, reverse=True)
    elif direction == "sell":
        actionable = [d for d in actionable if d.direction == "SELL"]
        actionable.sort(key=lambda d: d.score)  # most negative first
    else:
        actionable.sort(key=lambda d: d.confidence, reverse=True)

    return actionable[:top]

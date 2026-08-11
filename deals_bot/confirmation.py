"""
تأكيد الدخول من إطار أدنى (15 دقيقة) — الترقية الاحترافية (Master Build).

Entry confirmation on the lower timeframe. After the 1H trend + pullback set up,
we require the 15M chart to actually confirm the turn before entering:

  LONG  : bullish engulfing + volume expansion + break of minor structure (up)
  SHORT : bearish engulfing + volume expansion + break of minor structure (down)

Only acts on CLOSED candles (the last candle in the series is treated as closed),
so there is no look-ahead. Pure/offline-testable — takes a Series, no network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from . import indicators as ind
from .models import Series


@dataclass
class Confirmation:
    confirmed: bool
    reasons: List[str]


def bullish_engulfing(series: Series) -> bool:
    """آخر شمعة صاعدة يبتلع جسمها جسم الشمعة الهابطة السابقة."""
    c = series.candles
    if len(c) < 2:
        return False
    prev, cur = c[-2], c[-1]
    prev_bear = prev.close < prev.open
    cur_bull = cur.close > cur.open
    engulf = cur.close >= prev.open and cur.open <= prev.close
    return prev_bear and cur_bull and engulf


def bearish_engulfing(series: Series) -> bool:
    """آخر شمعة هابطة يبتلع جسمها جسم الشمعة الصاعدة السابقة."""
    c = series.candles
    if len(c) < 2:
        return False
    prev, cur = c[-2], c[-1]
    prev_bull = prev.close > prev.open
    cur_bear = cur.close < cur.open
    engulf = cur.open >= prev.close and cur.close <= prev.open
    return prev_bull and cur_bear and engulf


def volume_expansion(series: Series, mult: float = 1.3, period: int = 20) -> bool:
    """حجم شمعة التأكيد أعلى من متوسّط الحجم بمضاعف mult."""
    vs = ind.volume_surge(series.volumes(), period)
    return vs is not None and vs >= mult


def broke_minor_structure(series: Series, direction: str, lookback: int = 10) -> bool:
    """
    كسر بنية صغرى: للـLONG إغلاق فوق أعلى قمة أخيرة؛ للـSHORT إغلاق تحت أدنى قاع.
    """
    c = series.candles
    if len(c) < lookback + 1:
        return False
    window = c[-lookback - 1:-1]
    close = c[-1].close
    if direction == "BUY":
        return close > max(x.high for x in window)
    return close < min(x.low for x in window)


def confirm(series: Series, direction: str, vol_mult: float = 1.3) -> Confirmation:
    """
    تأكيد الدخول: انغلاف + توسّع حجم + كسر بنية صغرى في اتجاه الصفقة.

    Requires the pattern + volume + structure break to all agree. Momentum is
    implied by the engulfing close + structure break.
    """
    reasons: List[str] = []
    if direction == "BUY":
        eng = bullish_engulfing(series)
        eng_txt = "انغلاف صاعد (Bullish Engulfing)"
    else:
        eng = bearish_engulfing(series)
        eng_txt = "انغلاف هابط (Bearish Engulfing)"
    vol = volume_expansion(series, vol_mult)
    struct = broke_minor_structure(series, direction)

    if eng:
        reasons.append(f"✅ {eng_txt}")
    if vol:
        reasons.append("✅ توسّع في الحجم")
    if struct:
        reasons.append("✅ كسر بنية صغرى في اتجاه الصفقة")

    ok = eng and vol and struct
    if not ok:
        missing = []
        if not eng:
            missing.append("انغلاف")
        if not vol:
            missing.append("حجم")
        if not struct:
            missing.append("كسر بنية")
        reasons.append("⏳ لم يكتمل التأكيد — ناقص: " + "، ".join(missing))
    return Confirmation(confirmed=ok, reasons=reasons)

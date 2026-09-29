"""تأكيد الدخول من إطار أدنى + فلتر آخر شمعة."""

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
    c = series.candles
    if len(c) < 2:
        return False
    prev, cur = c[-2], c[-1]
    prev_bear = prev.close < prev.open
    cur_bull = cur.close > cur.open
    engulf = cur.close >= prev.open and cur.open <= prev.close
    return prev_bear and cur_bull and engulf


def bearish_engulfing(series: Series) -> bool:
    c = series.candles
    if len(c) < 2:
        return False
    prev, cur = c[-2], c[-1]
    prev_bull = prev.close > prev.open
    cur_bear = cur.close < cur.open
    engulf = cur.open >= prev.close and cur.close <= prev.open
    return prev_bull and cur_bear and engulf


def volume_expansion(series: Series, mult: float = 1.3, period: int = 20) -> bool:
    vs = ind.volume_surge(series.volumes(), period)
    return vs is not None and vs >= mult


def broke_minor_structure(series: Series, direction: str, lookback: int = 10) -> bool:
    c = series.candles
    if len(c) < lookback + 1:
        return False
    window = c[-lookback - 1:-1]
    close = c[-1].close
    if direction == "BUY":
        return close > max(x.high for x in window)
    return close < min(x.low for x in window)


def confirm(series: Series, direction: str, vol_mult: float = 1.3) -> Confirmation:
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


def last_bar_holds(series: Series, direction: str = "BUY") -> bool:
    candles = series.candles
    if len(candles) < 2:
        return False
    prev, cur = candles[-2], candles[-1]
    if direction == "BUY":
        return cur.close > cur.open and cur.close >= prev.close
    return cur.close < cur.open and cur.close <= prev.close

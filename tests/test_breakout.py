"""اختبارات كاشف «اختراق الاتجاه» (Donchian breakout) — offline بلا شبكة."""

import math

from deals_bot.analyzer import detect_breakout
from deals_bot.models import Candle, Series


def _range_then_breakout():
    c = []
    for i in range(70):
        p = 100 + math.sin(i / 3.0) * 2.0 + i * 0.05        # نطاق عرضي بميل خفيف
        c.append(Candle(ts=i * 3600, open=p, high=p * 1.005,
                        low=p * 0.995, close=p, volume=1000))
    prior_high = max(x.high for x in c[-21:])
    brk = prior_high * 1.02                                   # اختراق ~2% بحجم عالٍ
    c.append(Candle(ts=70 * 3600, open=c[-1].close, high=brk * 1.002,
                    low=c[-1].close * 0.999, close=brk, volume=3500))
    return Series("T", "crypto", c)


def test_breakout_fires_on_range_break():
    d = detect_breakout(_range_then_breakout())
    assert d is not None
    assert d["direction"] == "BUY"
    assert d["stop"] < d["price"] < d["target"]
    # نسبة الهدف/المخاطرة ≈ 2
    rr = (d["target"] - d["price"]) / (d["price"] - d["stop"])
    assert abs(rr - 2.0) < 0.01


def test_breakout_none_without_break():
    # سعر داخل النطاق (لا اختراق) → لا إشارة
    c = [Candle(ts=i * 3600, open=100, high=101, low=99, close=100, volume=1000)
         for i in range(70)]
    assert detect_breakout(Series("T", "crypto", c)) is None


def test_breakout_none_on_short_series():
    c = [Candle(ts=i * 3600, open=100, high=101, low=99, close=100, volume=1000)
         for i in range(30)]
    assert detect_breakout(Series("T", "crypto", c)) is None

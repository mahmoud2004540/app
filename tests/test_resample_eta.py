"""اختبارات: بناء إطار 30m بدمج 15m + تقدير الزمن المتوقّع للهدف (offline)."""

from deals_bot.analyzer import TF_HOURS, estimate_eta_hours
from deals_bot.formatter import _fmt_eta
from deals_bot.models import Candle
from deals_bot.providers import resample_candles


def test_resample_merges_pairs():
    c = [Candle(ts=i * 900, open=i, high=i + 2, low=i - 1, close=i + 1, volume=10)
         for i in range(6)]
    r = resample_candles(c, 2)
    assert len(r) == 3
    # أول شمعة 30m = دمج 0 و1: open=0, close=2, high=3, low=-1, vol=20
    assert r[0].open == 0 and r[0].close == 2
    assert r[0].high == 3 and r[0].low == -1 and r[0].volume == 20


def test_resample_drops_incomplete_oldest():
    c = [Candle(ts=i * 900, open=i, high=i + 1, low=i, close=i, volume=1)
         for i in range(5)]
    r = resample_candles(c, 2)
    # 5 شمعات → آخر 4 تتجمّع في 2، الأقدم تُهمَل لعدم اكتمال المجموعة
    assert len(r) == 2
    assert r[-1].close == c[-1].close        # أحدث شمعة مكتملة دائمًا


def test_resample_factor_one_noop():
    c = [Candle(ts=i, open=1, high=1, low=1, close=1, volume=1) for i in range(3)]
    assert len(resample_candles(c, 1)) == 3


def test_eta_basic():
    # مسافة 10، ATR=2 → 5 شمعات؛ على 1h = 5 ساعات
    assert estimate_eta_hours(100, 110, 2.0, TF_HOURS["1h"]) == 5.0
    # على 30m = 2.5 ساعة
    assert estimate_eta_hours(100, 110, 2.0, TF_HOURS["30m"]) == 2.5


def test_eta_invalid_returns_none():
    assert estimate_eta_hours(100, 110, 0, 1.0) is None
    assert estimate_eta_hours(100, 100, 2.0, 1.0) is None
    assert estimate_eta_hours(0, 110, 2.0, 1.0) is None


def test_fmt_eta_units():
    assert "دقيقة" in _fmt_eta(0.5)
    assert "ساعة" in _fmt_eta(5.0)
    assert "يوم" in _fmt_eta(48.0)

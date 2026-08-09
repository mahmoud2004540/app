"""اختبارات محرّك تقاطع الأدلة — بدون شبكة."""

import math

from deals_bot import indicators as ind
from deals_bot.confluence import analyze_confluence
from deals_bot.formatter import format_confluence
from deals_bot.models import Candle, Series


def _series(symbol, closes, market="crypto", vol=1000.0):
    candles = []
    ts = 0.0
    for c in closes:
        candles.append(
            Candle(ts=ts, open=c, high=c * 1.01, low=c * 0.99, close=c, volume=vol)
        )
        ts += 3600
    return Series(symbol=symbol, market=market, candles=candles)


def _trend(start, slope, n, wiggle=0.0):
    return [start + slope * i + wiggle * math.sin(i / 3.0) for i in range(n)]


# ---------------------------- new indicators ----------------------------- #
def test_bollinger_order():
    low, mid, up = ind.bollinger([10 + math.sin(i) for i in range(30)], 20)
    assert low < mid < up


def test_stochastic_bounds():
    highs = [10 + i * 0.1 for i in range(30)]
    lows = [9 + i * 0.1 for i in range(30)]
    closes = [9.5 + i * 0.1 for i in range(30)]
    st = ind.stochastic(highs, lows, closes, 14)
    assert 0 <= st <= 100


def test_swing_points_detects_pivots():
    highs = [1, 2, 3, 2, 1, 2, 4, 2, 1]
    lows = [h - 0.5 for h in highs]
    ph, pl = ind.swing_points(highs, lows, 1, 1)
    assert any(p[1] == 3 for p in ph)
    assert len(pl) >= 1


# ---------------------------- confluence --------------------------------- #
def test_confluence_uptrend_is_buy_with_agreement():
    rep = analyze_confluence(_series("UP", _trend(100.0, 0.6, 140, 1.0)), "1h", fear_greed=50)
    assert rep.decision == "شراء"
    assert rep.agree_bull > rep.agree_bear
    assert rep.targets and rep.targets[0] > rep.entry > rep.stop_loss
    assert rep.risk_reward >= 2.0            # بوابة 1:2


def test_confluence_downtrend_is_sell():
    rep = analyze_confluence(_series("DOWN", _trend(200.0, -0.5, 140, 2.0)), "1h", fear_greed=50)
    assert rep.decision == "بيع"
    assert rep.agree_bear > rep.agree_bull


def test_unavailable_schools_marked_not_guessed():
    rep = analyze_confluence(_series("X", _trend(100.0, 0.6, 140, 1.0)), "1h", fear_greed=None)
    names = {s.name: s for s in rep.schools}
    # مدارس يجب أن تكون معلَّمة كغير متوفّرة
    for n in ("أساسي", "كلّي/بيني", "أونشين", "مشاعر"):
        assert n in names and names[n].available is False


def test_forex_volume_school_unavailable_when_zero_volume():
    s = _series("EURUSD=X", _trend(1.1, 0.001, 140, 0.002), market="forex", vol=0.0)
    rep = analyze_confluence(s, "1h", fear_greed=None)
    vol = next(x for x in rep.schools if x.name == "حجم/تدفق أوامر")
    assert vol.available is False


def test_report_renders_all_sections():
    rep = analyze_confluence(_series("UP", _trend(100.0, 0.6, 140, 1.0)), "1h", fear_greed=20)
    text = format_confluence(rep)
    for token in ["الأصل", "ملخص المدارس", "المدارس المتفقة", "القرار",
                  "مستوى الثقة", "المخاطرة/العائد"]:
        assert token in text

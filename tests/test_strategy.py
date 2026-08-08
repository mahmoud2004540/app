"""اختبارات إدارة المخاطر وفلتر الجودة والباك-تِست — بدون شبكة."""

import math

from deals_bot.analyzer import add_position_sizing, analyze_symbol, rank_deals
from deals_bot.backtester import backtest_series
from deals_bot.models import Candle, Series


def _trend(start, slope, n, wiggle=0.0):
    out = []
    for i in range(n):
        out.append(start + slope * i + wiggle * math.sin(i / 3.0))
    return out


def _series(symbol, closes, market="crypto", vol=1000.0):
    candles = []
    ts = 0.0
    for c in closes:
        candles.append(
            Candle(ts=ts, open=c, high=c * 1.01, low=c * 0.99, close=c, volume=vol)
        )
        ts += 3600
    return Series(symbol=symbol, market=market, candles=candles)


# ---------------------------- position sizing ---------------------------- #
def test_position_sizing_risks_expected_amount():
    d = analyze_symbol(_series("UP", _trend(100.0, 0.6, 120, wiggle=1.0)))
    add_position_sizing(d, balance=1000.0, risk_pct=0.01)
    # المخاطرة = 1% من 1000 = 10
    assert d.risk_amount == 10.0
    # حجم الصفقة × مسافة وقف الخسارة ≈ المبلغ المخاطَر به
    risk_per_unit = abs(d.entry - d.stop_loss)
    assert math.isclose(d.qty * risk_per_unit, 10.0, rel_tol=1e-6)


def test_position_sizing_ignored_when_no_balance():
    d = analyze_symbol(_series("UP", _trend(100.0, 0.6, 120, wiggle=1.0)))
    add_position_sizing(d, balance=0.0, risk_pct=0.01)
    assert d.qty is None and d.risk_amount is None


# --------------------------- quality filter ------------------------------ #
def test_min_confidence_filters_weak_deals():
    strong = _series("UP", _trend(100.0, 0.6, 120, wiggle=1.0))
    all_series = [strong]
    high = rank_deals(all_series, top=5, min_confidence=95)
    low = rank_deals(all_series, top=5, min_confidence=0)
    # عتبة عالية جدًا تستبعد الصفقة، وعتبة صفر تقبلها
    assert len(low) >= 1
    assert len(high) == 0


# ------------------------------ backtest --------------------------------- #
def test_backtest_uptrend_is_profitable():
    closes = _trend(100.0, 0.8, 300, wiggle=2.0)
    res = backtest_series(_series("UP", closes))
    assert res.n > 0
    # اتجاه صاعد قوي يجب أن يعطي عائدًا موجبًا إجمالًا
    assert res.total_r > 0
    assert 0 <= res.win_rate <= 100


def test_backtest_result_math_consistent():
    closes = _trend(100.0, 0.8, 300, wiggle=2.0)
    res = backtest_series(_series("UP", closes))
    # مجموع R لكل الصفقات = إجمالي R
    assert math.isclose(res.total_r, sum(t.result_r for t in res.trades), rel_tol=1e-9)
    # العائد المتوقّع = الإجمالي / العدد
    assert math.isclose(res.expectancy_r, res.total_r / res.n, rel_tol=1e-9)


# ------------------------- coinbase (real-time) parsing ------------------- #
def test_parse_coinbase_maps_and_sorts():
    from deals_bot.providers import _parse_coinbase

    # Coinbase يرجع الأحدث أولًا بصيغة [time, low, high, open, close, volume]
    raw = [
        [1002, 9.0, 11.0, 10.0, 10.5, 100.0],   # newest
        [1001, 8.5, 10.5, 9.5, 10.0, 90.0],
        [1000, 8.0, 10.0, 9.0, 9.5, 80.0],      # oldest
    ]
    s = _parse_coinbase(raw, "BTC-USD")
    # مرتّبة تصاعديًا حسب الزمن
    assert [c.ts for c in s.candles] == [1000.0, 1001.0, 1002.0]
    # التعيين صحيح: open=idx3, high=idx2, low=idx1, close=idx4, volume=idx5
    last = s.candles[-1]
    assert (last.open, last.high, last.low, last.close, last.volume) == (
        10.0, 11.0, 9.0, 10.5, 100.0,
    )
    assert s.market == "crypto" and s.symbol == "BTC-USD"


# ------------------------------- whales ---------------------------------- #
def _series_hlcv(symbol, closes, volumes):
    candles = []
    ts = 0.0
    for c, v in zip(closes, volumes):
        candles.append(
            Candle(ts=ts, open=c, high=c * 1.01, low=c * 0.99, close=c, volume=v)
        )
        ts += 3600
    return Series(symbol=symbol, market="crypto", candles=candles)


def test_whale_detected_on_volume_spike_uptrend():
    closes = _trend(100.0, 0.6, 120, wiggle=1.0)
    volumes = [1000.0] * 119 + [6000.0]          # ×6 spike on the last bar
    d = analyze_symbol(_series_hlcv("WHALE", closes, volumes))
    assert d.whale is True
    assert d.direction == "BUY"
    # السبب الأول يجب أن يكون سبب الحوت المقنع
    assert "🐋" in d.reasons[0]


def test_no_whale_without_volume_spike():
    closes = _trend(100.0, 0.6, 120, wiggle=1.0)
    volumes = [1000.0] * 120                      # حجم ثابت — لا حوت
    d = analyze_symbol(_series_hlcv("CALM", closes, volumes))
    assert d.whale is False


def test_pump_detected_on_fast_spike():
    # اتجاه هادئ ثم قفزة سعرية سريعة + حجم عالٍ على آخر شمعات
    closes = [100.0 + 0.1 * i for i in range(117)] + [112.0, 116.0, 121.0]
    volumes = [1000.0] * 117 + [3000.0, 3200.0, 3500.0]
    d = analyze_symbol(_series_hlcv("PUMP", closes, volumes))
    assert d.pump is True
    assert d.direction == "BUY"
    assert "🚀" in d.reasons[0]


def test_no_pump_on_slow_move():
    closes = _trend(100.0, 0.2, 120, wiggle=0.5)   # حركة بطيئة
    volumes = [1000.0] * 120
    d = analyze_symbol(_series_hlcv("SLOW", closes, volumes))
    assert d.pump is False


def test_expected_moves_match_atr_levels():
    from deals_bot.formatter import expected_moves

    d = analyze_symbol(
        _series_hlcv("UP", _trend(100.0, 0.6, 120, wiggle=1.0), [1000.0] * 120)
    )
    tgt, stp = expected_moves(d)
    # يجب أن يطابقا نسبة الهدف/الوقف من سعر الدخول
    assert math.isclose(tgt, abs(d.take_profit - d.entry) / d.entry * 100.0, rel_tol=1e-9)
    assert math.isclose(stp, abs(d.stop_loss - d.entry) / d.entry * 100.0, rel_tol=1e-9)
    # نسبة الهدف/الوقف ≈ نسبة المخاطرة/العائد (2.5/1.5) — مع تسامح للتقريب
    assert math.isclose(tgt / stp, d.risk_reward, rel_tol=0.02)


def test_whale_only_filter_and_priority():
    from deals_bot.strategy import best_deals  # noqa: F401 (import guard)

    whale = analyze_symbol(
        _series_hlcv("WHALE", _trend(100.0, 0.6, 120, wiggle=1.0),
                     [1000.0] * 119 + [6000.0])
    )
    calm = analyze_symbol(
        _series_hlcv("CALM", _trend(100.0, 0.6, 120, wiggle=1.0), [1000.0] * 120)
    )
    # الحوت يجب أن يحمل ثقة أعلى (بسبب تعزيز +22)
    assert whale.confidence > calm.confidence


def test_grade_full_confluence_star():
    from deals_bot.formatter import grade

    d = analyze_symbol(
        _series_hlcv("WHALE", _trend(100.0, 0.6, 120, wiggle=1.0),
                     [1000.0] * 119 + [6000.0])
    )
    # حوت + ثقة عالية + تأكيد من إطار أعلى = توافق كامل ⭐
    d.confirmed = True
    assert "⭐" in grade(d)
    # بدون تأكيد لا يُمنح التوافق الكامل
    d.confirmed = None
    assert "⭐" not in grade(d)

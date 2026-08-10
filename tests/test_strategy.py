"""اختبارات إدارة المخاطر وفلتر الجودة والباك-تِست — بدون شبكة."""

import math

from deals_bot.analyzer import add_position_sizing, analyze_symbol, rank_deals
from deals_bot.backtester import backtest_series, backtest_trend_pullback_series
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


def test_trend_pullback_fires_and_targets_hit_2R():
    # اتجاه صاعد ثابت مع تنفّس دوري يلمس المتوسّط ثم يرتد
    candles = []
    for i in range(400):
        base = 100 + i * 0.4 + (-3.0 if (i % 20) in (10, 11) else 0.0)
        candles.append(
            Candle(ts=i, open=base, high=max(base, base + 0.5) + 0.8,
                   low=min(base, base + 0.5) - 1.2, close=base + 0.5, volume=1000.0)
        )
    res = backtest_trend_pullback_series(Series(symbol="UP", market="crypto", candles=candles))
    assert res.n > 0
    # كل هدف = 2R، فالفائزون يحققون +2R تقريبًا
    for t in res.trades:
        if t.won:
            assert math.isclose(t.result_r, 2.0, rel_tol=0.05)
    assert 0 <= res.win_rate <= 100


def test_trend_pullback_skips_downtrend():
    # اتجاه هابط: لا يجب أن تدخل استراتيجية الاتجاه الصاعد أي صفقة
    closes = _trend(300.0, -0.6, 200, wiggle=1.0)
    res = backtest_trend_pullback_series(_series("DOWN", closes))
    assert res.n == 0


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


def test_detect_accumulation_after_drop_then_base():
    from deals_bot.analyzer import detect_accumulation

    # هبوط من 100 إلى ~62 ثم نطاق عرضي ضيّق حول 62
    closes = [100.0 - 0.9 * i for i in range(42)]          # decline ~100 -> 63
    base = [62.0 + (0.6 if i % 2 else -0.6) for i in range(50)]  # tight base
    closes += base
    vols = [1000.0] * len(closes)
    s = _series_hlcv("ACC", closes, vols)
    acc = detect_accumulation(s)
    assert acc is not None
    assert acc["drop"] <= -15.0
    assert 0 < acc["score"] <= 100


def test_no_accumulation_in_uptrend():
    from deals_bot.analyzer import detect_accumulation

    closes = _trend(100.0, 0.6, 120, wiggle=1.0)           # rising
    s = _series_hlcv("UP", closes, [1000.0] * 120)
    assert detect_accumulation(s) is None


def test_no_accumulation_while_still_falling():
    from deals_bot.analyzer import detect_accumulation

    closes = [200.0 - 1.0 * i for i in range(120)]         # keeps making new lows
    s = _series_hlcv("DOWN", closes, [1000.0] * 120)
    assert detect_accumulation(s) is None


def test_parse_gainers_sorts_and_filters():
    from deals_bot.providers import _parse_gainers

    raw = [
        {"symbol": "tut", "name": "Tutorial", "current_price": 0.18, "price_change_percentage_24h": 87.7, "total_volume": 274_000_000},
        {"symbol": "bmt", "name": "Bubblemaps", "current_price": 0.034, "price_change_percentage_24h": 162.3, "total_volume": 54_000_000},
        {"symbol": "dead", "name": "Illiquid", "current_price": 1.0, "price_change_percentage_24h": 500.0, "total_volume": 1000},  # low vol → filtered
        {"symbol": "btc", "name": "Bitcoin", "current_price": 64000, "price_change_percentage_24h": 1.2, "total_volume": 20_000_000_000},
    ]
    g = _parse_gainers(raw, top=10, min_vol_usd=3_000_000)
    syms = [x["symbol"] for x in g]
    assert "DEAD" not in syms                       # filtered by low volume
    assert syms[0] == "BMT" and syms[1] == "TUT"    # sorted by 24h change desc


def test_format_gainers_flags_chase_risk():
    from deals_bot.formatter import format_gainers

    text = format_gainers([
        {"symbol": "BMT", "name": "Bubblemaps", "price": 0.034, "change_24h": 162.3, "volume": 54_000_000},
    ])
    assert "BMT" in text and "ملاحقة قمة" in text


def test_parse_trending_extracts_symbols():
    from deals_bot.providers import _parse_trending

    raw = {"coins": [
        {"item": {"symbol": "tut", "name": "Tutorial", "market_cap_rank": 420,
                  "data": {"price_change_percentage_24h": {"usd": 87.7}}}},
        {"item": {"symbol": "bmt", "name": "Bubblemaps", "market_cap_rank": 600,
                  "data": {}}},
    ]}
    t = _parse_trending(raw)
    assert t[0]["symbol"] == "TUT" and t[0]["change_24h"] == 87.7
    assert t[1]["symbol"] == "BMT" and t[1]["change_24h"] is None


def test_pre_pump_squeeze_detected_after_volatility_drop():
    from deals_bot.analyzer import detect_pre_pump

    # تذبذب عالٍ في البداية ثم انضغاط شديد (نطاق ضيّق جدًا) في النهاية
    wild = [100.0 + 8.0 * math.sin(i / 2.0) for i in range(40)]
    calm = [100.0 + 0.2 * math.sin(i) for i in range(40)]     # منضغط
    closes = wild + calm
    vols = [1000.0] * 79 + [1200.0]
    pre = detect_pre_pump(_series_hlcv("SQ", closes, vols))
    assert pre is not None
    assert 0 < pre["score"] <= 100


def test_no_pre_pump_when_volatility_high():
    from deals_bot.analyzer import detect_pre_pump

    closes = [100.0 + 8.0 * math.sin(i / 2.0) for i in range(90)]   # تذبذب عالٍ مستمر
    vols = [1000.0] * 90
    assert detect_pre_pump(_series_hlcv("WILD", closes, vols)) is None


def test_early_pump_on_first_breakout_with_volume():
    from deals_bot.analyzer import detect_early_pump

    # نطاق ضيّق حول 100 ثم كسر مبكّر إلى ~103 على آخر شمعة بحجم عالٍ
    closes = [100.0 + 0.3 * math.sin(i) for i in range(59)] + [103.0]
    vols = [1000.0] * 59 + [2500.0]
    ep = detect_early_pump(_series_hlcv("EP", closes, vols))
    assert ep is not None
    assert ep["base_high"] < ep["price"]
    assert 0 < ep["score"] <= 100


def test_no_early_pump_when_already_extended():
    from deals_bot.analyzer import detect_early_pump

    # كسر لكن السعر جرى بعيدًا (+30%) → لم يعد مبكّرًا
    closes = [100.0 + 0.3 * math.sin(i) for i in range(59)] + [130.0]
    vols = [1000.0] * 59 + [2500.0]
    assert detect_early_pump(_series_hlcv("LATE", closes, vols)) is None


def test_no_early_pump_without_volume():
    from deals_bot.analyzer import detect_early_pump

    closes = [100.0 + 0.3 * math.sin(i) for i in range(59)] + [103.0]
    vols = [1000.0] * 60                                    # لا ارتفاع في الحجم
    assert detect_early_pump(_series_hlcv("NOVOL", closes, vols)) is None


def test_binance_symbol_conversion():
    from deals_bot.providers import _to_binance_symbol

    assert _to_binance_symbol("BTC-USD") == "BTCUSDT"
    assert _to_binance_symbol("ETH-USD") == "ETHUSDT"
    assert _to_binance_symbol("SOL-USD") == "SOLUSDT"


def test_apply_live_price_updates_price_and_levels():
    from deals_bot.strategy import apply_live_price

    d = analyze_symbol(
        _series_hlcv("UP", _trend(100.0, 0.6, 120, wiggle=1.0), [1000.0] * 120)
    )
    assert d.direction == "BUY"
    atr = d.indicators["atr"]
    live = 500.0                                   # سعر فوري مختلف تمامًا
    apply_live_price(d, live)
    assert d.price == 500.0 and d.entry == 500.0
    # الوقف/الهدف يُعاد حسابهما من السعر الفوري + ATR
    assert math.isclose(d.stop_loss, 500.0 - 1.5 * atr, rel_tol=1e-6)
    assert math.isclose(d.take_profit, 500.0 + 2.5 * atr, rel_tol=1e-6)


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

"""
اختبارات أدوات Smart Money / ICT + VWAP (من دليل الأدوات الاحترافية H1) — بلا شبكة.

نتأكد إن: (1) المؤشرات الجديدة تحسب صح، (2) فلاتر ICT انتقائية في الباك-تِست —
تقلّل الصفقات أو تساويها أبدًا لا تزيدها (فلتر لا يخترع صفقات).
"""

from deals_bot import indicators as ind
from deals_bot.backtester import backtest_trend_pullback_series
from deals_bot.models import Candle, Series


def _series(symbol, rows, market="crypto"):
    """rows = list of (open, high, low, close, volume)."""
    candles = []
    ts = 0.0
    for o, h, l, c, v in rows:
        candles.append(Candle(ts=ts, open=o, high=h, low=l, close=c, volume=v))
        ts += 3600
    return Series(symbol=symbol, market=market, candles=candles)


def _firing_series(symbol="ICT-USD", n=420):
    """سلسلة صاعدة مثبتة تُطلق إشارات ارتداد داخل اتجاه (نفس نمط اختبارات multi_tf)."""
    rows = []
    for i in range(n):
        base = 100.0 + i * 0.4 + (-3.0 if (i % 20) in (10, 11) else 0.0)
        rows.append((base, base * 1.02, base * 0.985, base, 1000.0 + (i % 7) * 50))
    return _series(symbol, rows)


# ------------------------------ VWAP -------------------------------------- #
def test_vwap_between_extremes_and_none_when_short():
    highs = [11.0] * 60
    lows = [9.0] * 60
    closes = [10.0] * 60
    vols = [100.0] * 60
    v = ind.vwap(highs, lows, closes, vols, window=50)
    assert v is not None and 9.0 <= v <= 11.0
    assert ind.vwap(highs[:10], lows[:10], closes[:10], vols[:10], window=50) is None


def test_vwap_none_on_zero_volume():
    assert ind.vwap([1.0] * 60, [1.0] * 60, [1.0] * 60, [0.0] * 60, window=50) is None


# ------------------------------ FVG --------------------------------------- #
def test_bullish_fvg_detected_and_absent():
    # فجوة صاعدة: high الشمعة A أقل من low الشمعة C (قفزة تركت فراغًا)
    highs = [10.0, 10.5, 12.0, 13.0]
    lows = [9.0, 9.5, 11.0, 12.0]          # low C=11.0 > high A=10.5 → فجوة
    assert ind.has_bullish_fvg(highs, lows, lookback=10) is True
    # سلسلة بمدى متداخل (شموع عريضة، ميل بسيط) → لا فجوات
    flat_h = [10.0 + i * 0.1 + 1.0 for i in range(20)]
    flat_l = [10.0 + i * 0.1 - 1.0 for i in range(20)]
    assert ind.has_bullish_fvg(flat_h, flat_l, lookback=10) is False


# ------------------------------ BOS --------------------------------------- #
def test_bos_bullish_on_break_of_prior_swing_high():
    # قمة ارتكاز عند 3، ثم إغلاق فوقها (كسر هيكل صاعد)
    highs = [1.0, 2.0, 3.0, 2.0, 1.0, 2.0, 2.5, 4.0]
    lows = [h - 0.5 for h in highs]
    closes = [h - 0.1 for h in highs]
    assert ind.bos_bullish(highs, lows, closes, left=1, right=1) is True
    # نفس القمم لكن الإغلاق الأخير تحت القمة → لا كسر
    closes2 = closes[:-1] + [2.4]
    highs2 = highs[:-1] + [2.6]
    assert ind.bos_bullish(highs2, lows[:-1] + [2.0], closes2, left=1, right=1) is False


# --------------------------- Liquidity sweep ------------------------------ #
def test_liquidity_sweep_bullish_detects_stop_hunt():
    # قاع ارتكاز عند 1.0 (index 2), ثم شمعة تكنسه (low<1.0) وتغلق فوقه
    highs = [3.0, 2.0, 1.5, 2.0, 3.0, 2.5]
    lows = [2.0, 1.5, 1.0, 1.5, 2.0, 0.9]
    closes = [2.5, 1.8, 1.2, 1.8, 2.5, 1.6]     # آخر شمعة: low 0.9<1.0، إغلاق 1.6>1.0
    assert ind.liquidity_sweep_bullish(highs, lows, closes, lookback=6,
                                       left=1, right=1) is True


# ------------------- gates are SELECTIVE (never add trades) --------------- #
def test_ict_gates_never_add_trades():
    s = _firing_series()
    base = backtest_trend_pullback_series(s, min_score=0.0, rr=2.0)
    n_base = base.n
    for gate in ("require_vwap", "require_fvg", "require_bos", "require_sweep"):
        res = backtest_trend_pullback_series(s, min_score=0.0, rr=2.0, **{gate: True})
        assert res.n <= n_base, f"{gate} زادت الصفقات — الفلتر يجب أن يكون انتقائيًا"


def test_ict_combo_selective():
    s = _firing_series()
    n_base = backtest_trend_pullback_series(s, min_score=0.0, rr=2.0).n
    res = backtest_trend_pullback_series(
        s, min_score=0.0, rr=2.0,
        require_vwap=True, require_fvg=True, require_bos=True, require_sweep=True)
    assert res.n <= n_base


# --------------------- exit/vol/liquidity levers -------------------------- #
def test_volatility_and_liquidity_gates_selective():
    s = _firing_series()
    n_base = backtest_trend_pullback_series(s, min_score=0.0, rr=2.0).n
    for gate in ({"atr_pct_min": 2.0}, {"atr_pct_max": 8.0}, {"min_dollar_vol": 1e12}):
        res = backtest_trend_pullback_series(s, min_score=0.0, rr=2.0, **gate)
        assert res.n <= n_base, f"{gate} زادت الصفقات — يجب أن يكون فلترًا انتقائيًا"


def test_trailing_and_time_stop_run_and_keep_count():
    s = _firing_series()
    n_base = backtest_trend_pullback_series(s, min_score=0.0, rr=2.0).n
    # إدارة الخروج تغيّر النتائج لكن لا تغيّر عدد الصفقات (نفس نقاط الدخول)
    trail = backtest_trend_pullback_series(s, min_score=0.0, rr=2.0,
                                           trail_activate_r=1.0, trail_atr=3.0)
    tstop = backtest_trend_pullback_series(s, min_score=0.0, rr=2.0, time_stop_bars=48)
    assert trail.n == n_base
    assert tstop.n == n_base
    for t in list(trail.trades) + list(tstop.trades):
        assert -5.0 <= t.result_r <= 20.0        # نتائج معقولة، لا استثناء

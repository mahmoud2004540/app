"""اختبارات المؤشرات الفنية — تعمل offline بدون شبكة."""

import math

from deals_bot import indicators as ind


def test_sma_basic():
    assert ind.sma([1, 2, 3, 4, 5], 5) == 3.0
    assert ind.sma([2, 4, 6], 3) == 4.0
    assert ind.sma([1, 2], 5) is None


def test_ema_series_length_and_seed():
    vals = list(range(1, 21))
    s = ind.ema_series(vals, 5)
    assert len(s) == len(vals)
    # seed is SMA of first 5 = 3.0
    assert math.isclose(s[4], 3.0)
    # EMA of an increasing series keeps rising
    assert s[-1] > s[-2]


def test_rsi_all_gains_is_100():
    vals = list(range(1, 30))          # strictly increasing
    assert ind.rsi(vals, 14) == 100.0


def test_rsi_all_losses_is_zero():
    vals = list(range(30, 1, -1))      # strictly decreasing
    assert ind.rsi(vals, 14) == 0.0


def test_rsi_midrange_for_flat_noise():
    vals = []
    x = 100.0
    for i in range(60):
        x += 1 if i % 2 == 0 else -1
        vals.append(x)
    r = ind.rsi(vals, 14)
    assert r is not None
    assert 30 < r < 70


def test_macd_returns_triple():
    vals = [math.sin(i / 5.0) * 10 + 100 for i in range(100)]
    out = ind.macd(vals)
    assert out is not None
    line, signal, hist = out
    assert math.isclose(hist, line - signal, rel_tol=1e-9)


def test_atr_positive():
    highs = [10 + i * 0.5 for i in range(40)]
    lows = [9 + i * 0.5 for i in range(40)]
    closes = [9.5 + i * 0.5 for i in range(40)]
    a = ind.atr(highs, lows, closes, 14)
    assert a is not None and a > 0


def test_momentum_pct():
    vals = [100.0] * 10 + [110.0]
    m = ind.momentum_pct(vals, 10)
    assert math.isclose(m, 10.0, rel_tol=1e-9)


def test_volume_surge():
    vols = [100.0] * 20 + [300.0]
    vs = ind.volume_surge(vols, 20)
    assert math.isclose(vs, 3.0, rel_tol=1e-9)


def test_mfi_high_when_price_and_money_rise():
    n = 30
    highs = [10 + i * 0.5 + 0.2 for i in range(n)]
    lows = [10 + i * 0.5 - 0.2 for i in range(n)]
    closes = [10 + i * 0.5 for i in range(n)]     # rising
    volumes = [1000.0] * n
    m = ind.mfi(highs, lows, closes, volumes, 14)
    assert m is not None and m > 60


def test_mfi_low_when_price_falls():
    n = 30
    highs = [30 - i * 0.5 + 0.2 for i in range(n)]
    lows = [30 - i * 0.5 - 0.2 for i in range(n)]
    closes = [30 - i * 0.5 for i in range(n)]     # falling
    volumes = [1000.0] * n
    m = ind.mfi(highs, lows, closes, volumes, 14)
    assert m is not None and m < 40


def test_mfi_none_when_no_volume():
    n = 30
    seq = [10 + i * 0.5 for i in range(n)]
    assert ind.mfi(seq, seq, seq, [0.0] * n, 14) is None

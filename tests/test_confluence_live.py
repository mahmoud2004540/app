"""اختبار تفعيل فلتر «تلاقي المؤشرات» في المسار الحيّ (top_picks) — بدون شبكة."""

import config
from deals_bot import strategy
from deals_bot.analyzer import detect_trend_pullback
from deals_bot.models import Candle, Series


def _uptrend_series(symbol="UP-USD", n=400):
    """اتجاه صاعد ثابت مع تنفّس دوري يلمس المتوسّط ثم يرتد (يُفعّل الارتداد)."""
    candles = []
    for i in range(n):
        base = 100 + i * 0.4 + (-3.0 if (i % 20) in (10, 11) else 0.0)
        candles.append(
            Candle(ts=i, open=base, high=max(base, base + 0.5) + 0.8,
                   low=min(base, base + 0.5) - 1.2, close=base + 0.5, volume=1000.0)
        )
    return Series(symbol=symbol, market="crypto", candles=candles)


def _firing_series(symbol="UP-USD"):
    """قُصّ السلسلة عند آخر شمعة يُفعّل عندها detect_trend_pullback (زي الباك-تِست)."""
    full = _uptrend_series(symbol)
    cs = full.candles
    for k in range(len(cs) - 1, 55, -1):
        sub = Series(symbol=symbol, market="crypto", candles=cs[: k + 1])
        if detect_trend_pullback(sub):
            return sub
    raise AssertionError("لم يُفعّل الإعداد في السلسلة التخيلية")


def _patch_env(monkeypatch, stoch_max, require_macd):
    s = _firing_series()
    monkeypatch.setattr(strategy, "resolve_symbols", lambda *a, **k: ["UP-USD"])
    monkeypatch.setattr(strategy, "fetch", lambda *a, **k: s)
    monkeypatch.setattr(strategy, "market_is_bullish", lambda *a, **k: True)
    monkeypatch.setattr(strategy, "_refresh_live_price", lambda d: None)
    monkeypatch.setattr(strategy, "add_position_sizing", lambda *a, **k: None)
    monkeypatch.setattr(config, "TREND_STOCH_MAX", stoch_max)
    monkeypatch.setattr(config, "TREND_REQUIRE_MACD", require_macd)
    # نحيّد فلاتر أخرى قد تمنع الدخول حتى نعزل أثر تلاقي المؤشرات
    monkeypatch.setattr(config, "TREND_REQUIRE_EMA200", False)
    monkeypatch.setattr(config, "MIN_DOLLAR_VOL", 0)
    monkeypatch.setattr(config, "TREND_RSI_MAX", None)
    monkeypatch.setattr(config, "TREND_MIN_SCORE", 0)


def test_stoch_gate_blocks_overbought(monkeypatch):
    """عتبة Stochastic منخفضة جدًا (متشبّع دائمًا) → لا صفقة مؤكّدة."""
    _patch_env(monkeypatch, stoch_max=1.0, require_macd=False)
    picks, cands, _ = strategy.top_picks(["crypto"], timeframe="1h", top=5)
    assert cands, "المفروض في مرشّحين (الإعداد اتفعّل) لكن الفلتر يمنع التأكيد"
    assert picks == []                       # الفلتر منع كل الصفقات


def test_stoch_gate_allows_when_high_threshold(monkeypatch):
    """عتبة Stochastic عالية (100) → الفلتر لا يمنع؛ الصفقة تمرّ."""
    _patch_env(monkeypatch, stoch_max=100.0, require_macd=False)
    picks, cands, _ = strategy.top_picks(["crypto"], timeframe="1h", top=5)
    assert cands
    assert len(picks) >= 1                    # مرّت الصفقة (الفلتر مسموح)
    assert all(getattr(d, "_confluence_ok", True) for d in picks)

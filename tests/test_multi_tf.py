"""اختبارات الفحص متعدّد الفريمات — دمج/إزالة تكرار + بيان الفريم (بدون شبكة)."""

from deals_bot import strategy
from deals_bot import journal
from deals_bot.formatter import _tf_label, format_picks
from deals_bot.models import Deal


def _deal(symbol, conf, tf=None):
    d = Deal(
        symbol=symbol, market="crypto", direction="BUY",
        score=conf, confidence=conf, price=100.0,
        entry=100.0, stop_loss=95.0, take_profit=110.0, risk_reward=2.0,
        reasons=["اتجاه صاعد + ارتداد"],
    )
    d.timeframe = tf
    return d


def test_multi_tf_tags_each_pick_with_its_timeframe(monkeypatch):
    """كل صفقة تُوسَم بالفريم اللي جت منه."""
    canned = {
        "1h": ([_deal("AAA", 90)], [_deal("AAA", 90)], True),
        "6h": ([_deal("BBB", 88)], [_deal("BBB", 88)], True),
        "1d": ([_deal("CCC", 95)], [_deal("CCC", 95)], True),
    }

    def fake_top_picks(markets, timeframe=None, **kw):
        return canned[timeframe]

    monkeypatch.setattr(strategy, "top_picks", fake_top_picks)
    picks, cands, bullish = strategy.top_picks_multi(
        ["crypto"], timeframes=["1h", "6h", "1d"], top=5)
    assert bullish is True
    by = {d.symbol: d.timeframe for d in picks}
    assert by == {"AAA": "1h", "BBB": "6h", "CCC": "1d"}
    # مرتّبة تنازليًا بالثقة: CCC(95) ثم AAA(90) ثم BBB(88)
    assert [d.symbol for d in picks] == ["CCC", "AAA", "BBB"]


def test_multi_tf_dedupes_same_symbol_keeping_higher_confidence(monkeypatch):
    """نفس العملة على فريمين → نبقي الأعلى ثقة فقط."""
    canned = {
        "1h": ([_deal("AAA", 84)], [_deal("AAA", 84)], True),
        "1d": ([_deal("AAA", 92)], [_deal("AAA", 92)], True),
    }
    monkeypatch.setattr(strategy, "top_picks", lambda m, timeframe=None, **k: canned[timeframe])
    picks, _cands, _b = strategy.top_picks_multi(["crypto"], timeframes=["1h", "1d"])
    assert len(picks) == 1
    assert picks[0].symbol == "AAA"
    assert picks[0].confidence == 92
    assert picks[0].timeframe == "1d"


def test_multi_tf_regime_bullish_if_any_frame_bullish(monkeypatch):
    """السوق يُعتبر صاعدًا لو أي فريم صاعد (لا نفوّت صفقة الفريم الأعلى)."""
    canned = {
        "1h": ([], [], False),
        "1d": ([_deal("AAA", 90)], [_deal("AAA", 90)], True),
    }
    monkeypatch.setattr(strategy, "top_picks", lambda m, timeframe=None, **k: canned[timeframe])
    picks, _c, bullish = strategy.top_picks_multi(["crypto"], timeframes=["1h", "1d"])
    assert bullish is True
    assert picks[0].symbol == "AAA"


def test_tf_label_maps_known_frames():
    assert "يومي" in _tf_label("1d")
    assert "ساعة" in _tf_label("1h")
    assert _tf_label("99x") == "إطار 99x"


def test_format_picks_shows_timeframe_line():
    out = format_picks([_deal("AAA", 90, tf="1d")])
    assert "فريم يومي" in out


def test_market_return_map_computes_trailing_return():
    from deals_bot.backtester import market_return_map
    from deals_bot.models import Candle, Series
    cs = [Candle(ts=i * 3600, open=0, high=0, low=0, close=100 * (1.01 ** i), volume=0)
          for i in range(25)]
    m = market_return_map(Series("BTC", "crypto", cs), lookback=20)
    key = round(20 * 3600)
    assert key in m
    assert abs(m[key] - (1.01 ** 20 - 1)) < 1e-9
    # قبل اكتمال النافذة لا قيمة
    assert round(10 * 3600) not in m


def test_pro_filters_do_not_increase_trades(tmp_path):
    """الفلاتر الاحترافية انتقائية: لا تزيد عدد الصفقات أبدًا (تقلّل أو تساوي)."""
    import math
    from deals_bot.backtester import backtest_trend_pullback_series
    from deals_bot.models import Candle, Series
    closes = [100 + 0.6 * i + 2 * math.sin(i / 3.0) for i in range(260)]
    cs = [Candle(ts=i * 3600, open=c, high=c * 1.01, low=c * 0.985, close=c, volume=1000)
          for i, c in enumerate(closes)]
    s = Series("X", "crypto", cs)
    base = backtest_trend_pullback_series(s, min_score=0).n
    for kw in ({"rsi_max": 60.0}, {"min_slope_pct": 0.3},
               {"rsi_max": 65.0, "min_slope_pct": 0.2}):
        assert backtest_trend_pullback_series(s, min_score=0, **kw).n <= base


def test_mae_recorded_and_nonnegative():
    """كل صفقة تُسجَّل بأقصى انعكاس (MAE) ≥ 0؛ والخاسرة تلمس الوقف (MAE ≈ 1R)."""
    from deals_bot.backtester import backtest_trend_pullback_series
    from deals_bot.models import Candle, Series
    # نفس بنّاء السلسلة المُثبت أنه يُفعّل الارتداد (اتجاه صاعد + تنفّس دوري)
    candles = []
    for i in range(400):
        base = 100 + i * 0.4 + (-3.0 if (i % 20) in (10, 11) else 0.0)
        candles.append(Candle(ts=i, open=base, high=max(base, base + 0.5) + 0.8,
                              low=min(base, base + 0.5) - 1.2, close=base + 0.5,
                              volume=1000.0))
    res = backtest_trend_pullback_series(Series("UP", "crypto", candles))
    assert res.n > 0
    for t in res.trades:
        assert t.mae_r >= 0.0                      # الانعكاس لا يكون سالبًا
        if not t.won:
            assert t.mae_r >= 0.99                 # الخاسرة لمست الوقف (~1R)


def test_confluence_filters_do_not_increase_trades():
    """فلاتر تلاقي المؤشرات انتقائية: تقلّل أو تساوي عدد الصفقات، لا تزيده أبدًا."""
    import math
    from deals_bot.backtester import backtest_trend_pullback_series
    from deals_bot.models import Candle, Series
    closes = [100 + 0.6 * i + 2 * math.sin(i / 3.0) for i in range(260)]
    cs = [Candle(ts=i * 3600, open=c, high=c * 1.01, low=c * 0.985, close=c, volume=1000 + i)
          for i, c in enumerate(closes)]
    s = Series("X", "crypto", cs)
    base = backtest_trend_pullback_series(s, min_score=0).n
    for kw in ({"require_macd": True}, {"require_obv": True},
               {"stoch_max": 70.0}, {"mfi_min": 40.0, "mfi_max": 85.0},
               {"require_bb_inside": True},
               {"require_macd": True, "require_obv": True, "stoch_max": 80.0}):
        assert backtest_trend_pullback_series(s, min_score=0, **kw).n <= base


def test_journal_records_per_deal_timeframe(tmp_path):
    """في الدمج: كل صفقة تُسجَّل بفريمها هي، لا فريم واحد للكل."""
    path = str(tmp_path / "trades.jsonl")
    d1 = _deal("AAA", 90, tf="1d")
    d1.opened_ts = 1000.0
    d2 = _deal("BBB", 88, tf="6h")
    d2.opened_ts = 2000.0
    added = journal.record_signals([d1, d2], "1h", now_ts=5000.0, path=path)
    assert added == 2
    trades = {t.symbol: t.timeframe for t in journal.load(path)}
    assert trades == {"AAA": "1d", "BBB": "6h"}

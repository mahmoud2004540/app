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

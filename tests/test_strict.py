"""اختبارات المحلّل المتحفّظ وسجلّه — offline بشموع صناعية."""

from datetime import datetime, timezone

from deals_bot import strict, strict_journal
from deals_bot.models import Candle, Series

H = 3600


def _c(ts, o, h, l, c, v=100.0):
    return Candle(ts=ts, open=o, high=h, low=l, close=c, volume=v)


def _trend(n, start, step, tf_sec=H):
    """سلسلة صاعدة (step>0) أو هابطة (step<0) بسيطة."""
    out, px = [], start
    for i in range(n):
        nxt = px + step
        out.append(_c(i * tf_sec, px, max(px, nxt) + 0.1, min(px, nxt) - 0.1, nxt))
        px = nxt
    return Series("BTC-USD", "crypto", out)


def test_closed_candles_drops_open_bar():
    s = Series("X", "crypto", [_c(0, 1, 1, 1, 1), _c(H, 1, 1, 1, 1)])
    assert len(strict.closed_candles(s, "1h", now_ts=H + 10).candles) == 1
    assert len(strict.closed_candles(s, "1h", now_ts=2 * H).candles) == 2


def test_bullish_engulfing_and_pin_bar():
    eng = [_c(0, 10, 10.2, 9.4, 9.5), _c(H, 9.4, 10.6, 9.3, 10.5)]
    assert strict.candle_pattern(eng, "BUY")[0] == "engulfing"
    assert strict.candle_pattern(eng, "SELL")[0] is None
    pin = [_c(0, 10, 10.1, 9.9, 10), _c(H, 10, 10.1, 9.0, 10.05)]
    assert strict.candle_pattern(pin, "BUY")[0] == "pin"
    bear_pin = [_c(0, 10, 10.1, 9.9, 10), _c(H, 10, 11.0, 9.95, 9.97)]
    assert strict.candle_pattern(bear_pin, "SELL")[0] == "pin"


def test_news_window_and_currency():
    ev = [{"ts": 10_000, "currency": "USD", "title": "CPI m/m", "impact": "High"},
          {"ts": 50_000, "currency": "JPY", "title": "BOJ Rate", "impact": "High"},
          {"ts": 90_000, "currency": "USD", "title": "Retail Sales", "impact": "Medium"}]
    assert strict.blocking_news(ev, ["USD"], 10_000 + 3000, 10_000 + 3500)  # بعد الخبر بأقل من ساعة
    assert strict.blocking_news(ev, ["USD"], 10_000 + 3700, 10_000 + 4000) is None
    assert strict.blocking_news(ev, ["USD"], 50_000, 50_000) is None      # خبر ين مش دولار
    assert strict.blocking_news(ev, ["USD"], 90_000, 90_000) is None      # متوسط بلا كلمة مفتاحية
    assert strict.news_currencies("EURUSD=X", "forex") == ["EUR", "USD"]


def test_weekend_and_session_filters():
    sat = datetime(2026, 10, 24, 12, tzinfo=timezone.utc).timestamp()
    tue_night = datetime(2026, 10, 20, 22, tzinfo=timezone.utc).timestamp()
    assert strict.low_liquidity_time("crypto", sat)
    assert strict.low_liquidity_time("crypto", sat, block_weekend_crypto=False) is None
    assert strict.low_liquidity_time("forex", tue_night)


def test_rejects_buy_against_higher_trend():
    up = _trend(300, 100, 0.5)
    down4 = _trend(300, 300, -0.5, 4 * H)
    setup, why = strict.analyze(up, {"4h": down4}, "1h", now_ts=10**9, news=[],
                                direction="BUY")
    assert setup is None and why[0].startswith("1)")


def test_rejects_without_news_calendar():
    """الأجندة غير متاحة = لا نقدر نتأكّد من الشرط 7 → لا صفقة (حتى لو الباقي تمام)."""
    up = _trend(300, 100, 0.5)
    setup, why = strict.analyze(up, {"4h": _trend(300, 100, 0.5, 4 * H)}, "1h",
                                now_ts=10**9, news=None, direction="BUY")
    assert setup is None


def test_position_size_risk_is_clamped():
    qty, amount = strict.position_size(1000, 0.05, 100, 95)
    assert amount == 20 and qty == 4          # 5% مطلوبة → 2% أقصى
    _, amount = strict.position_size(1000, 0.001, 100, 95)
    assert amount == 10                       # 0.1% → 1% أدنى


# --------------------------- السجل ------------------------------------------ #
def _trade(**kw):
    base = dict(id="x", symbol="BTC-USD", market="crypto", timeframe="1h",
                direction="BUY", entry=100, stop=95, tp1=105, tp2=110, rr=2.0,
                score=85, opened_ts=0)
    base.update(kw)
    return strict_journal.StrictTrade(**base)


def test_step_outcomes():
    t = _trade()
    strict_journal.step(t, 104, 94, 1)              # الوقف قبل TP1
    assert t.status == "loss" and t.result_r == -1.0
    t = _trade()
    strict_journal.step(t, 106, 99, 1)              # TP1 → الوقف للدخول
    assert t.tp1_hit and t.status == "open"
    strict_journal.step(t, 103, 99.5, 2)            # رجع للدخول
    assert t.status == "breakeven" and t.result_r == 0.0
    t = _trade()
    strict_journal.step(t, 111, 99, 1)              # TP2
    assert t.status == "win" and t.result_r == 2.0
    t = _trade()
    strict_journal.step(t, 111, 94, 1)              # الاتنين في شمعة واحدة → ضدّنا
    assert t.status == "loss"
    t = _trade(direction="SELL", entry=100, stop=105, tp1=95, tp2=90)
    strict_journal.step(t, 101, 89, 1)
    assert t.status == "win"


def test_weekly_review_raises_threshold_below_60(tmp_path):
    jp, sp = str(tmp_path / "t.jsonl"), str(tmp_path / "s.json")
    now = datetime(2026, 10, 26, 9, tzinfo=timezone.utc)      # الإثنين
    last_week = datetime(2026, 10, 21, tzinfo=timezone.utc).timestamp()
    trades = [_trade(id="a", status="win", result_r=2.0, closed_ts=last_week),
              _trade(id="b", status="loss", result_r=-1.0, closed_ts=last_week),
              _trade(id="c", status="breakeven", result_r=0.0, closed_ts=last_week)]
    strict_journal.save(trades, jp)
    rep = strict_journal.weekly_review(now, journal_path=jp, state_path=sp)
    assert rep and "33%" in rep
    assert strict_journal.current_min_score(path=sp) == 85
    assert strict_journal.weekly_review(now, journal_path=jp, state_path=sp) is None  # مرة واحدة


def test_weekly_review_back_to_base(tmp_path):
    jp, sp = str(tmp_path / "t.jsonl"), str(tmp_path / "s.json")
    strict_journal.save_state({"min_score": 85, "reviewed_week": "old"}, sp)
    now = datetime(2026, 11, 2, 9, tzinfo=timezone.utc)
    lw = datetime(2026, 10, 28, tzinfo=timezone.utc).timestamp()
    strict_journal.save([_trade(id="a", status="win", result_r=2.0, closed_ts=lw),
                         _trade(id="b", status="win", result_r=2.0, closed_ts=lw)], jp)
    strict_journal.weekly_review(now, journal_path=jp, state_path=sp)
    assert strict_journal.current_min_score(path=sp) == 80


def test_record_dedupes(tmp_path):
    jp = str(tmp_path / "t.jsonl")
    s = strict.StrictSetup("BTC-USD", "crypto", "1h", "BUY", 100, 95, 105, 110, 2.0, 85, 3600)
    assert strict_journal.record(s, 7200, jp) is True
    assert strict_journal.record(s, 7200, jp) is False
    assert strict_journal.has_open("BTC-USD", jp)

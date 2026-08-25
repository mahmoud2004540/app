"""اختبارات تحسينات: قاطع دائرة سلسلة الخسارة + فلتر الارتباط (بدون شبكة)."""

import config
from deals_bot import journal, strategy
from deals_bot.journal import JournalTrade
from deals_bot.models import Candle, Deal, Series


def _jt(symbol, status, closed_ts, r):
    return JournalTrade(
        id=f"1h:{symbol}:{closed_ts}", symbol=symbol, market="crypto",
        timeframe="1h", entry=100.0, stop=95.0, target=110.0, score=90, rr=2.0,
        opened_ts=closed_ts - 100, recorded_ts=closed_ts - 90,
        status=status, exit=95.0 if status == "loss" else 110.0,
        result_r=r, closed_ts=closed_ts,
    )


def test_loss_streak_counts_trailing_losses(tmp_path):
    path = str(tmp_path / "t.jsonl")
    journal.save([
        _jt("A", "win", 1000, 2.0),
        _jt("B", "loss", 2000, -1.0),
        _jt("C", "loss", 3000, -1.0),
        _jt("D", "loss", 4000, -1.0),
    ], path)
    assert journal.loss_streak(path) == 3          # آخر 3 خسائر متتالية


def test_loss_streak_resets_after_a_win(tmp_path):
    path = str(tmp_path / "t.jsonl")
    journal.save([
        _jt("A", "loss", 1000, -1.0),
        _jt("B", "loss", 2000, -1.0),
        _jt("C", "win", 3000, 2.0),        # فوز يكسر السلسلة
        _jt("D", "loss", 4000, -1.0),
    ], path)
    assert journal.loss_streak(path) == 1


def test_streak_note_warns_at_threshold(tmp_path):
    path = str(tmp_path / "t.jsonl")
    journal.save([_jt(s, "loss", ts, -1.0)
                  for s, ts in (("A", 1000), ("B", 2000), ("C", 3000))], path)
    note = journal.streak_note(path, threshold=3)
    assert note and "خسائر متتالية" in note


def test_streak_note_silent_below_threshold(tmp_path):
    path = str(tmp_path / "t.jsonl")
    journal.save([_jt("A", "loss", 1000, -1.0), _jt("B", "loss", 2000, -1.0)], path)
    assert journal.streak_note(path, threshold=3) == ""


# ---------------------------- فلتر الارتباط ---------------------------- #
def _deal(symbol, conf):
    d = Deal(symbol=symbol, market="crypto", direction="BUY",
             score=conf, confidence=conf, price=100.0, entry=100.0,
             stop_loss=95.0, take_profit=110.0, risk_reward=2.0, reasons=["x"])
    d.timeframe = "1h"
    return d


def _series_from(closes):
    cs = [Candle(ts=i, open=c, high=c, low=c, close=c, volume=1.0)
          for i, c in enumerate(closes)]
    return Series("X", "crypto", cs)


def test_diversify_drops_highly_correlated(monkeypatch):
    import math
    monkeypatch.setattr(config, "CORR_FILTER_ENABLED", True)
    monkeypatch.setattr(config, "CORR_MAX", 0.9)
    # موجتان متطابقتان (ارتباط عوائد ~+1) + واحدة معاكسة الطور (ارتباط ~−1)
    same = [100 + 5 * math.sin(i / 3.0) for i in range(60)]
    opp = [100 + 5 * math.sin(i / 3.0 + math.pi) for i in range(60)]
    data = {"AAA": same, "BBB": same, "CCC": opp}
    monkeypatch.setattr(strategy, "fetch",
                        lambda sym, *a, **k: _series_from(data[sym]))
    picks = [_deal("AAA", 95), _deal("BBB", 90), _deal("CCC", 88)]
    out = strategy._diversify(picks)
    syms = [d.symbol for d in out]
    assert "AAA" in syms                 # الأعلى ثقة يبقى
    assert "BBB" not in syms             # المطابق يُسقط
    assert "CCC" in syms                 # المعاكس (تنويع) يبقى


def test_diversify_keeps_all_when_disabled(monkeypatch):
    monkeypatch.setattr(config, "CORR_FILTER_ENABLED", False)
    picks = [_deal("AAA", 95), _deal("BBB", 90)]
    assert len(strategy._diversify(picks)) == 2

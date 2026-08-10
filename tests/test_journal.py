"""اختبارات سجل التداول وحلقة التعلّم — offline، بشموع صناعية بلا شبكة."""

import os

from deals_bot import journal
from deals_bot.models import Candle, Series


class _D:
    """صفقة بسيطة تحاكي Deal لأغراض التسجيل."""
    def __init__(self, symbol, entry, stop, target, opened_ts, score=88.0, rr=2.0):
        self.symbol = symbol
        self.market = "crypto"
        self.entry = entry
        self.stop_loss = stop
        self.take_profit = target
        self.confidence = score
        self.risk_reward = rr
        self.opened_ts = opened_ts
        self.reasons = ["اتجاه صاعد (ارتداد)"]


def _series(symbol, candles):
    return Series(symbol=symbol, market="crypto", candles=candles)


def test_record_dedupes_same_setup(tmp_path):
    path = os.path.join(tmp_path, "trades.jsonl")
    d = _D("BTC-USD", 100.0, 98.0, 104.0, opened_ts=1000)
    assert journal.record_signals([d], "1h", now_ts=1000, path=path) == 1
    # نفس الإعداد (نفس opened_ts) لا يُسجَّل ثانيةً
    assert journal.record_signals([d], "1h", now_ts=2000, path=path) == 0
    assert len(journal.load(path)) == 1


def test_evaluate_marks_win_when_target_hit(tmp_path):
    path = os.path.join(tmp_path, "trades.jsonl")
    d = _D("AAA-USD", 100.0, 98.0, 104.0, opened_ts=1000)
    journal.record_signals([d], "1h", now_ts=1000, path=path)
    # شموع بعد الدخول: ترتفع وتلمس الهدف 104
    candles = [
        Candle(ts=1001, open=100, high=101, low=99.5, close=100.5, volume=1),
        Candle(ts=1002, open=100.5, high=104.5, low=100, close=104.2, volume=1),
    ]
    fetch_fn = lambda s, m, tf, lim: _series("AAA-USD", candles)
    assert journal.evaluate_open(fetch_fn, path=path) == 1
    t = journal.load(path)[0]
    assert t.status == "win"
    assert round(t.result_r, 1) == 2.0        # (104-100)/2


def test_evaluate_marks_loss_when_stop_hit(tmp_path):
    path = os.path.join(tmp_path, "trades.jsonl")
    d = _D("BBB-USD", 100.0, 98.0, 104.0, opened_ts=1000)
    journal.record_signals([d], "1h", now_ts=1000, path=path)
    candles = [Candle(ts=1001, open=100, high=100.5, low=97.5, close=98.0, volume=1)]
    fetch_fn = lambda s, m, tf, lim: _series("BBB-USD", candles)
    assert journal.evaluate_open(fetch_fn, path=path) == 1
    t = journal.load(path)[0]
    assert t.status == "loss"
    assert round(t.result_r, 1) == -1.0


def test_evaluate_ignores_candles_before_entry(tmp_path):
    path = os.path.join(tmp_path, "trades.jsonl")
    d = _D("CCC-USD", 100.0, 98.0, 104.0, opened_ts=1000)
    journal.record_signals([d], "1h", now_ts=1000, path=path)
    # شمعة قبل/عند الدخول تلمس الهدف — يجب تجاهلها
    candles = [Candle(ts=1000, open=100, high=105, low=95, close=100, volume=1)]
    fetch_fn = lambda s, m, tf, lim: _series("CCC-USD", candles)
    assert journal.evaluate_open(fetch_fn, path=path) == 0
    assert journal.load(path)[0].status == "open"


def test_summary_and_learning_note(tmp_path):
    path = os.path.join(tmp_path, "trades.jsonl")
    # سجّل 3 صفقات وأغلقها (2 ربح، 1 خسارة)
    for i, (tp_hit) in enumerate([True, True, False]):
        d = _D(f"C{i}-USD", 100.0, 98.0, 104.0, opened_ts=1000 + i)
        journal.record_signals([d], "1h", now_ts=1000 + i, path=path)
    trades = journal.load(path)
    # اضبط النتائج يدويًا للتحقق من الإحصاء
    trades[0].status, trades[0].result_r = "win", 2.0
    trades[1].status, trades[1].result_r = "win", 2.0
    trades[2].status, trades[2].result_r = "loss", -1.0
    journal.save(trades, path)
    s = journal.summary(path)
    assert s["closed"] == 3 and s["wins"] == 2
    assert round(s["total_r"], 1) == 3.0
    assert round(s["win_rate"]) == 67
    # عيّنة صغيرة → ملاحظة تشير لذلك
    assert "العيّنة صغيرة" in journal.learning_note(path)

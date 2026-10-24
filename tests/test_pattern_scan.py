"""اختبارات حجم الصفقة وسجل النماذج — offline."""

from deals_bot import pattern_scan as ps
from deals_bot.models import Candle

H4 = 14400


def test_position_size_risks_exact_percent():
    s = ps.position_size(1000, 0.02, entry=100, stop=90)
    assert abs(s["risk"] - 20) < 1e-9 and abs(s["qty"] - 2) < 1e-9 and abs(s["value"] - 200) < 1e-9


def test_position_size_never_uses_leverage():
    s = ps.position_size(1000, 0.02, entry=100, stop=99.9)   # وقف قريب جدًا → المركز أكبر من رأس المال
    assert abs(s["value"] - 1000) < 1e-9 and s["risk_pct"] < 2


def _setup(sym="SOL-USD", ts=0.0):
    return {"symbol": sym, "timeframe": "4h", "pattern": "Bull flag", "entry": 100.0, "stop": 90.0,
            "target": 120.0, "breakout_ts": ts}


def test_record_new_dedupes(tmp_path):
    path = str(tmp_path / "t.jsonl")
    assert len(ps.record_new([_setup()], now=H4, path=path)) == 1
    assert ps.record_new([_setup()], now=2 * H4, path=path) == []
    assert ps.stats(path)["open"] == 1


def test_evaluate_win_and_loss(tmp_path):
    path = str(tmp_path / "t.jsonl")
    ps.record_new([_setup("WIN-USD"), _setup("LOSS-USD")], now=H4, path=path)
    bars = {"WIN-USD": [Candle(H4, 100, 110, 95, 108, 1), Candle(2 * H4, 108, 121, 104, 119, 1)],
            "LOSS-USD": [Candle(H4, 100, 104, 89, 92, 1)]}
    assert ps.evaluate_open(lambda s, tf: bars[s], now=10 * H4, path=path) == 2
    st = ps.stats(path)
    assert st["closed"] == 2 and st["wins"] == 1 and st["total_r"] == 1.0   # +2R −1R


def test_open_candle_not_evaluated(tmp_path):
    path = str(tmp_path / "t.jsonl")
    ps.record_new([_setup()], now=H4, path=path)
    bars = [Candle(H4, 100, 125, 99, 124, 1)]                 # لسه مفتوحة
    assert ps.evaluate_open(lambda s, tf: bars, now=H4 + 60, path=path) == 0

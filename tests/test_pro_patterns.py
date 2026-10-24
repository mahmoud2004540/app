"""اختبارات النماذج الاحترافية — offline بشموع صناعية."""

from deals_bot import pro_patterns as pp
from deals_bot.models import Candle

H4 = 14400


def _bar(i, o, c, wick=0.3):
    return Candle(ts=i * H4, open=o, high=max(o, c) + wick, low=min(o, c) - wick, close=c, volume=100.0)


def _flag_series():
    """قاعدة هادية ثم عمود صاعد حاد ثم تصحيح صغير ثم كسر قمة العمود."""
    bars, px = [], 100.0
    for i in range(240):                       # تذبذب صغير حوالين 100
        nxt = 100.0 + (0.4 if i % 2 else -0.4)
        bars.append(_bar(i, px, nxt)); px = nxt
    for _ in range(10):                        # العمود: +3 كل شمعة
        bars.append(_bar(len(bars), px, px + 3)); px += 3
    for _ in range(6):                         # التصحيح: −1.5 كل شمعة
        bars.append(_bar(len(bars), px, px - 1.5)); px -= 1.5
    for _ in range(4):                         # رجوع لحد قبل القمة
        bars.append(_bar(len(bars), px, px + 2)); px += 2
    bars.append(_bar(len(bars), px, px + 3))   # إغلاق فوق قمة العمود
    return bars


def test_zigzag_is_causal():
    bars = _flag_series()
    h = [b.high for b in bars]; l = [b.low for b in bars]; c = [b.close for b in bars]
    for kind, idx, price, conf in pp.zigzag(h, l, pp.atr(h, l, c)):
        assert conf >= idx                     # الارتكاز بيتأكد بعد ما يحصل (أو مع قفل نفس الشمعة)، مش قبله


def test_bull_flag_breakout_detected():
    bars = _flag_series()
    now = bars[-1].ts + H4 + 1
    found = pp.recent_setups(bars, "4h", now)
    assert [d["pattern"] for d in found] == ["Bull flag"]
    d = found[0]
    assert d["bars_ago"] == 0 and d["stop"] < d["entry"] < d["target"]


def test_open_candle_is_ignored():
    bars = _flag_series()
    now = bars[-1].ts + 60                     # شمعة الكسر لسه مفتوحة
    assert all(d["bars_ago"] != 0 for d in pp.recent_setups(bars, "4h", now))


def test_no_signal_on_flat_market():
    bars = [_bar(i, 100.0, 100.0 + (0.4 if i % 2 else -0.4)) for i in range(300)]
    assert pp.recent_setups(bars, "4h", bars[-1].ts + H4 + 1) == []


def test_market_bullish():
    up = [_bar(i, 100 + i, 101 + i) for i in range(250)]
    down = [_bar(i, 400 - i, 399 - i) for i in range(250)]
    assert pp.market_bullish(up) is True
    assert pp.market_bullish(down) is False
    assert pp.market_bullish(up[:50]) is None


def test_format_setup_mentions_stop_and_target():
    d = {"symbol": "SOL-USD", "timeframe": "4h", "pattern": "Bull flag", "entry": 150.0, "stop": 140.0,
         "target": 175.0, "rr": 2.5, "risk_pct": 6.7, "target_pct": 16.7, "bars_ago": 0}
    msg = pp.format_setup(d)
    assert "SOLUSDT" in msg and "العلم الصاعد" in msg and "140" in msg and "175" in msg

"""فلتر منع الدخول وسط انعكاس جارٍ — بدون شبكة."""

from deals_bot.confirmation import last_bar_holds
from deals_bot.models import Candle, Series


def _series(bars):
    candles = [
        Candle(ts=i, open=o, high=h, low=l, close=c, volume=100.0)
        for i, (o, h, l, c) in enumerate(bars)
    ]
    return Series("X", "crypto", candles)


def test_buy_holds_on_bullish_higher_close():
    s = _series([
        (10, 11, 9.5, 10.2),
        (10.2, 11.5, 10.1, 11.0),
    ])
    assert last_bar_holds(s, "BUY") is True


def test_buy_rejects_bearish_bar():
    s = _series([
        (10, 11, 9.5, 10.8),
        (10.8, 10.9, 9.8, 10.0),
    ])
    assert last_bar_holds(s, "BUY") is False


def test_buy_rejects_weaker_close():
    s = _series([
        (10, 11, 9.5, 10.8),
        (10.4, 10.7, 10.3, 10.6),
    ])
    assert last_bar_holds(s, "BUY") is False


def test_sell_holds_on_bearish_lower_close():
    s = _series([
        (11, 11.2, 10.5, 10.8),
        (10.8, 10.9, 10.0, 10.1),
    ])
    assert last_bar_holds(s, "SELL") is True

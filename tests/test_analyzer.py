"""اختبارات محرّك التقييم باستخدام سلاسل اصطناعية — بدون شبكة."""

import math

from deals_bot.analyzer import analyze_symbol, rank_deals
from deals_bot.models import Candle, Series


def _series_from_closes(symbol, closes, market="crypto", vol=1000.0):
    candles = []
    ts = 0.0
    for c in closes:
        candles.append(
            Candle(ts=ts, open=c, high=c * 1.01, low=c * 0.99, close=c, volume=vol)
        )
        ts += 3600
    return Series(symbol=symbol, market=market, candles=candles)


def _trend(start, slope, n, wiggle=0.0):
    """اتجاه خطي مع تذبذب خفيف — يحاكي السوق الحقيقي (RSI ليس 0/100)."""
    out = []
    for i in range(n):
        out.append(start + slope * i + wiggle * math.sin(i / 3.0))
    return out


def test_insufficient_data_is_neutral_with_error():
    s = _series_from_closes("X", [100.0] * 10)
    d = analyze_symbol(s)
    assert d.direction == "NEUTRAL"
    assert d.error is not None


def test_strong_uptrend_is_buy():
    closes = _trend(100.0, 0.6, 120, wiggle=1.0)          # steady climb
    s = _series_from_closes("UP", closes)
    d = analyze_symbol(s)
    assert d.direction == "BUY"
    assert d.score > 0
    assert d.take_profit > d.entry > d.stop_loss
    assert d.risk_reward > 0


def test_strong_downtrend_is_sell():
    closes = _trend(200.0, -0.4, 120, wiggle=3.0)          # steady decline
    s = _series_from_closes("DOWN", closes)
    d = analyze_symbol(s)
    assert d.direction == "SELL"
    assert d.score < 0
    assert d.take_profit < d.entry < d.stop_loss


def test_rank_orders_by_confidence_and_respects_top():
    up = _series_from_closes("UP", _trend(100.0, 0.6, 120, wiggle=1.0))
    down = _series_from_closes("DOWN", _trend(200.0, -0.6, 120, wiggle=1.0))
    flat = _series_from_closes(
        "FLAT", [100.0 + (1 if i % 2 else -1) for i in range(120)]
    )
    deals = rank_deals([up, down, flat], top=2, direction="any")
    assert len(deals) <= 2
    # sorted by confidence descending
    for a, b in zip(deals, deals[1:]):
        assert a.confidence >= b.confidence


def test_direction_filter_buy_only():
    up = _series_from_closes("UP", _trend(100.0, 0.6, 120, wiggle=1.0))
    down = _series_from_closes("DOWN", _trend(200.0, -0.6, 120, wiggle=1.0))
    deals = rank_deals([up, down], top=5, direction="buy")
    assert all(d.direction == "BUY" for d in deals)


def test_risk_reward_ratio_matches_atr_multiples():
    closes = _trend(100.0, 0.6, 120, wiggle=1.0)
    d = analyze_symbol(_series_from_closes("UP", closes))
    # TARGET/STOP multiples are 2.5 / 1.5 => R:R ~ 1.67
    assert math.isclose(d.risk_reward, 2.5 / 1.5, rel_tol=0.05)

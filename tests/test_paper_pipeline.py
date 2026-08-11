"""اختبارات التنفيذ الورقي + خط القرار + تأكيد 15M (offline)."""

import math

from deals_bot import paper_trading as pt
from deals_bot.confirmation import bearish_engulfing, bullish_engulfing, confirm, volume_expansion
from deals_bot.models import Candle, Series
from deals_bot.pipeline import APPROVED, NO_TRADE, evaluate
from deals_bot.risk_engine import DailyState


# --------------------------- Paper Trading --------------------------- #
def test_paper_win_increases_equity_and_reports_r():
    acc = pt.PaperAccount(equity=1000.0, starting_equity=1000.0)
    pos = pt.open_position(acc, "BTC-USD", "crypto", "BUY", entry=100.0, stop=98.0,
                           target=104.0, qty=2.5, opened_ts=1, fee_rate=0.0, slippage_rate=0.0)
    trade = pt.close_position(acc, pos, exit_price=104.0, reason="target", closed_ts=2,
                              fee_rate=0.0, slippage_rate=0.0)
    assert trade.reason == "target"
    assert math.isclose(trade.pnl, 10.0, rel_tol=1e-9)      # (104-100)*2.5
    assert math.isclose(trade.result_r, 2.0, rel_tol=1e-9)  # هدف عند 2R
    assert acc.equity > 1000.0


def test_paper_loss_decreases_equity():
    acc = pt.PaperAccount(equity=1000.0, starting_equity=1000.0)
    pos = pt.open_position(acc, "X-USD", "crypto", "BUY", 100.0, 98.0, 104.0, 2.5, 1,
                           fee_rate=0.0, slippage_rate=0.0)
    trade = pt.close_position(acc, pos, 98.0, "stop", 2, fee_rate=0.0, slippage_rate=0.0)
    assert math.isclose(trade.result_r, -1.0, rel_tol=1e-9)
    assert acc.equity < 1000.0


def test_fees_and_slippage_cost_money():
    acc = pt.PaperAccount(equity=1000.0, starting_equity=1000.0)
    pos = pt.open_position(acc, "X-USD", "crypto", "BUY", 100.0, 98.0, 104.0, 2.5, 1,
                           fee_rate=0.001, slippage_rate=0.0005)
    # الدخول الفعلي أعلى من 100 بسبب الانزلاق، ودُفعت رسوم دخول
    assert pos.entry > 100.0 and pos.fees_paid > 0.0


def test_check_exit_stop_first_when_both_touched():
    pos = pt.PaperPosition("X", "crypto", "BUY", 100.0, 98.0, 104.0, 1.0, 1)
    # شمعة تلمس الوقف والهدف معًا → نفترض الوقف (الأسوأ)
    out = pt.check_exit(pos, high=105.0, low=97.0)
    assert out == (98.0, "stop")


# --------------------------- Confirmation --------------------------- #
def _c(o, h, l, cl, v=100.0, ts=0):
    return Candle(ts=ts, open=o, high=h, low=l, close=cl, volume=v)


def test_bullish_engulfing_detected():
    s = Series("X", "crypto", [_c(10, 10.2, 9.5, 9.6), _c(9.5, 10.6, 9.4, 10.5)])
    assert bullish_engulfing(s) is True
    assert bearish_engulfing(s) is False


def test_volume_expansion():
    candles = [_c(10, 10.1, 9.9, 10.0, v=100.0) for _ in range(20)]
    candles.append(_c(10, 10.5, 10, 10.4, v=200.0))
    assert volume_expansion(Series("X", "crypto", candles), mult=1.3) is True


# --------------------------- Pipeline --------------------------- #
def _uptrend_pullback(n=412):
    out = []
    for i in range(n):
        base = 100 + i * 0.4 + (-3.0 if (i % 20) in (10, 11) else 0.0)
        out.append(Candle(ts=i, open=base, high=max(base, base + 0.5) + 0.8,
                          low=min(base, base + 0.5) - 1.2, close=base + 0.5, volume=1000.0))
    return out


def test_pipeline_blocks_when_daily_limit_hit():
    base = Series("UP", "crypto", _uptrend_pullback())
    daily = DailyState(starting_equity=1000.0, current_equity=980.0)  # -2% > 1.5%
    dec = evaluate(base, equity=1000.0, daily=daily)
    assert dec.status == NO_TRADE
    assert "الخسارة اليومية" in " ".join(dec.reasons)


def test_pipeline_no_trade_on_downtrend():
    closes = [Candle(ts=i, open=300 - i, high=300 - i + 0.5, low=300 - i - 0.5,
                     close=300 - i, volume=100.0) for i in range(200)]
    dec = evaluate(Series("DOWN", "crypto", closes), equity=1000.0,
                   daily=DailyState(1000.0, 1000.0))
    assert dec.status == NO_TRADE


def test_pipeline_runs_full_chain_without_crash():
    base = Series("UP", "crypto", _uptrend_pullback())
    dec = evaluate(base, equity=1000.0, daily=DailyState(1000.0, 1000.0))
    # يمرّ بالسلسلة ويُنتج قرارًا صالحًا
    assert dec.status in (APPROVED, "WAIT", NO_TRADE, "REJECTED")
    assert dec.reasons

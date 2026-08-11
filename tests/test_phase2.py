"""اختبارات PHASE 2: Walk-Forward + حلقة البوت الورقية (offline)."""

from deals_bot import paper_trading as pt
from deals_bot.bot_loop import run_cycle
from deals_bot.models import Candle, Series
from deals_bot.risk_engine import RiskConfig, RiskEngine
from deals_bot.walkforward import summarize, walk_forward


def _uptrend(n=600):
    out = []
    for i in range(n):
        base = 100 + i * 0.4 + (-3.0 if (i % 20) in (10, 11) else 0.0)
        out.append(Candle(ts=i, open=base, high=max(base, base + 0.5) + 0.8,
                          low=min(base, base + 0.5) - 1.2, close=base + 0.5, volume=1000.0))
    return out


# ----------------------------- Walk-Forward ----------------------------- #
def test_walk_forward_produces_folds_and_summary():
    series = [Series("A-USD", "crypto", _uptrend()), Series("B-USD", "crypto", _uptrend())]
    results = walk_forward(series, folds=3, thresholds=(80.0, 85.0), require_ema200=False)
    assert len(results) == 3
    for r in results:
        assert r.train_best_score in (80.0, 85.0)
        assert r.test_trades >= 0
    s = summarize(results)
    assert s["folds"] == 3 and "oos_expectancy" in s


def test_walk_forward_empty_on_no_data():
    assert walk_forward([], folds=3) == []


# ----------------------------- Bot Loop ----------------------------- #
def _engine():
    return RiskEngine(RiskConfig(risk_per_trade=0.005, max_open_positions=5,
                                 fee_rate=0.0, slippage_rate=0.0, min_rr=2.0))


def test_run_cycle_closes_position_on_target_hit():
    acc = pt.PaperAccount(equity=1000.0, starting_equity=1000.0)
    pos = pt.open_position(acc, "X-USD", "crypto", "BUY", 100.0, 98.0, 104.0, 2.5, 1,
                           fee_rate=0.0, slippage_rate=0.0)
    # آخر شمعة تلمس الهدف
    hit = Series("X-USD", "crypto", [Candle(ts=5, open=103, high=104.5, low=102, close=104, volume=1)])
    events = run_cycle(acc, [], lambda s, m, tf, l: hit, now_ts=86400 * 2,
                       engine=_engine(), fee_rate=0.0, slippage_rate=0.0)
    assert any(e.kind == "close" and e.symbol == "X-USD" for e in events)
    assert len(acc.positions) == 0 and len(acc.closed) == 1


def test_run_cycle_respects_daily_stop_after_three_losses():
    acc = pt.PaperAccount(equity=1000.0, starting_equity=1000.0, day_start_equity=1000.0)
    # 3 خسائر متتالية في السجل
    for i in range(3):
        acc.closed.append(pt.ClosedTrade("L", "BUY", 100, 98, 1, -2.0, 0.0, -1.0, "stop", i, i + 1))
    base = Series("UP-USD", "crypto", _uptrend())
    events = run_cycle(acc, ["UP-USD"], lambda s, m, tf, l: base, now_ts=86400 * 2,
                       engine=_engine())
    # لا يفتح أي صفقة رغم وجود مرشّح (البوت موقوف بعد 3 خسائر)
    assert not any(e.kind == "open" for e in events)


def test_run_cycle_no_crash_with_real_shaped_inputs():
    acc = pt.PaperAccount(equity=1000.0, starting_equity=1000.0, day_start_equity=1000.0)
    base = Series("UP-USD", "crypto", _uptrend())
    events = run_cycle(acc, ["UP-USD"], lambda s, m, tf, l: base, now_ts=86400 * 2,
                       engine=_engine(), fetch_confirm=lambda s, m, tf, l: base)
    assert isinstance(events, list)

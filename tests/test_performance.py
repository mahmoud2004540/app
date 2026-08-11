"""اختبارات تحليل الأداء (Dashboard metrics) — offline."""

import math

from deals_bot import paper_trading as pt
from deals_bot.performance import compute, equity_curve, max_drawdown


def test_max_drawdown_basic():
    # قمة 120 ثم قاع 90 → تراجع 25%
    assert max_drawdown([100, 120, 90, 110]) == 25.0
    assert max_drawdown([100, 101, 102]) == 0.0
    assert max_drawdown([]) == 0.0


def test_equity_curve_accumulates():
    assert equity_curve(1000.0, [10.0, -5.0, 20.0]) == [1000.0, 1010.0, 1005.0, 1025.0]


def _closed(pnl, r):
    return pt.ClosedTrade("X", "BUY", 100, 100 + pnl, 1, pnl, 0.0, r, "target" if pnl > 0 else "stop", 0, 1)


def test_compute_full_metrics():
    acc = pt.PaperAccount(equity=1015.0, starting_equity=1000.0)
    acc.closed = [_closed(20, 2.0), _closed(-10, -1.0), _closed(20, 2.0), _closed(-15, -1.0)]
    m = compute(acc)
    assert m["closed"] == 4 and m["wins"] == 2 and m["losses"] == 2
    assert m["win_rate"] == 50.0
    # عامل الربح = 40 / 25 = 1.6
    assert math.isclose(m["profit_factor"], 1.6, rel_tol=1e-9)
    assert math.isclose(m["net_pnl"], 15.0, rel_tol=1e-9)
    assert m["longest_win_streak"] >= 1 and m["longest_loss_streak"] >= 1
    assert m["max_drawdown_pct"] >= 0.0


def test_compute_empty_account_is_safe():
    acc = pt.PaperAccount(equity=1000.0, starting_equity=1000.0)
    m = compute(acc)
    assert m["closed"] == 0 and m["win_rate"] == 0.0 and m["profit_factor"] == 0.0
    assert m["max_drawdown_pct"] == 0.0

"""
تحليل الأداء (Performance Analytics) — PHASE 3.

Turns the paper account + trade journal into the metrics a trading dashboard
needs: equity, return %, win rate, profit factor, expectancy in R, average
win/loss, max drawdown (from the realized equity curve), and streaks. Pure and
offline-testable — takes the account object, computes numbers, no I/O.
"""

from __future__ import annotations

from typing import List


def max_drawdown(equity_curve: List[float]) -> float:
    """أقصى تراجع نسبي (٪) من قمة إلى قاع على منحنى رأس المال."""
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    worst = 0.0
    for v in equity_curve:
        peak = max(peak, v)
        if peak > 0:
            worst = max(worst, (peak - v) / peak)
    return round(worst * 100.0, 2)


def equity_curve(starting_equity: float, closed_pnls: List[float]) -> List[float]:
    """ابنِ منحنى رأس المال المُحقَّق من الأرباح/الخسائر المتتالية."""
    curve = [starting_equity]
    eq = starting_equity
    for pnl in closed_pnls:
        eq += pnl
        curve.append(eq)
    return curve


def _streaks(wins_losses: List[bool]) -> tuple:
    """أطول سلسلة أرباح وأطول سلسلة خسائر."""
    best_w = best_l = cur_w = cur_l = 0
    for won in wins_losses:
        if won:
            cur_w += 1
            cur_l = 0
        else:
            cur_l += 1
            cur_w = 0
        best_w = max(best_w, cur_w)
        best_l = max(best_l, cur_l)
    return best_w, best_l


def compute(account) -> dict:
    """احسب كل مقاييس الأداء من حساب التداول الورقي."""
    closed = account.closed
    n = len(closed)
    pnls = [t.pnl for t in closed]
    rs = [t.result_r for t in closed]
    wins = [t for t in closed if t.pnl > 0]
    losses = [t for t in closed if t.pnl < 0]
    gross_win = sum(t.pnl for t in wins)
    gross_loss = -sum(t.pnl for t in losses)
    curve = equity_curve(account.starting_equity, pnls)
    best_w, best_l = _streaks([t.pnl > 0 for t in closed])

    return {
        "equity": round(account.equity, 2),
        "starting_equity": round(account.starting_equity, 2),
        "return_pct": round((account.equity / account.starting_equity - 1.0) * 100.0, 2)
        if account.starting_equity else 0.0,
        "open_positions": len(account.positions),
        "closed": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / n * 100.0, 1) if n else 0.0,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else (
            float("inf") if gross_win > 0 else 0.0
        ),
        "expectancy_r": round(sum(rs) / n, 3) if n else 0.0,
        "net_pnl": round(sum(pnls), 2),
        "total_r": round(sum(rs), 2),
        "avg_win": round(gross_win / len(wins), 2) if wins else 0.0,
        "avg_loss": round(-gross_loss / len(losses), 2) if losses else 0.0,
        "max_drawdown_pct": max_drawdown(curve),
        "longest_win_streak": best_w,
        "longest_loss_streak": best_l,
        "equity_curve": [round(v, 2) for v in curve],
    }

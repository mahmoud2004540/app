"""
اختبار المشي الأمامي (Walk-Forward Testing) — PHASE 2.

Proper out-of-sample validation: split history into sequential folds. In each
fold, "train" on an in-sample window (pick the score threshold that maximises
expectancy there), then measure that chosen threshold on the FOLLOWING, unseen
window. Aggregating the test-window results across folds gives an honest
out-of-sample expectancy — the real test of whether the edge generalises or was
curve-fit to one period.

No look-ahead: every entry decision uses only candles up to its own bar, and the
test window is strictly after the train window it was tuned on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .backtester import backtest_trend_pullback_series
from .models import Series


@dataclass
class FoldResult:
    fold: int
    train_best_score: float
    train_expectancy: float
    test_expectancy: float
    test_trades: int
    test_total_r: float


def _aggregate(series_list: List[Series], min_score: float,
               t0: float, t1: float, require_ema200: bool) -> Tuple[float, int, float]:
    """توقّع/عدد/إجمالي R عبر كل الرموز لصفقات تُفتح داخل [t0, t1)."""
    tt = 0
    tr = 0.0
    for s in series_list:
        res = backtest_trend_pullback_series(
            s, min_score=min_score, require_ema200=require_ema200,
            entry_min_ts=t0, entry_max_ts=t1,
        )
        tt += res.n
        tr += res.total_r
    exp = (tr / tt) if tt else 0.0
    return exp, tt, tr


def walk_forward(
    series_list: List[Series],
    folds: int = 4,
    thresholds: Tuple[float, ...] = (80.0, 85.0, 90.0),
    require_ema200: bool = True,
    ts_lo: Optional[float] = None,
    ts_hi: Optional[float] = None,
) -> List[FoldResult]:
    """
    شغّل المشي الأمامي عبر عدة طيّات، مُرجعًا نتيجة كل طيّة (خارج العيّنة).

    ts_lo/ts_hi: المدى الزمني الكلي؛ إن لم يُمرَّر يُستنتج من الرموز.
    """
    # استنتج المدى الزمني الكلي من كل الشموع
    all_ts = [c.ts for s in series_list for c in s.candles]
    if not all_ts:
        return []
    lo = ts_lo if ts_lo is not None else min(all_ts)
    hi = ts_hi if ts_hi is not None else max(all_ts)
    if hi <= lo:
        return []

    # قسّم المدى إلى (folds + 1) شرائح: كل طيّة = تدريب على شريحة، اختبار على التالية
    n_slices = folds + 1
    edges = [lo + (hi - lo) * k / n_slices for k in range(n_slices + 1)]

    results: List[FoldResult] = []
    for k in range(folds):
        train_t0, train_t1 = edges[k], edges[k + 1]
        test_t0, test_t1 = edges[k + 1], edges[k + 2]

        # تدريب: اختر العتبة التي تعظّم التوقّع داخل نافذة التدريب
        best_score, best_exp = thresholds[0], float("-inf")
        for th in thresholds:
            exp, n, _ = _aggregate(series_list, th, train_t0, train_t1, require_ema200)
            if n >= 5 and exp > best_exp:
                best_exp, best_score = exp, th
        if best_exp == float("-inf"):
            best_exp = 0.0

        # اختبار خارج العيّنة بالعتبة المختارة
        test_exp, test_n, test_tr = _aggregate(
            series_list, best_score, test_t0, test_t1, require_ema200
        )
        results.append(FoldResult(
            fold=k + 1, train_best_score=best_score,
            train_expectancy=round(best_exp, 3),
            test_expectancy=round(test_exp, 3), test_trades=test_n,
            test_total_r=round(test_tr, 1),
        ))
    return results


def summarize(results: List[FoldResult]) -> dict:
    """لخّص الأداء خارج العيّنة عبر كل الطيّات."""
    tt = sum(r.test_trades for r in results)
    tr = sum(r.test_total_r for r in results)
    return {
        "folds": len(results),
        "oos_trades": tt,
        "oos_total_r": round(tr, 1),
        "oos_expectancy": round(tr / tt, 3) if tt else 0.0,
    }

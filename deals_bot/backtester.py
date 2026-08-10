"""
باك-تِست: يقيس أداء الاستراتيجية على بيانات تاريخية بالأرقام.

Event-driven backtest. Walks the candle series forward, and whenever the
analyzer produces an actionable signal (and no trade is open), it opens a trade
at that bar's close using the analyzer's stop-loss / take-profit. It then checks
following bars: whichever level is touched first closes the trade.

Outputs honest performance numbers: number of trades, win rate, average win/loss
in R multiples, profit factor, and expectancy. There is no guaranteed-profit
strategy — this exists to set realistic expectations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .analyzer import (
    analyze_symbol,
    detect_accumulation,
    detect_early_pump,
    detect_pre_pump,
)
from .models import Series


@dataclass
class Trade:
    symbol: str
    direction: str
    entry: float
    stop: float
    target: float
    exit_price: float
    result_r: float          # نتيجة الصفقة بمضاعفات المخاطرة (R)
    won: bool


@dataclass
class BacktestResult:
    symbol: str
    trades: List[Trade]

    @property
    def n(self) -> int:
        return len(self.trades)

    @property
    def wins(self) -> int:
        return sum(1 for t in self.trades if t.won)

    @property
    def win_rate(self) -> float:
        return (self.wins / self.n * 100.0) if self.n else 0.0

    @property
    def total_r(self) -> float:
        return sum(t.result_r for t in self.trades)

    @property
    def avg_win_r(self) -> float:
        w = [t.result_r for t in self.trades if t.won]
        return sum(w) / len(w) if w else 0.0

    @property
    def avg_loss_r(self) -> float:
        losses = [t.result_r for t in self.trades if not t.won]
        return sum(losses) / len(losses) if losses else 0.0

    @property
    def profit_factor(self) -> float:
        gross_win = sum(t.result_r for t in self.trades if t.result_r > 0)
        gross_loss = -sum(t.result_r for t in self.trades if t.result_r < 0)
        if gross_loss == 0:
            return float("inf") if gross_win > 0 else 0.0
        return gross_win / gross_loss

    @property
    def expectancy_r(self) -> float:
        """متوسط العائد المتوقّع لكل صفقة بمضاعفات R."""
        return (self.total_r / self.n) if self.n else 0.0


def backtest_series(series: Series, warmup: int = 60) -> BacktestResult:
    """شغّل الباك-تِست على سلسلة رمز واحد."""
    candles = series.candles
    trades: List[Trade] = []
    i = warmup
    n = len(candles)

    while i < n - 1:
        sub = Series(symbol=series.symbol, market=series.market, candles=candles[: i + 1])
        deal = analyze_symbol(sub)
        if not deal.is_actionable() or deal.stop_loss == deal.entry:
            i += 1
            continue

        entry = deal.entry
        stop = deal.stop_loss
        target = deal.take_profit
        risk = abs(entry - stop)
        if risk <= 0:
            i += 1
            continue

        # تتبّع الصفقة على الشموع التالية
        outcome = None
        j = i + 1
        while j < n:
            hi = candles[j].high
            lo = candles[j].low
            if deal.direction == "BUY":
                hit_stop = lo <= stop
                hit_target = hi >= target
            else:  # SELL
                hit_stop = hi >= stop
                hit_target = lo <= target
            # في حال لمست الشمعة الحدّين، نفترض الأسوأ (وقف الخسارة أولًا)
            if hit_stop:
                outcome = (stop, False)
                break
            if hit_target:
                outcome = (target, True)
                break
            j += 1

        if outcome is None:
            # لم تُغلق حتى نهاية البيانات — نغلق على آخر سعر
            last = candles[-1].close
            r = (last - entry) / risk if deal.direction == "BUY" else (entry - last) / risk
            trades.append(
                Trade(series.symbol, deal.direction, entry, stop, target, last, r, r > 0)
            )
            break

        exit_price, won = outcome
        r = (exit_price - entry) / risk if deal.direction == "BUY" else (entry - exit_price) / risk
        trades.append(
            Trade(series.symbol, deal.direction, entry, stop, target, exit_price, r, won)
        )
        # استأنف التحليل بعد إغلاق الصفقة
        i = j + 1

    return BacktestResult(symbol=series.symbol, trades=trades)


def _prepump_levels(setup: dict, kind: str):
    """احسب الدخول/الوقف/الهدف لإعداد قبل الاندفاع (نفس منطق بناة الصفقات)."""
    price = setup["price"]
    base_high = setup.get("base_high", price)
    base_low = setup.get("base_low", price)
    width = max(base_high - base_low, price * 0.001)
    if kind == "early":
        stop = min(base_high * 0.985, price * 0.97)
        target = max(base_high + 1.5 * width, price * 1.10)
    else:  # accumulation / squeeze
        stop = base_low * 0.98
        target = max(base_high + 2.0 * width, price * 1.12)
    return price, stop, target


def backtest_prepump_series(series: Series, warmup: int = 80) -> BacktestResult:
    """
    باك-تِست مخصّص لإشارات «ما قبل الاندفاع» (بداية اندفاع / تجميع / انضغاط).

    Measures whether the pre-pump detectors actually precede up-moves: at each
    bar, if a setup fires, open a long at that price with the same stop/target
    the bot would use, then check forward bars for the outcome.
    """
    candles = series.candles
    trades: List[Trade] = []
    i = warmup
    n = len(candles)

    while i < n - 1:
        sub = Series(symbol=series.symbol, market=series.market, candles=candles[: i + 1])
        setup = detect_early_pump(sub)
        kind = "early"
        if not setup:
            setup = detect_accumulation(sub) or detect_pre_pump(sub)
            kind = "base"
        if not setup:
            i += 1
            continue

        entry, stop, target = _prepump_levels(setup, kind)
        risk = abs(entry - stop)
        if risk <= 0:
            i += 1
            continue

        outcome = None
        j = i + 1
        while j < n:
            hi, lo = candles[j].high, candles[j].low
            if lo <= stop:          # long: الوقف أولًا في الأسوأ
                outcome = (stop, False)
                break
            if hi >= target:
                outcome = (target, True)
                break
            j += 1

        if outcome is None:
            i += 1
            continue
        exit_price, won = outcome
        r = (exit_price - entry) / risk
        trades.append(
            Trade(series.symbol, "BUY", entry, stop, target, exit_price, r, won)
        )
        i = j + 1

    return BacktestResult(symbol=series.symbol, trades=trades)

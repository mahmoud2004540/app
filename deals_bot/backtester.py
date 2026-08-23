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

from typing import Optional

from . import indicators as ind
from .analyzer import (
    analyze_symbol,
    detect_accumulation,
    detect_breakout,
    detect_early_pump,
    detect_pre_pump,
    detect_trend_pullback,
)
from .models import Series


def market_uptrend_map(btc: Series, period: int = 50) -> dict:
    """
    ابنِ خريطة «حالة السوق»: لكل شمعة بيتكوين، هل السعر فوق متوسّطه (سوق صاعد)؟

    Maps each BTC candle timestamp → True if BTC closed above its EMA(period).
    Used as a market-regime gate: only take long setups on other coins when the
    overall market has a tailwind. Longs into a market-wide downtrend bleed.
    """
    closes = btc.closes()
    ema_s = ind.ema_series(closes, period)
    out = {}
    for c, e in zip(btc.candles, ema_s):
        out[round(c.ts)] = c.close > e if e else False
    return out


def market_return_map(btc: Series, lookback: int = 20) -> dict:
    """
    خريطة عائد السوق: لكل شمعة بيتكوين، عائد آخر `lookback` شمعة (نسبة).

    Maps each BTC candle timestamp → BTC's trailing `lookback`-bar return. Used
    for a relative-strength gate: only buy coins that outperformed the market
    (coin return > BTC return) over the same window — institutions buy leaders.
    """
    closes = btc.closes()
    out = {}
    for idx, c in enumerate(btc.candles):
        if idx - lookback < 0:
            continue
        past = closes[idx - lookback]
        if past > 0:
            out[round(c.ts)] = closes[idx] / past - 1.0
    return out


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


def backtest_prepump_series(series: Series, warmup: int = 80,
                            min_score: float = 0.0) -> BacktestResult:
    """
    باك-تِست مخصّص لإشارات «ما قبل الاندفاع» (بداية اندفاع / تجميع / انضغاط).

    Measures whether the pre-pump detectors actually precede up-moves: at each
    bar, if a setup fires (and passes min_score), open a long at that price with
    the same stop/target the bot would use, then check forward bars for outcome.
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
        if not setup or setup.get("score", 0.0) < min_score:
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


def backtest_breakout_series(
    series: Series,
    warmup: int = 60,
    rr: float = 2.0,
    min_score: float = 0.0,
    regime: Optional[dict] = None,
    lookback: int = 20,
    stop_buffer_atr: float = 0.5,
) -> BacktestResult:
    """
    باك-تِست لاستراتيجية «اختراق الاتجاه» (Donchian breakout) — نفس كاشف البوت.

    يفتح عند كسر أعلى قمة `lookback`، ويتتبّع الشموع التالية: الوقف أولًا في الأسوأ.
    فلتر السوق (regime) اختياري: لا ندخل إلا حين يكون السوق العام في صالحنا.
    """
    candles = series.candles
    trades: List[Trade] = []
    n = len(candles)
    i = max(warmup, lookback + 5)

    while i < n - 1:
        sub = Series(symbol=series.symbol, market=series.market, candles=candles[: i + 1])
        setup = detect_breakout(sub, lookback=lookback, rr=rr,
                                stop_buffer_atr=stop_buffer_atr)
        if not setup or setup["score"] < min_score:
            i += 1
            continue
        if regime is not None and not regime.get(round(candles[i].ts), False):
            i += 1
            continue

        entry, stop, target = setup["price"], setup["stop"], setup["target"]
        risk = entry - stop
        if risk <= 0:
            i += 1
            continue

        outcome = None
        j = i + 1
        while j < n:
            hi, lo = candles[j].high, candles[j].low
            if lo <= stop:                      # الوقف تحت — الأسوأ أولًا
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
        trades.append(Trade(series.symbol, "BUY", entry, stop, target, exit_price, r, won))
        i = j + 1

    return BacktestResult(symbol=series.symbol, trades=trades)


def backtest_trend_pullback_series(
    series: Series,
    warmup: int = 60,
    rr: float = 2.0,
    min_score: float = 0.0,
    regime: Optional[dict] = None,
    require_ema200: bool = False,
    breakeven_r: float = 0.0,
    entry_min_ts: Optional[float] = None,
    entry_max_ts: Optional[float] = None,
    direction: str = "long",
    require_momentum: bool = False,
    stop_buffer_atr: float = 0.0,
    rsi_max: Optional[float] = None,
    min_slope_pct: Optional[float] = None,
    rel_strength: Optional[dict] = None,
) -> BacktestResult:
    """
    باك-تِست لاستراتيجية «الارتداد داخل الاتجاه» (Long أو Short).

    يستخدم نفس كاشف البوت الحيّ `detect_trend_pullback` (مصدر واحد للحقيقة).

    فلاتر اختيارية لاختبار الانتقائية:
      - min_score: تجاهل أي إعداد أضعف من هذه الدرجة (نختار الأفضل فقط).
      - regime: خريطة حالة السوق {ts→مناسب؟}؛ لا ندخل إلا لما السوق في صالحنا.
      - require_ema200: Long لا يدخل إلا فوق EMA200؛ Short لا يدخل إلا تحته.
      - breakeven_r: بعد ربح breakeven_r×المخاطرة، ننقل الوقف إلى نقطة الدخول.
      - direction: "long" (شراء) أو "short" (بيع).
    """
    candles = series.candles
    closes = [c.close for c in candles]
    trades: List[Trade] = []
    n = len(candles)
    i = max(warmup, 55)
    is_short = direction == "short"
    side = "SELL" if is_short else "BUY"

    while i < n - 1:
        # نافذة الدخول (للـ walk-forward): لا نفتح إلا داخل المدى الزمني المطلوب.
        ts = candles[i].ts
        if entry_min_ts is not None and ts < entry_min_ts:
            i += 1
            continue
        if entry_max_ts is not None and ts >= entry_max_ts:
            break
        sub = Series(symbol=series.symbol, market=series.market, candles=candles[: i + 1])
        setup = detect_trend_pullback(sub, rr=rr, direction=direction,
                                      require_momentum=require_momentum,
                                      stop_buffer_atr=stop_buffer_atr)
        if not setup or setup["score"] < min_score:
            i += 1
            continue
        if regime is not None and not regime.get(round(candles[i].ts), False):
            i += 1
            continue
        # --- فلاتر احترافية اختيارية (تُقاس قبل تفعيلها حيًّا) ---
        # سقف علوي للـRSI: نرفض الارتداد الضعيف/العملة المتمدّدة (RSI عالٍ جدًا).
        if rsi_max is not None:
            r = setup.get("rsi")
            if r is not None and not is_short and r > rsi_max:
                i += 1
                continue
            if r is not None and is_short and r < (100.0 - rsi_max):
                i += 1
                continue
        # حد أدنى لميل الاتجاه (EMA50 slope %): ندخل فقط في اتجاه قويّ الميل.
        if min_slope_pct is not None:
            e50 = ind.ema(closes[: i + 1], 50)
            e50_prev = ind.ema(closes[: i - 2], 50) if i > 53 else None
            if not e50 or not e50_prev:
                i += 1
                continue
            slope = (e50 / e50_prev - 1.0) * 100.0
            if not is_short and slope < min_slope_pct:
                i += 1
                continue
            if is_short and -slope < min_slope_pct:
                i += 1
                continue
        # القوة النسبية مقابل BTC: ندخل فقط لو العملة تفوّقت على السوق آخر N شمعة.
        if rel_strength is not None:
            look = int(rel_strength.get("lookback", 20))
            btc_ret_map = rel_strength.get("btc_ret", {})
            btc_ret = btc_ret_map.get(round(candles[i].ts))
            if btc_ret is None or i - look < 0:
                i += 1
                continue
            past = closes[i - look]
            coin_ret = (closes[i] / past - 1.0) if past > 0 else 0.0
            if not is_short and coin_ret <= btc_ret:   # لازم تتفوّق على السوق
                i += 1
                continue
            if is_short and coin_ret >= btc_ret:        # للبيع: أضعف من السوق
                i += 1
                continue
        if require_ema200:
            e200 = ind.ema(closes[: i + 1], 200)
            if not e200:
                i += 1
                continue
            if is_short and candles[i].close >= e200:      # Short: لازم تحت EMA200
                i += 1
                continue
            if not is_short and candles[i].close <= e200:  # Long: لازم فوق EMA200
                i += 1
                continue

        entry = setup["price"]
        stop = setup["stop"]
        target = setup["target"]
        risk = abs(entry - stop)
        if risk <= 0:
            i += 1
            continue

        outcome = None
        moved = False                              # هل نُقل الوقف لنقطة الدخول؟
        be_level = (entry - breakeven_r * risk if is_short
                    else entry + breakeven_r * risk) if breakeven_r > 0 else None
        j = i + 1
        while j < n:
            hi, lo = candles[j].high, candles[j].low
            cur_stop = entry if moved else stop
            if is_short:
                if hi >= cur_stop:                # short: الوقف فوق — الأسوأ أولًا
                    outcome = (cur_stop, cur_stop < entry)
                    break
                if lo <= target:                  # الهدف تحت
                    outcome = (target, True)
                    break
                if be_level is not None and not moved and lo <= be_level:
                    moved = True
            else:
                if lo <= cur_stop:                # long: الوقف تحت — الأسوأ أولًا
                    outcome = (cur_stop, cur_stop > entry)
                    break
                if hi >= target:
                    outcome = (target, True)
                    break
                if be_level is not None and not moved and hi >= be_level:
                    moved = True
            j += 1

        if outcome is None:
            i += 1
            continue
        exit_price, won = outcome
        result_r = ((entry - exit_price) if is_short else (exit_price - entry)) / risk
        trades.append(
            Trade(series.symbol, side, entry, stop, target, exit_price, result_r, won)
        )
        i = j + 1

    return BacktestResult(symbol=series.symbol, trades=trades)

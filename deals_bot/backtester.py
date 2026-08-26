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
    mae_r: float = 0.0       # أقصى تحرّك عكس الصفقة قبل خروجها (بمضاعفات R) — «الانعكاس»
    ict_confirm: int = -1    # عدد تأكيدات ICT عند الدخول (0..6)؛ -1 = لم يُحسب


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
    require_macd: bool = False,
    require_obv: bool = False,
    stoch_max: Optional[float] = None,
    mfi_min: Optional[float] = None,
    mfi_max: Optional[float] = None,
    require_bb_inside: bool = False,
    fib_min: Optional[float] = None,
    fib_max: Optional[float] = None,
    require_vwap: bool = False,
    require_fvg: bool = False,
    require_bos: bool = False,
    require_sweep: bool = False,
    smc_lookback: int = 10,
    ict_confirm: bool = False,
    atr_pct_min: Optional[float] = None,
    atr_pct_max: Optional[float] = None,
    min_dollar_vol: Optional[float] = None,
    trail_activate_r: float = 0.0,
    trail_atr: float = 0.0,
    time_stop_bars: int = 0,
    vol_surge_min: Optional[float] = None,
    max_ext_atr: Optional[float] = None,
    near_support_atr: Optional[float] = None,
    target_at_resistance: bool = False,
    scale_out_r: float = 0.0,
    scale_out_frac: float = 0.0,
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
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    vols = [c.volume for c in candles]
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
                                      stop_buffer_atr=stop_buffer_atr,
                                      target_at_resistance=target_at_resistance)
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
        # --- فلاتر «تلاقي المؤشرات» (confluence) الاختيارية — long فقط، تُقاس أولًا ---
        # كل واحد يُختبر منفردًا على الكون الكامل؛ لا نفعّل إلا ما يرفع التوقّع فعلًا.
        if not is_short:
            win = closes[: i + 1]
            # MACD: الهيستوجرام في صعود (زخم إيجابي متسارع)
            if require_macd and not ind.macd_hist_rising(win):
                i += 1
                continue
            # OBV: تدفّق الحجم صاعد (تجميع، مش توزيع)
            if require_obv and ind.obv_rising(win, vols[: i + 1], lookback=10) is not True:
                i += 1
                continue
            # Stochastic %K: مش متشبّع شرائيًا (نتجنّب الدخول في القمة)
            if stoch_max is not None:
                st = ind.stochastic(highs[: i + 1], lows[: i + 1], win, k=14)
                if st is not None and st > stoch_max:
                    i += 1
                    continue
            # MFI: تدفّق أموال صحّي (شراء بمال حقيقي، بلا انفجار توزيعي)
            if mfi_min is not None or mfi_max is not None:
                mf = ind.mfi(highs[: i + 1], lows[: i + 1], win, vols[: i + 1], period=14)
                if mf is not None:
                    if mfi_min is not None and mf < mfi_min:
                        i += 1
                        continue
                    if mfi_max is not None and mf > mfi_max:
                        i += 1
                        continue
            # Bollinger: السعر لسه جوّه النطاق (مش ممدود فوق الباند العلوي)
            if require_bb_inside:
                bb = ind.bollinger(win, period=20, mult=2.0)
                if bb and closes[i] > bb[2]:
                    i += 1
                    continue
            # فيبوناتشي: عمق الارتداد لازم يقع في منطقة فيبوناتشي (المنطقة الذهبية).
            # نحسب ارتداد الشمعة الحالية بالنسبة للموجة الصاعدة الأخيرة (قاع→قمة).
            if fib_min is not None or fib_max is not None:
                ph, pl = ind.swing_points(highs[: i + 1], lows[: i + 1], left=2, right=2)
                sh = pl_before = None
                if ph:
                    sh_idx, sh = ph[-1]                         # آخر قمة (رأس الموجة)
                    lows_before = [p for p in pl if p[0] < sh_idx]
                    pl_before = lows_before[-1] if lows_before else None
                if sh is None or pl_before is None:
                    i += 1
                    continue                                   # لا هيكل موجة واضح
                rng = sh - pl_before[1]
                if rng <= 0:
                    i += 1
                    continue
                retr = (sh - lows[i]) / rng                     # عمق الارتداد (0..1)
                if fib_min is not None and retr < fib_min:
                    i += 1
                    continue
                if fib_max is not None and retr > fib_max:
                    i += 1
                    continue

            # --- أدوات Smart Money / ICT + VWAP (من دليل الأدوات) — تُقاس أولًا ---
            hw = highs[: i + 1]
            lw = lows[: i + 1]
            # VWAP: ندخل فقط والسعر فوق السعر المرجعي المرجّح بالحجم (فوق القيمة).
            if require_vwap:
                vw = ind.vwap(hw, lw, win, vols[: i + 1], window=50)
                if vw is None or closes[i] < vw:
                    i += 1
                    continue
            # FVG: لازم توجد فجوة قيمة عادلة صاعدة حديثة (بصمة مؤسسات).
            if require_fvg and not ind.has_bullish_fvg(hw, lw, lookback=smc_lookback):
                i += 1
                continue
            # BOS: كسر هيكل صاعد (إغلاق فوق آخر قمة ارتكاز).
            if require_bos and not ind.bos_bullish(hw, lw, win):
                i += 1
                continue
            # Liquidity Sweep: كنس قاع سابق ثم ارتداد فوقه (stop-hunt صاعد).
            if require_sweep and not ind.liquidity_sweep_bullish(
                    hw, lw, win, lookback=smc_lookback):
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

        # كلاسيكي: الهدف عند المقاومة مُطبَّق داخل detect_trend_pullback (مصدر واحد)
        # — فـ setup["target"] أعلاه يحمله بالفعل. هنا فقط فلتر الدخول قرب الدعم.
        # --- كلاسيكي: الدخول قريب من دعم أفقي حقيقي (تجميع قيعان سابقة) ---
        if near_support_atr is not None and not is_short:
            atr_sr = ind.atr(highs[: i + 1], lows[: i + 1], closes[: i + 1], 14) \
                or (entry * 0.01)
            _ph, pl_sr = ind.swing_points(highs[: i + 1], lows[: i + 1], 2, 2)
            supports = ind.sr_cluster([p[1] for p in pl_sr], 0.01)
            near = [s for s in supports
                    if abs(entry - s) <= near_support_atr * atr_sr and s <= entry * 1.02]
            if not near:
                i += 1
                continue

        # --- رافعة (2): فلتر التقلّب — تجنّب الدخول في ATR متطرّف (تشوّش/موت) ---
        atr_here = ind.atr(highs[: i + 1], lows[: i + 1], closes[: i + 1], 14)
        if (atr_pct_min is not None or atr_pct_max is not None) and atr_here and entry > 0:
            atr_pct = atr_here / entry * 100.0
            if atr_pct_min is not None and atr_pct < atr_pct_min:
                i += 1
                continue
            if atr_pct_max is not None and atr_pct > atr_pct_max:
                i += 1
                continue
        # --- رافعة (3): جودة السيولة — استبعاد العملات ضعيفة الحجم الدولاري ---
        if min_dollar_vol is not None and min_dollar_vol > 0:
            recent = candles[max(0, i - 19): i + 1]
            dv = sum(c.close * c.volume for c in recent) / max(1, len(recent))
            if dv < min_dollar_vol:
                i += 1
                continue
        # --- Warrior/Momentum: تأكيد الحجم — الدخول فقط مع اندفاع حجم حقيقي ---
        if vol_surge_min is not None and not is_short:
            vs = ind.volume_surge(vols[: i + 1], period=20)
            if vs is None or vs < vol_surge_min:
                i += 1
                continue
        # --- Warrior/Momentum: «لا تطارد» — رفض الدخول لو السعر ممتد جدًا فوق EMA9 ---
        if max_ext_atr is not None and not is_short:
            e9 = ind.ema(closes[: i + 1], 9)
            a9 = ind.atr(highs[: i + 1], lows[: i + 1], closes[: i + 1], 14)
            if e9 and a9 and a9 > 0 and (closes[i] - e9) / a9 > max_ext_atr:
                i += 1
                continue

        atr_fixed = atr_here or (entry * 0.01)     # ATR ثابت للـtrailing
        outcome = None
        moved = False                              # هل نُقل الوقف لنقطة الدخول؟
        peak = entry                               # أقصى سعر لصالح الصفقة (للـtrailing)
        trail_on = False
        adverse = 0.0                              # أقصى تحرّك عكس الصفقة (سعر)
        # --- خروج جزئي (Scale-out) — long فقط: نبيع جزءًا عند +scale_out_r ونبنك
        # ربحه، وننقل وقف الباقي لنقطة الدخول، والباقي يجري بالتتبّع/الهدف كالمعتاد.
        do_scale = (scale_out_r > 0 and 0 < scale_out_frac < 1 and not is_short)
        scaled = False
        banked_r = 0.0                             # R المُبنَّك من الجزء المُباع
        rem_frac = 1.0                             # الجزء المتبقّي من الصفقة
        be_level = (entry - breakeven_r * risk if is_short
                    else entry + breakeven_r * risk) if breakeven_r > 0 else None
        j = i + 1
        while j < n:
            hi, lo = candles[j].high, candles[j].low
            cur_stop = entry if moved else stop
            # --- رافعة (1أ): trailing stop — الوقف مبنيّ على قمة الشموع *السابقة* فقط
            # (بلا نظرة مستقبلية): نستخدم trail_on/peak المحدّثين من الشمعة الماضية،
            # ثم نُحدّثهما بشمعة اليوم *بعد* فحوص الخروج (أسفل) للتكرار التالي.
            if not is_short and trail_atr > 0 and trail_activate_r > 0 and trail_on:
                cur_stop = max(cur_stop, peak - trail_atr * atr_fixed)
            # تتبّع أقصى انعكاس عكس الصفقة (قبل الخروج): للشراء = كم نزل تحت الدخول.
            adverse = max(adverse, (hi - entry) if is_short else (entry - lo))
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
                    leg_r = (cur_stop - entry) / risk
                    total_r = banked_r + rem_frac * leg_r
                    outcome = (cur_stop, total_r > 0)
                    break
                # خروج جزئي عند +scale_out_r: بنك الجزء، والباقي يجري بنفس الوقف/الهدف
                # (بلا نقل للتعادل — ده رافعة منفصلة قِسناها) فيبقى التوقيت والدخول متطابقًا
                # مع الأساس ونعزل تأثير الخروج الجزئي وحده بمقارنة نظيفة.
                if do_scale and not scaled and hi >= entry + scale_out_r * risk:
                    banked_r = scale_out_frac * scale_out_r
                    rem_frac = 1.0 - scale_out_frac
                    scaled = True
                if hi >= target:
                    leg_r = (target - entry) / risk
                    total_r = banked_r + rem_frac * leg_r
                    outcome = (target, total_r > 0)
                    break
                if be_level is not None and not moved and hi >= be_level:
                    moved = True
            # حدّث حالة التتبّع بشمعة اليوم للتكرار التالي (بعد الخروج — لا lookahead)
            if not is_short and trail_atr > 0 and trail_activate_r > 0:
                peak = max(peak, hi)
                if not trail_on and hi >= entry + trail_activate_r * risk:
                    trail_on = True
            # --- رافعة (1ب): خروج زمني — صفقة ميتة لم تُغلق خلال N شمعة نُخرجها بالسعر ---
            if time_stop_bars > 0 and (j - i) >= time_stop_bars:
                px = candles[j].close
                outcome = (px, (px > entry) if not is_short else (px < entry))
                break
            j += 1

        if outcome is None:
            # صفقة لم تُغلق حتى نهاية البيانات: لو كنا بنكنا جزءًا بالفعل (scale-out)
            # نُغلق الباقي بآخر سعر متاح حتى لا نضيّع الربح المُحقَّق؛ وإلا نتجاهلها.
            if scaled and rem_frac > 0:
                outcome = (candles[n - 1].close, True)
            else:
                i += 1
                continue
        exit_price, _won_hint = outcome
        leg_r = ((entry - exit_price) if is_short else (exit_price - entry)) / risk
        result_r = banked_r + rem_frac * leg_r     # يشمل الجزء المُبنَّك (scale-out)
        won = result_r > 0
        mae_r = max(0.0, adverse) / risk           # الانعكاس بمضاعفات المخاطرة
        # طبقة تأكيد ICT (اختيارية): كم تأكيد ICT يدعم هذه الإشارة عند دخولها؟
        # عتبة 200 شمعة 1H تكفي لإعادة بناء 4H (≥50) واليومي كإضافة — عشان نقيس على
        # عيّنة حقيقية (تاريخ 1H من yfinance محدود، لا يبلغ 720 غالبًا).
        conf = -1
        if ict_confirm and not is_short and i >= 200:
            try:
                from .ict import ict_confirmations
                from .providers import resample_candles
                sub = candles[: i + 1]
                d1 = Series(series.symbol, series.market, resample_candles(sub, 24))
                h4 = Series(series.symbol, series.market, resample_candles(sub, 4))
                h1 = Series(series.symbol, series.market, sub)
                conf, _got = ict_confirmations(d1, h4, h1)
            except Exception:  # noqa: BLE001 - التأكيد إضافة، لا يُفشل القياس
                conf = -1
        trades.append(
            Trade(series.symbol, side, entry, stop, target, exit_price,
                  result_r, won, mae_r=mae_r, ict_confirm=conf)
        )
        i = j + 1

    return BacktestResult(symbol=series.symbol, trades=trades)


def backtest_ict_series(
    series: Series,
    step: int = 6,
    warmup: int = 720,
    fill_window: int = 36,
    max_hold: int = 240,
    min_score: Optional[float] = None,
) -> BacktestResult:
    """
    باك-تِست لنموذج ICT الكامل (نقطة-في-الزمن) — يقيس أداءه التاريخي الحقيقي.

    عند كل خطوة (كل `step` شمعة 1H، بعد إحماء يكفي لـ≥30 شمعة يومية) نعيد بناء
    الفريمات الثلاثة من مقطع التاريخ حتى تلك اللحظة (بلا نظر مستقبلي)، ونشغّل
    analyze_ict_frames. لو الإعداد صالح (score≥العتبة): ننتظر ارتداد السعر لمنطقة
    الدخول (أمر محدّد ICT) خلال `fill_window`؛ فإن امتلأ نتتبّع حتى TP1/SL. هذا
    يقيس: «لو دخلت إشارات ICT فعلًا، نسبة نجاحها وتوقّعها كام؟».
    """
    from .ict import ICT_MIN_SCORE, analyze_ict_frames
    from .providers import resample_candles

    thr = ICT_MIN_SCORE if min_score is None else min_score
    c = series.candles
    n = len(c)
    trades: List[Trade] = []
    i = max(warmup, 720)
    while i < n - 1:
        h1 = Series(series.symbol, series.market, c[: i + 1])
        h4 = Series(series.symbol, series.market, resample_candles(c[: i + 1], 4))
        d1 = Series(series.symbol, series.market, resample_candles(c[: i + 1], 24))
        setup = analyze_ict_frames(series.symbol, series.market, d1, h4, h1)
        if not setup or setup.score < thr or setup.entry <= 0 or setup.stop <= 0:
            i += step
            continue
        entry, stop, target = setup.entry, setup.stop, setup.tp1
        risk = entry - stop
        if risk <= 0 or target <= entry:
            i += step
            continue

        # انتظر ملء الأمر المحدّد (ارتداد السعر لمنطقة الدخول) خلال نافذة محدودة
        filled_at = None
        for j in range(i + 1, min(i + 1 + fill_window, n)):
            if c[j].low <= entry:
                filled_at = j
                break
        if filled_at is None:
            i += step
            continue

        # تتبّع النتيجة بعد الملء: الوقف أولًا في الأسوأ
        outcome = None
        for k in range(filled_at, min(filled_at + max_hold, n)):
            hi, lo = c[k].high, c[k].low
            if lo <= stop:
                outcome = (stop, False)
                break
            if hi >= target:
                outcome = (target, True)
                break
        if outcome is None:
            i = filled_at + 1
            continue
        exit_price, won = outcome
        r = (exit_price - entry) / risk
        trades.append(Trade(series.symbol, "BUY", entry, stop, target,
                            exit_price, r, won))
        # استأنف بعد خروج الصفقة
        i = max(i + step, filled_at + 1)

    return BacktestResult(symbol=series.symbol, trades=trades)

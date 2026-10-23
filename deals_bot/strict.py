"""
المحلّل المتحفّظ — صفقات عالية الاحتمالية فقط، و«لا صفقة» أفضل من صفقة ضعيفة.

Strict, rule-based analyst. Eight mandatory conditions must ALL hold on the last
*closed* candle of the primary timeframe; a single miss = no trade:

  1. الاتجاه: كل فريمات الاتجاه (مثلًا 4H و1D) فوق EMA200 للشراء / تحتها للبيع.
  2. المنطقة: الدخول من دعم/مقاومة مختبرة مرتين على الأقل، أو Order Block واضح.
  3. التأكيد: شمعة Engulfing أو Pin Bar مقفولة على الفريم الأساسي.
  4. الزخم: RSI مش متشبّع ضد الصفقة + MACD متوافق (الهيستوجرام في اتجاه الصفقة).
  5. الفوليوم: حجم شمعة التأكيد أعلى من متوسّط آخر 20 شمعة.
  6. العائد/المخاطرة: ≥ 1:2 حتى أقرب عائق (قمة/قاع معاكس) — وإلا نرفض.
  7. الأخبار: لا صفقات قبل/بعد خبر قوي (فائدة/تضخم/وظائف) بساعة.
  8. السيولة: لا صفقات في سوق جانبي (ADX ضعيف) أو وقت سيولة ضعيفة.

بعد تحقّق الثمانية تُحسب درجة ثقة من 100 حسب جودة التأكيدات (الحد الأدنى
للشروط وحدها 65، فالوصول لـ80 يحتاج تأكيدات إضافية حقيقية). لا ترسل تحت العتبة.

كل الدوال هنا نقية (بلا شبكة) ما عدا fetch_news — عشان الاختبار offline.
"""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from . import indicators as ind
from .models import Candle, Series

TF_SECONDS = {"15m": 900, "30m": 1800, "1h": 3600, "2h": 7200, "4h": 14400,
              "6h": 21600, "1d": 86400}

NEWS_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
# أخبار قوية حتى لو المصدر صنّفها «متوسطة»: فائدة، تضخم، وظائف.
NEWS_KEYWORDS = re.compile(
    r"rate|fomc|cpi|ppi|pce|inflation|non-farm|nonfarm|employment|unemployment|"
    r"jobless|payroll|jolts|powell|lagarde|bailey|ueda",
    re.IGNORECASE,
)


@dataclass
class StrictSetup:
    symbol: str
    market: str
    timeframe: str
    direction: str              # BUY | SELL
    entry: float
    stop: float
    tp1: float
    tp2: float
    rr: float                   # العائد/المخاطرة حتى TP2
    score: int
    candle_ts: float            # زمن فتح شمعة التأكيد
    reasons: List[str] = field(default_factory=list)


@dataclass
class StrictConfig:
    trend_ema: int = 200
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    min_rr: float = 2.0
    max_rr: float = 3.0           # سقف واقعي للهدف (لو العائق بعيد جدًا)
    adx_min: float = 20.0         # تحته = سوق جانبي عشوائي
    min_dollar_vol: float = 0.0   # متوسط حجم دولاري لكل شمعة (0 = معطّل)
    block_weekend_crypto: bool = True
    news_window_min: int = 60
    zone_lookback: int = 150
    stop_buffer_atr: float = 0.25


# --------------------------------------------------------------------------- #
# أدوات مساعدة
# --------------------------------------------------------------------------- #
def closed_candles(series: Series, timeframe: str, now_ts: float) -> Series:
    """احذف الشمعة اللي لسه مفتوحة — ممنوع القرار قبل قفل الشمعة."""
    step = TF_SECONDS.get(timeframe, 3600)
    done = [c for c in series.candles if c.ts + step <= now_ts]
    return Series(symbol=series.symbol, market=series.market, candles=done)


def adx(highs: List[float], lows: List[float], closes: List[float],
        period: int = 14) -> Optional[float]:
    """مؤشر ADX (Wilder) — قوة الاتجاه؛ أقل من ~20 = حركة جانبية."""
    n = len(closes)
    if n < period * 2 + 1:
        return None
    tr, pdm, mdm = [], [], []
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        pdm.append(up if up > down and up > 0 else 0.0)
        mdm.append(down if down > up and down > 0 else 0.0)
        tr.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]),
                      abs(lows[i] - closes[i - 1])))

    def wilder(vals):
        s = sum(vals[:period])
        out = [s]
        for v in vals[period:]:
            s = s - s / period + v
            out.append(s)
        return out

    atr_s, p_s, m_s = wilder(tr), wilder(pdm), wilder(mdm)
    dx = []
    for a, p, m in zip(atr_s, p_s, m_s):
        if a <= 0:
            dx.append(0.0)
            continue
        pdi, mdi = 100 * p / a, 100 * m / a
        dx.append(0.0 if pdi + mdi == 0 else 100 * abs(pdi - mdi) / (pdi + mdi))
    if len(dx) < period:
        return None
    val = sum(dx[:period]) / period
    for d in dx[period:]:
        val = (val * (period - 1) + d) / period
    return val


def _macd_hist(closes: List[float]) -> Optional[Tuple[float, float, float, float]]:
    """(macd_line, signal, hist_now, hist_prev) لآخر شمعتين."""
    fast, slow = ind.ema_series(closes, 12), ind.ema_series(closes, 26)
    if len(fast) < 2 or len(slow) < 2:
        return None
    line = [f - s for f, s in zip(fast, slow)]
    sig = ind.ema_series(line, 9)
    if len(sig) < 2:
        return None
    return line[-1], sig[-1], line[-1] - sig[-1], line[-2] - sig[-2]


def candle_pattern(c: List[Candle], direction: str) -> Tuple[Optional[str], bool]:
    """
    نوع شمعة الانعكاس على آخر شمعة مقفولة: ("engulfing"|"pin", قوية؟) أو (None, False).

    Engulfing: جسم الحالية يبتلع جسم السابقة المعاكسة. قوية لو جسمها ≥ 1.5× جسم السابقة.
    Pin Bar: فتيل الرفض ≥ 2× الجسم، والفتيل المعاكس ≤ الجسم، والإغلاق في الثلث المناسب.
    قوية لو فتيل الرفض ≥ 3× الجسم.
    """
    if len(c) < 2:
        return None, False
    prev, cur = c[-2], c[-1]
    rng = cur.high - cur.low
    if rng <= 0:
        return None, False
    body = abs(cur.close - cur.open)
    prev_body = abs(prev.close - prev.open)
    if direction == "BUY":
        if (prev.close < prev.open and cur.close > cur.open
                and cur.close >= prev.open and cur.open <= prev.close):
            return "engulfing", prev_body > 0 and body >= 1.5 * prev_body
        lower = min(cur.open, cur.close) - cur.low
        upper = cur.high - max(cur.open, cur.close)
        b = max(body, rng * 0.02)
        if lower >= 2 * b and upper <= b and cur.close >= cur.low + rng * 2 / 3:
            return "pin", lower >= 3 * b
    else:
        if (prev.close > prev.open and cur.close < cur.open
                and cur.open >= prev.close and cur.close <= prev.open):
            return "engulfing", prev_body > 0 and body >= 1.5 * prev_body
        lower = min(cur.open, cur.close) - cur.low
        upper = cur.high - max(cur.open, cur.close)
        b = max(body, rng * 0.02)
        if upper >= 2 * b and lower <= b and cur.close <= cur.high - rng * 2 / 3:
            return "pin", upper >= 3 * b
    return None, False


def _order_block(c: List[Candle], direction: str, lookback: int = 20):
    """
    آخر Order Block قبل نمط التأكيد (نستبعد آخر شمعتين حتى لا يصنع النمط نفسه OB).
    شراء: آخر شمعة هابطة تلاها اندفاع يقفل فوق قمّتها. بيع: العكس.
    يرجّع (low, high) أو None.
    """
    hist = c[:-2]
    n = len(hist)
    for m in range(n - 2, max(0, n - lookback) - 1, -1):
        k = hist[m]
        nxt = hist[m + 1:m + 4]
        if direction == "BUY" and k.close < k.open and any(x.close > k.high for x in nxt):
            return k.low, k.high
        if direction == "SELL" and k.close > k.open and any(x.close < k.low for x in nxt):
            return k.low, k.high
    return None


def _levels(prices: List[float], tol: float) -> List[Tuple[float, int]]:
    """عنقدة نقاط الارتكاز المتقاربة → [(مستوى, عدد اللمسات)]."""
    out: List[Tuple[float, int]] = []
    used = [False] * len(prices)
    for i, a in enumerate(prices):
        if used[i]:
            continue
        grp = [a]
        for j in range(i + 1, len(prices)):
            if not used[j] and abs(prices[j] - a) <= tol:
                used[j] = True
                grp.append(prices[j])
        out.append((sum(grp) / len(grp), len(grp)))
    return out


# --------------------------------------------------------------------------- #
# الأخبار
# --------------------------------------------------------------------------- #
def fetch_news(url: str = NEWS_URL, timeout: int = 20) -> List[dict]:
    """أجندة الأسبوع (ForexFactory) → [{"ts", "currency", "title", "impact"}]."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    out = []
    for e in raw or []:
        try:
            ts = datetime.fromisoformat(e["date"]).timestamp()
        except (KeyError, ValueError, TypeError):
            continue
        out.append({"ts": ts, "currency": e.get("country", ""),
                    "title": e.get("title", ""), "impact": e.get("impact", "")})
    return out


def news_currencies(symbol: str, market: str) -> List[str]:
    """العملات اللي أخبارها تحرّك الرمز. الكريبتو والأسهم الأمريكية → USD."""
    if market == "forex":
        s = symbol.upper().replace("=X", "").replace("/", "")
        return [s[:3], s[3:6]] if len(s) >= 6 else ["USD"]
    return ["USD"]


def blocking_news(events: List[dict], currencies: List[str], start_ts: float,
                  end_ts: float, window_min: int = 60) -> Optional[dict]:
    """أول خبر قوي يقع خلال ساعة قبل/بعد الفترة [start, end] (أو None)."""
    w = window_min * 60
    for e in events:
        if e.get("currency") not in currencies and e.get("currency") != "All":
            continue
        strong = e.get("impact") == "High" or NEWS_KEYWORDS.search(e.get("title", ""))
        if strong and start_ts - w <= e["ts"] <= end_ts + w:
            return e
    return None


# --------------------------------------------------------------------------- #
# السيولة / الجلسة
# --------------------------------------------------------------------------- #
def low_liquidity_time(market: str, ts: float, block_weekend_crypto: bool = True) -> Optional[str]:
    """سبب لو التوقيت ضعيف السيولة، وإلا None."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    weekend = dt.weekday() >= 5
    if market == "crypto":
        return "عطلة نهاية الأسبوع (سيولة الكريبتو أضعف)" if weekend and block_weekend_crypto else None
    if weekend:
        return "السوق مقفول (عطلة)"
    if market == "forex" and not (7 <= dt.hour < 20):
        return "خارج جلستي لندن/نيويورك"
    return None


# --------------------------------------------------------------------------- #
# المحلّل
# --------------------------------------------------------------------------- #
def analyze(primary: Series, trend: Dict[str, Series], timeframe: str, now_ts: float,
            news: Optional[List[dict]], cfg: StrictConfig = StrictConfig(),
            direction: str = "BUY") -> Tuple[Optional[StrictSetup], List[str]]:
    """
    قيّم اتجاهًا واحدًا (BUY أو SELL) على آخر شمعة مقفولة.

    news=None يعني «الأجندة غير متاحة» → نرفض (لا نقدر نتأكّد من الشرط 7).
    يرجّع (الإعداد أو None، قائمة أسباب الرفض/النجاح).
    """
    buy = direction == "BUY"
    sym, market = primary.symbol, primary.market
    p = closed_candles(primary, timeframe, now_ts)
    c = p.candles
    if len(c) < 60:
        return None, ["بيانات الفريم الأساسي غير كافية"]
    closes, highs, lows, vols = p.closes(), p.highs(), p.lows(), p.volumes()
    last = c[-1]
    points = 0
    why: List[str] = []

    # 1) الاتجاه على الفريمات الأكبر
    aligned = []
    stack_ok = True
    for tf, s in trend.items():
        s = closed_candles(s, tf, now_ts)
        e200 = ind.ema(s.closes(), cfg.trend_ema)
        if e200 is None:
            return None, [f"1) بيانات {tf} أقل من {cfg.trend_ema} شمعة"]
        px = s.closes()[-1]
        if (px > e200) != buy:
            return None, [f"1) {tf}: السعر {'تحت' if buy else 'فوق'} EMA{cfg.trend_ema}"]
        e50 = ind.ema(s.closes(), 50)
        if e50 is None or (e50 > e200) != buy:
            stack_ok = False
        aligned.append(tf.upper())
    points += 15 + (5 if stack_ok else 0)
    why.append(f"اتجاه {' و'.join(aligned)} {'فوق' if buy else 'تحت'} EMA{cfg.trend_ema}")

    a = ind.atr(highs, lows, closes, 14)
    if not a or a <= 0:
        return None, ["ATR غير متاح"]

    # 3) شمعة التأكيد (نتحقّق منها قبل المنطقة لأنها أرخص وأندر)
    pattern, strong = candle_pattern(c, direction)
    if not pattern:
        return None, ["3) لا توجد شمعة Engulfing/Pin Bar مقفولة"]
    points += 10 + (5 if strong else 0)
    why.append(("Engulfing" if pattern == "engulfing" else "Pin Bar") + (" قوية" if strong else ""))

    # 2) المنطقة: دعم/مقاومة ملموسة ≥2 أو Order Block
    hist_h, hist_l = highs[-cfg.zone_lookback:-2], lows[-cfg.zone_lookback:-2]
    ph, pl = ind.swing_points(hist_h, hist_l, 3, 3)
    tol = 0.5 * a
    pivots = [x[1] for x in (pl if buy else ph)]
    probe = min(last.low, c[-2].low) if buy else max(last.high, c[-2].high)
    level = None
    touches = 0
    for lv, n in _levels(pivots, tol):
        if n >= 2 and abs(probe - lv) <= tol and ((last.close > lv) if buy else (last.close < lv)):
            if n > touches:
                level, touches = lv, n
    ob = _order_block(c, direction)
    in_ob = bool(ob) and (
        (probe <= ob[1] and last.close >= ob[0]) if buy else (probe >= ob[0] and last.close <= ob[1])
    )
    if level is None and not in_ob:
        return None, ["2) الدخول ليس من دعم/مقاومة مختبرة مرتين ولا من Order Block"]
    points += 10 + (5 if touches >= 3 else 0) + (5 if level is not None and in_ob else 0)
    if level is not None:
        why.append(f"{'دعم' if buy else 'مقاومة'} مختبر {touches} مرات")
    if in_ob:
        why.append("Order Block")

    # 4) الزخم
    r = ind.rsi(closes, 14)
    m = _macd_hist(closes)
    if r is None or m is None:
        return None, ["4) RSI/MACD غير متاح"]
    if (buy and r >= cfg.rsi_overbought) or (not buy and r <= cfg.rsi_oversold):
        return None, [f"4) RSI {r:.0f} متشبّع ضد الصفقة"]
    line, sig, h_now, h_prev = m
    if (h_now <= h_prev) if buy else (h_now >= h_prev):
        return None, ["4) MACD غير متوافق (الهيستوجرام عكس الصفقة)"]
    both = (line > sig) if buy else (line < sig)
    points += 10 + (5 if both else 0)
    why.append(f"RSI {r:.0f} + MACD {'متقاطع و' if both else ''}متسارع")

    # 5) الفوليوم
    avg_v = sum(vols[-21:-1]) / 20
    if avg_v <= 0 or vols[-1] <= avg_v:
        return None, ["5) فوليوم شمعة التأكيد ليس أعلى من متوسط 20 شمعة"]
    vr = vols[-1] / avg_v
    points += 5 + (5 if vr >= 1.5 else 0)
    why.append(f"فوليوم {vr:.1f}× المتوسط")

    # 6) العائد/المخاطرة حتى أقرب عائق معاكس
    entry = last.close
    if buy:
        stop = min(last.low, c[-2].low, ob[0] if in_ob else last.low) - cfg.stop_buffer_atr * a
        risk = entry - stop
    else:
        stop = max(last.high, c[-2].high, ob[1] if in_ob else last.high) + cfg.stop_buffer_atr * a
        risk = stop - entry
    if risk <= 0:
        return None, ["6) وقف غير منطقي"]
    ph_all, pl_all = ind.swing_points(highs[-cfg.zone_lookback:], lows[-cfg.zone_lookback:], 3, 3)
    if buy:
        obstacles = sorted(x[1] for x in ph_all if x[1] > entry)
    else:
        obstacles = sorted((x[1] for x in pl_all if x[1] < entry), reverse=True)
    if obstacles:
        room = abs(obstacles[0] - entry) / risk
        if room < cfg.min_rr:
            return None, [f"6) أقرب {'مقاومة' if buy else 'دعم'} على بعد {room:.1f}R فقط (< {cfg.min_rr:g})"]
        rr = min(room, cfg.max_rr)
    else:
        rr = cfg.min_rr
    tp2 = entry + rr * risk if buy else entry - rr * risk
    tp1 = entry + risk if buy else entry - risk
    points += 5 + (5 if rr >= 3.0 - 1e-9 else 0)

    # 7) الأخبار
    if news is None:
        return None, ["7) أجندة الأخبار غير متاحة — لا نخاطر بدون تأكّد"]
    hit = blocking_news(news, news_currencies(sym, market), last.ts, now_ts, cfg.news_window_min)
    if hit:
        when = datetime.fromtimestamp(hit["ts"], tz=timezone.utc).strftime("%a %H:%M UTC")
        return None, [f"7) خبر قوي قريب: {hit['currency']} {hit['title']} ({when})"]
    points += 5

    # 8) السيولة والحركة الجانبية
    lq = low_liquidity_time(market, now_ts, cfg.block_weekend_crypto)
    if lq:
        return None, [f"8) {lq}"]
    x = adx(highs, lows, closes, 14)
    if x is None or x < cfg.adx_min:
        return None, [f"8) سوق جانبي/عشوائي (ADX {x or 0:.0f} < {cfg.adx_min:g})"]
    if cfg.min_dollar_vol > 0:
        dvol = sum(cl * v for cl, v in zip(closes[-20:], vols[-20:])) / 20
        if dvol < cfg.min_dollar_vol:
            return None, [f"8) سيولة ضعيفة (${dvol:,.0f}/شمعة)"]
    points += 5
    why.append(f"ADX {x:.0f}")

    return StrictSetup(
        symbol=sym, market=market, timeframe=timeframe, direction=direction,
        entry=entry, stop=stop, tp1=tp1, tp2=tp2, rr=rr, score=int(points),
        candle_ts=last.ts, reasons=why,
    ), why


def best_setup(primary: Series, trend: Dict[str, Series], timeframe: str, now_ts: float,
               news: Optional[List[dict]], cfg: StrictConfig = StrictConfig(),
               allow_short: bool = True) -> Tuple[Optional[StrictSetup], List[str]]:
    """جرّب الشراء ثم البيع (لو مسموح) — يرجّع الإعداد الأعلى درجة وأسباب الرفض."""
    found, notes = [], []
    for d in (("BUY", "SELL") if allow_short else ("BUY",)):
        s, why = analyze(primary, trend, timeframe, now_ts, news, cfg, d)
        if s:
            found.append(s)
        else:
            notes.append(f"{'شراء' if d == 'BUY' else 'بيع'}: {why[0]}")
    if not found:
        return None, notes
    best = max(found, key=lambda s: s.score)
    return best, best.reasons


# --------------------------------------------------------------------------- #
# الرسالة
# --------------------------------------------------------------------------- #
NO_TRADE = "لا توجد فرصة مطابقة للشروط حالياً"


def _px(x: float) -> str:
    if x >= 1000:
        return f"{x:,.2f}"
    if x >= 1:
        return f"{x:.4f}"
    return f"{x:.6g}"


def position_size(equity: float, risk_pct: float, entry: float, stop: float) -> Tuple[float, float]:
    """(الكمية، المبلغ المُخاطَر) — المخاطرة مقصورة على 1%–2% من رأس المال."""
    risk_pct = min(max(risk_pct, 0.01), 0.02)
    amount = equity * risk_pct
    per_unit = abs(entry - stop)
    return (amount / per_unit if per_unit > 0 else 0.0), amount


def format_setup(s: StrictSetup, equity: float, risk_pct: float) -> str:
    qty, amount = position_size(equity, risk_pct, s.entry, s.stop)
    pair = s.symbol.replace("-USD", "USDT") if s.market == "crypto" else s.symbol
    side = "شراء 🟢" if s.direction == "BUY" else "بيع 🔴"
    reasons = s.reasons
    half = (len(reasons) + 1) // 2
    return (
        f"📊 الزوج: {pair} ({s.timeframe.upper()})\n"
        f"📈 الاتجاه: {side}\n"
        f"🎯 الدخول: {_px(s.entry)}\n"
        f"🛑 وقف الخسارة: {_px(s.stop)}\n"
        f"✅ TP1: {_px(s.tp1)} (انقل الوقف لنقطة الدخول بعده)\n"
        f"✅ TP2: {_px(s.tp2)}\n"
        f"⚖️ العائد/المخاطرة: 1:{s.rr:.1f}\n"
        f"🔒 درجة الثقة: {s.score}/100\n"
        f"💼 المخاطرة: {min(max(risk_pct, 0.01), 0.02) * 100:g}% = ${amount:,.2f} "
        f"(الكمية ≈ {qty:.6g})\n"
        f"📝 السبب: {' + '.join(reasons[:half])}\n"
        f"{' + '.join(reasons[half:])}"
    )

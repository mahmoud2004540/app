"""
محلّل ICT / Smart Money Concepts — تحليل مؤسسي حقيقي من شموع فعلية (لا تأليف).

Institutional-style ICT/SMC analyzer. Every element below is COMPUTED from real
OHLCV candles — market structure from fractal pivots, liquidity from actual
prior-day/week extremes and equal highs/lows, FVG/Order-Block/Displacement from
the candle bodies themselves. Nothing is hand-waved.

Honest scope (stated, not hidden):
  • The bot is SPOT-ONLY (no leverage, no shorting) → this model takes LONG
    setups only. Bearish HTF bias ⇒ NO TRADE (we stand aside, we don't short).
  • On 24/7 crypto, NWOG/NDOG (weekend/session opening gaps) and true body-to-body
    "volume imbalances" are ~nil (price is continuous). We surface the measurable
    proxies (displacement + volume surge + wick rejection) and say so, rather
    than invent gaps that don't exist.

Entry requires MULTIPLE confirmations (never a lone FVG/OB):
  HTF bias + liquidity target + liquidity sweep + displacement + FVG/OB + LTF
  confirmation. The setup is then scored /100 on the user's rubric and only
  proposed at ≥ MIN_SCORE (default 80); otherwise NO TRADE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from . import indicators as ind
from .models import Series

# ----------------------------------------------------------------------------- #
# عتبة الجودة: لا نقترح صفقة تحتها (نفس ما طلب المستخدم: ركّز على الجودة).
try:
    import config as _cfg
    ICT_MIN_SCORE = float(getattr(_cfg, "ICT_MIN_SCORE", 80.0))
except Exception:  # noqa: BLE001 - الوحدة تعمل مستقلة في الاختبارات بلا config
    ICT_MIN_SCORE = 80.0
# تفاوت «القمم/القيعان المتساوية» (سيولة مكدّسة): ضمن هذه النسبة تُعدّ متساوية.
EQUAL_TOL = 0.0015          # 0.15%


@dataclass
class Zone:
    """منطقة سعرية (FVG / Order Block) — حدّها الأدنى والأعلى ومكانها."""
    low: float
    high: float
    idx: int
    kind: str               # "fvg" | "ob"

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2.0


@dataclass
class ICTSetup:
    symbol: str
    market: str
    price: float
    htf_bias: str                       # "bullish" | "bearish" | "ranging"
    entry: float = 0.0
    stop: float = 0.0
    tp1: float = 0.0
    tp2: float = 0.0
    tp3: float = 0.0
    invalidation: float = 0.0
    rr: float = 0.0
    score: float = 0.0
    breakdown: dict = field(default_factory=dict)     # نقاط كل عامل
    liquidity_target: str = ""
    liquidity_sweep: str = ""
    entry_zone: str = ""
    reasons: List[str] = field(default_factory=list)   # لماذا الصفقة
    blockers: List[str] = field(default_factory=list)   # أسباب عدم الدخول
    timeframe: str = "1h"

    @property
    def is_tradeable(self) -> bool:
        return self.score >= ICT_MIN_SCORE and self.entry > 0 and self.rr > 0


# ----------------------------------------------------------------------------- #
# 1) هيكل السوق (Market Structure) — من نقاط الارتكاز الفراكتالية
# ----------------------------------------------------------------------------- #
def market_structure(series: Series, left: int = 2, right: int = 2) -> dict:
    """
    حدّد اتجاه الهيكل من تسلسل القمم/القيعان: HH+HL=صاعد، LH+LL=هابط.

    Returns {bias, bos, choch, last_ph, last_pl, prev_ph, prev_pl}. BOS (Break of
    Structure) = the last close pushed past the most recent pivot in the trend's
    direction; CHoCH (Change of Character) = the first break the OTHER way after
    a run — the earliest tell that structure is flipping.
    """
    highs, lows, closes = series.highs(), series.lows(), series.closes()
    ph, pl = ind.swing_points(highs, lows, left, right)
    out = {"bias": "ranging", "bos": False, "choch": False,
           "last_ph": None, "last_pl": None, "prev_ph": None, "prev_pl": None}
    if len(ph) < 2 or len(pl) < 2 or not closes:
        return out
    out["last_ph"], out["prev_ph"] = ph[-1][1], ph[-2][1]
    out["last_pl"], out["prev_pl"] = pl[-1][1], pl[-2][1]
    higher_highs = ph[-1][1] > ph[-2][1]
    higher_lows = pl[-1][1] > pl[-2][1]
    lower_highs = ph[-1][1] < ph[-2][1]
    lower_lows = pl[-1][1] < pl[-2][1]
    if higher_highs and higher_lows:
        out["bias"] = "bullish"
    elif lower_highs and lower_lows:
        out["bias"] = "bearish"
    close = closes[-1]
    # BOS صاعد: إغلاق فوق آخر قمة ارتكاز؛ هابط: إغلاق تحت آخر قاع.
    if close > ph[-1][1]:
        out["bos"] = "bullish"
    elif close < pl[-1][1]:
        out["bos"] = "bearish"
    # CHoCH: كسر عكس الاتجاه السائد (أضعف إشارة لكن الأبكر).
    if out["bias"] == "bearish" and close > ph[-1][1]:
        out["choch"] = "bullish"
    elif out["bias"] == "bullish" and close < pl[-1][1]:
        out["choch"] = "bearish"
    return out


# ----------------------------------------------------------------------------- #
# 2) السيولة (Liquidity): PDH/PDL, PWH/PWL, Equal Highs/Lows
# ----------------------------------------------------------------------------- #
def prev_period_levels(daily: Series) -> dict:
    """أعلى/أدنى اليوم السابق (PDH/PDL) والأسبوع السابق (PWH/PWL) من شموع 1D."""
    c = daily.candles
    out = {"pdh": None, "pdl": None, "pwh": None, "pwl": None}
    if len(c) >= 2:
        out["pdh"], out["pdl"] = c[-2].high, c[-2].low          # اليوم المكتمل السابق
    if len(c) >= 8:
        prev_week = c[-8:-1]                                     # 7 أيام سابقة مكتملة
        out["pwh"] = max(x.high for x in prev_week)
        out["pwl"] = min(x.low for x in prev_week)
    return out


def equal_levels(series: Series, tol: float = EQUAL_TOL, left: int = 2, right: int = 2):
    """
    اكتشف «القمم المتساوية» و«القيعان المتساوية» (سيولة مكدّسة) من نقاط الارتكاز.

    Equal highs/lows are pivots sitting within `tol` of each other — retail stops
    pool just beyond them, so price is drawn there (a liquidity magnet). Returns
    (equal_highs, equal_lows) as representative price levels.
    """
    highs, lows = series.highs(), series.lows()
    ph, pl = ind.swing_points(highs, lows, left, right)
    eq_h = _cluster([p[1] for p in ph], tol)
    eq_l = _cluster([p[1] for p in pl], tol)
    return eq_h, eq_l


def _cluster(levels: List[float], tol: float) -> List[float]:
    """اجمع المستويات المتقاربة (ضمن tol) → مستوى تمثيلي واحد لكل عنقود ≥2."""
    out = []
    used = [False] * len(levels)
    for i, a in enumerate(levels):
        if used[i] or a <= 0:
            continue
        group = [a]
        for j in range(i + 1, len(levels)):
            if not used[j] and abs(levels[j] - a) / a <= tol:
                used[j] = True
                group.append(levels[j])
        if len(group) >= 2:                 # «متساوية» تحتاج تكرارًا
            out.append(sum(group) / len(group))
    return out


# ----------------------------------------------------------------------------- #
# 3) تسليم السعر (Price Delivery): Displacement, FVG, Order Block, Wick
# ----------------------------------------------------------------------------- #
def displacement(series: Series, lookback: int = 5, body_atr_mult: float = 1.5):
    """
    اكتشف «الاندفاع» (Displacement): شمعة جسمها ضخم مقارنةً بالـATR (طاقة مؤسسية).

    Displacement = an outsized, one-sided candle (body ≥ body_atr_mult × ATR)
    within the recent window — the institutional footprint that creates the FVG.
    Returns (found_bull, found_bear, strength_in_atr).
    """
    c = series.candles
    highs, lows, closes = series.highs(), series.lows(), series.closes()
    a = ind.atr(highs, lows, closes, 14)
    if not a or a <= 0 or len(c) < lookback + 1:
        return False, False, 0.0
    bull = bear = False
    strength = 0.0
    for k in range(len(c) - lookback, len(c)):
        body = c[k].close - c[k].open
        mag = abs(body) / a
        if mag >= body_atr_mult:
            strength = max(strength, mag)
            if body > 0:
                bull = True
            else:
                bear = True
    return bull, bear, strength


def find_bullish_fvg(series: Series, lookback: int = 12) -> Optional[Zone]:
    """
    أحدث فجوة قيمة عادلة صاعدة (Bullish FVG) كمنطقة دخول: high[A] < low[C].

    Scans the recent window for the newest 3-candle bullish imbalance and returns
    its untraded gap (A.high → C.low) as the entry Zone. Institutions revisit it.
    """
    highs, lows = series.highs(), series.lows()
    n = len(highs)
    if n < 3:
        return None
    start = max(1, n - lookback)
    for m in range(n - 2, start - 1, -1):       # الأحدث أولًا
        if m - 1 >= 0 and highs[m - 1] < lows[m + 1]:
            return Zone(low=highs[m - 1], high=lows[m + 1], idx=m, kind="fvg")
    return None


def find_bullish_ob(series: Series, lookback: int = 12) -> Optional[Zone]:
    """
    آخر Order Block صاعد: آخر شمعة هابطة قبل اندفاع صاعد يكسر قمّتها.

    Bullish order block = the last down-candle immediately before an up-move that
    breaks above that candle's high — the price zone where institutions loaded
    longs. Returns its body/range as the entry Zone.
    """
    c = series.candles
    n = len(c)
    if n < 3:
        return None
    start = max(1, n - lookback)
    for m in range(n - 2, start - 1, -1):
        if c[m].close < c[m].open:                      # شمعة هابطة (مرشّح OB)
            # اندفاع صاعد بعدها يكسر قمّتها؟
            if any(c[k].close > c[m].high for k in range(m + 1, min(m + 4, n))):
                return Zone(low=c[m].low, high=c[m].high, idx=m, kind="ob")
    return None


def wick_rejection(series: Series, bull: bool = True, ratio: float = 1.5) -> bool:
    """
    رفض بفتيل (Wick/Rejection): فتيل سفلي طويل (شراء) أطول من الجسم بمضاعف ratio.

    A long lower wick (buyers rejecting lower prices) on the last candle is a
    rejection signal. `ratio` = wick must exceed body by this factor.
    """
    if not series.candles:
        return False
    k = series.candles[-1]
    body = abs(k.close - k.open) or (k.high - k.low) * 0.01 or 1e-9
    if bull:
        lower_wick = min(k.open, k.close) - k.low
        return lower_wick > body * ratio
    upper_wick = k.high - max(k.open, k.close)
    return upper_wick > body * ratio


def liquidity_sweep_of(series: Series, level: float, lookback: int = 6) -> bool:
    """
    هل كنس السعر مستوى سيولة معيّنًا (اخترقه بفتيل ثم أغلق فوقه) خلال آخر lookback؟

    A sweep of `level` = a recent candle whose LOW pierced below it (grabbing the
    stops resting there) but whose CLOSE reclaimed above it — the stop-hunt that
    typically precedes the real move up.
    """
    c = series.candles
    if level is None or level <= 0 or not c:
        return False
    for k in c[-lookback:]:
        if k.low < level and k.close > level:
            return True
    return False


# ----------------------------------------------------------------------------- #
# 4) بريميوم/ديسكاونت (Premium/Discount) — من مدى التداول
# ----------------------------------------------------------------------------- #
def premium_discount(series: Series, left: int = 2, right: int = 2) -> dict:
    """
    قسّم مدى التداول (آخر قاع→قمة مهمّين): تحت 50% = خصم (شراء)، فوق = بريميوم.

    Splits the current dealing range at its 50% equilibrium. For longs we want
    price in DISCOUNT (below equilibrium) — buying value, not chasing premium.
    Returns {high, low, eq, pct, zone}.
    """
    highs, lows, closes = series.highs(), series.lows(), series.closes()
    ph, pl = ind.swing_points(highs, lows, left, right)
    if not ph or not pl or not closes:
        return {"high": None, "low": None, "eq": None, "pct": None, "zone": "unknown"}
    hi = ph[-1][1]
    lo = pl[-1][1]
    if hi <= lo:
        hi, lo = max(highs[-50:]), min(lows[-50:])
    rng = hi - lo
    if rng <= 0:
        return {"high": hi, "low": lo, "eq": hi, "pct": None, "zone": "unknown"}
    pct = (closes[-1] - lo) / rng
    zone = "discount" if pct < 0.5 else "premium"
    return {"high": hi, "low": lo, "eq": lo + rng / 2.0, "pct": pct, "zone": zone}


# ----------------------------------------------------------------------------- #
# 5) المُنسّق: حلّل رمزًا واحدًا عبر التسلسل الكامل (1D→4H→1H) وابنِ الصفقة
# ----------------------------------------------------------------------------- #
def _htf_bias(struct_1d: dict, struct_4h: dict) -> Tuple[str, float]:
    """HTF Bias من هيكل 1D + 4H. يُرجع (bias, score/20)."""
    b1, b4 = struct_1d["bias"], struct_4h["bias"]
    if b1 == "bullish" and b4 == "bullish":
        return "bullish", 20.0
    if b1 == "bearish" and b4 == "bearish":
        return "bearish", 20.0            # واضح لكنه ضدّنا (سبوت = لا شورت)
    if b1 == "bullish" and b4 != "bearish":
        return "bullish", 13.0            # اتجاه أعلى صاعد، الأوسط ليس ضدّه
    if b1 == "bullish" and b4 == "bearish":
        return "bullish", 8.0             # صاعد كبير لكن ارتداد أوسط — بيَاس أضعف
    if b1 == "bearish":
        return "bearish", 6.0
    return "ranging", 6.0


def analyze_ict(symbol: str, fetch_fn: Callable, market: str = "crypto") -> Optional[ICTSetup]:
    """
    حلّل رمزًا بمنهج ICT الكامل من شموع فعلية. يُرجع ICTSetup (بأي درجة) أو None لو
    البيانات ناقصة. القرار النهائي (يُقترح أم NO TRADE) عبر setup.is_tradeable.
    """
    try:
        d1 = fetch_fn(symbol, market, "1d", 260)
        h4 = fetch_fn(symbol, market, "4h", 300)
        h1 = fetch_fn(symbol, market, "1h", 320)
    except Exception:  # noqa: BLE001
        return None
    return analyze_ict_frames(symbol, market, d1, h4, h1)


def analyze_ict_frames(symbol: str, market: str, d1: Series, h4: Series,
                       h1: Series) -> Optional[ICTSetup]:
    """
    جوهر تحليل ICT من ثلاثة فريمات جاهزة (1D/4H/1H) — مفصول عن الجلب حتى يقدر
    الباك-تِست يغذّيه بشموع تاريخية مقطوعة (نقطة-في-الزمن) لقياس أدائه الحقيقي.
    """
    if not d1.candles or not h4.candles or not h1.candles:
        return None
    if len(h1.candles) < 60 or len(h4.candles) < 40 or len(d1.candles) < 30:
        return None

    price = h1.candles[-1].close
    atr1 = ind.atr(h1.highs(), h1.lows(), h1.closes(), 14) or (price * 0.01)

    # A) HTF ANALYSIS
    st_1d = market_structure(d1)
    st_4h = market_structure(h4)
    st_1h = market_structure(h1)
    bias, s_bias = _htf_bias(st_1d, st_4h)

    # B) LIQUIDITY ANALYSIS
    lv = prev_period_levels(d1)
    eq_h, eq_l = equal_levels(h4)
    pd = premium_discount(h4)
    # أهداف السيولة فوق السعر (buy-side): PDH/PWH + القمم المتساوية + قمة المدى
    buyside = [x for x in ([lv["pdh"], lv["pwh"]] + eq_h + [pd["high"]])
               if x and x > price]
    buyside = sorted(set(round(x, 10) for x in buyside))
    # سيولة أسفل (sell-side) المرشّحة للكنس: PDL/PWL + القيعان المتساوية
    sellside = [x for x in ([lv["pdl"], lv["pwl"]] + eq_l) if x and x < price]
    sellside = sorted(set(round(x, 10) for x in sellside), reverse=True)

    # C) PRICE DELIVERY (على 1H)
    disp_bull, _disp_bear, disp_str = displacement(h1)
    fvg = find_bullish_fvg(h1)
    ob = find_bullish_ob(h1)
    wick = wick_rejection(h1, bull=True)

    # كنس السيولة: هل كُنِس أقرب مستوى sell-side (stop-hunt) مؤخّرًا؟
    swept_level = None
    for lvl in sellside:
        if liquidity_sweep_of(h1, lvl):
            swept_level = lvl
            break
    # أو كنس قاع هيكل 1H (لو مفيش مستوى يومي/أسبوعي واضح)
    if swept_level is None and st_1h["last_pl"]:
        if liquidity_sweep_of(h1, st_1h["last_pl"]):
            swept_level = st_1h["last_pl"]

    # D) ENTRY MODEL — عدّة تأكيدات (لا دخول بمجرّد FVG/OB)
    zone = fvg or ob
    ltf_confirm = bool(st_1h["bias"] == "bullish" or st_1h["bos"] == "bullish"
                       or st_1h["choch"] == "bullish" or wick)

    # ------- SCORING /100 (نفس روبريك المستخدم بالضبط) -------
    bd = {}
    bd["HTF Bias"] = round(s_bias, 1)                              # /20

    # Liquidity /20: هدف واضح فوق + كنس سيولة تحت
    s_liq = 0.0
    if buyside:
        s_liq += 10.0
    if swept_level is not None:
        s_liq += 10.0
    bd["Liquidity"] = round(s_liq, 1)

    # Market Structure /15
    s_ms = 0.0
    if st_1h["bias"] == "bullish":
        s_ms += 9.0
    elif st_1h["bias"] == "ranging":
        s_ms += 4.0
    if st_1h["bos"] == "bullish" or st_1h["choch"] == "bullish":
        s_ms += 6.0
    bd["Market Structure"] = round(min(15.0, s_ms), 1)

    # Displacement /15 (متدرّج بقوّة الاندفاع)
    s_disp = 0.0
    if disp_bull:
        s_disp = 15.0 if disp_str >= 2.0 else (11.0 if disp_str >= 1.5 else 8.0)
    bd["Displacement"] = round(s_disp, 1)

    # FVG/OB /10
    s_zone = 0.0
    if fvg:
        s_zone += 6.0
    if ob:
        s_zone += 6.0
    if pd["zone"] == "discount":
        s_zone += 2.0                        # منطقة خصم = مكان دخول أفضل
    bd["FVG/OB"] = round(min(10.0, s_zone), 1)

    # Entry Confirmation /10
    s_conf = 0.0
    if ltf_confirm:
        s_conf += 6.0
    if wick:
        s_conf += 4.0
    bd["Entry Confirmation"] = round(min(10.0, s_conf), 1)

    # E) بناء الدخول/الوقف/الأهداف (سيتم حساب RR ثم منح نقاطه)
    entry = stop = tp1 = tp2 = tp3 = invalid = rr = 0.0
    entry_zone_txt = ""
    if zone is not None and bias == "bullish":
        entry = zone.mid
        # الوقف: تحت أدنى (منطقة الدخول / مستوى الكنس / قاع الهيكل) بمصدّ ATR
        floor_candidates = [zone.low]
        if swept_level is not None:
            floor_candidates.append(swept_level)
        if st_1h["last_pl"]:
            floor_candidates.append(st_1h["last_pl"])
        invalid = min(floor_candidates)
        stop = invalid - 0.25 * atr1
        # الأهداف من السيولة فوق (TP based on liquidity)
        tps = [x for x in buyside if x > entry][:3]
        risk = entry - stop
        while len(tps) < 3 and risk > 0:      # لو السيولة غير كافية، كمّل بمضاعفات R
            mult = 2.0 + len(tps)             # 2R, 3R, 4R
            tps.append(entry + mult * risk)
        tp1, tp2, tp3 = tps[0], tps[1], tps[2]
        if risk > 0:
            rr = (tp2 - entry) / risk         # RR تمثيلي إلى الهدف الأوسط
        entry_zone_txt = (f"{zone.kind.upper()} {zone.low:.6g}–{zone.high:.6g}"
                          f" ({pd['zone']})")

    # Risk/Reward /10
    s_rr = 0.0
    if rr >= 3.0:
        s_rr = 10.0
    elif rr >= 2.0:
        s_rr = 7.0
    elif rr >= 1.5:
        s_rr = 4.0
    bd["Risk/Reward"] = round(s_rr, 1)

    total = round(sum(bd.values()), 1)

    # أسباب الدخول / أسباب عدم الدخول (شفافية كاملة)
    reasons, blockers = [], []
    if bias == "bullish":
        reasons.append(f"HTF Bias صاعد (1D={st_1d['bias']}, 4H={st_4h['bias']})")
    else:
        blockers.append(f"HTF Bias غير صاعد (1D={st_1d['bias']}, 4H={st_4h['bias']}) "
                        "— والبوت سبوت (لا شورت) → NO TRADE")
    if swept_level is not None:
        reasons.append(f"كنس سيولة عند {swept_level:.6g} (stop-hunt ثم ارتداد)")
    else:
        blockers.append("لا كنس سيولة واضح قبل الدخول")
    if disp_bull:
        reasons.append(f"Displacement صاعد (قوة {disp_str:.1f}×ATR)")
    else:
        blockers.append("لا اندفاع (Displacement) صاعد حديث")
    if zone is not None:
        reasons.append(f"منطقة دخول {zone.kind.upper()} في {pd['zone']}")
    else:
        blockers.append("لا FVG/Order Block صالح للدخول")
    if ltf_confirm:
        reasons.append("تأكيد الفريم الأدنى (1H): هيكل/كسر/رفض صاعد")
    else:
        blockers.append("لا تأكيد من الفريم الأدنى (1H)")
    if buyside:
        reasons.append(f"هدف سيولة واضح فوق ({buyside[0]:.6g})")
    if pd["zone"] == "premium":
        blockers.append("السعر في Premium (فوق 50%) — ليس مكان شراء مثالي")

    liq_target = (f"buy-side {buyside[0]:.6g}"
                  + (f" → {buyside[-1]:.6g}" if len(buyside) > 1 else "")
                  if buyside else "غير محدّد")
    liq_sweep = (f"{swept_level:.6g} (تم الكنس)" if swept_level is not None
                 else "لم يحدث")

    return ICTSetup(
        symbol=symbol, market=market, price=price, htf_bias=bias,
        entry=entry, stop=stop, tp1=tp1, tp2=tp2, tp3=tp3, invalidation=invalid,
        rr=rr, score=total, breakdown=bd, liquidity_target=liq_target,
        liquidity_sweep=liq_sweep, entry_zone=entry_zone_txt,
        reasons=reasons, blockers=blockers, timeframe="1h",
    )


# ----------------------------------------------------------------------------- #
# 6) المُنسّق النصّي (Final Output) + الماسح على كل الكون
# ----------------------------------------------------------------------------- #
def _fmt(x) -> str:
    if x is None:
        return "—"
    ax = abs(x)
    if ax >= 1000:
        return f"{x:,.2f}"
    if ax >= 1:
        return f"{x:.4g}"
    return f"{x:.6g}"


def format_ict(s: ICTSetup, when: str = "") -> str:
    """اطبع نتيجة ICT بالشكل المطلوب بالضبط — أو NO TRADE مع الأسباب."""
    head = f"📊 ICT / Smart Money — {s.symbol}"
    if not s.is_tradeable:
        lines = [head, ""]
        lines.append("🚫 NO TRADE")
        lines.append(f"Setup Score: {s.score:.0f}/100 (الحدّ الأدنى {ICT_MIN_SCORE:.0f})")
        lines.append(f"HTF Bias: {s.htf_bias}")
        if s.blockers:
            lines.append("\nReasons NOT to Enter:")
            lines += [f"  • {b}" for b in s.blockers]
        lines.append("\nℹ️ الجودة قبل الكمية — لا نُجبر الصفقة. ننتظر إعدادًا ≥"
                     f"{ICT_MIN_SCORE:.0f}.")
        return "\n".join(lines)

    prob = ("عالية" if s.score >= 90 else "جيدة" if s.score >= 85 else "متوسطة-عالية")
    bd = s.breakdown
    lines = [
        head, "",
        f"Market: {s.symbol} ({s.market})",
        f"Time: {when or s.timeframe}",
        f"HTF Bias: {s.htf_bias} 🟢",
        f"Liquidity Target: {s.liquidity_target}",
        f"Liquidity Sweep: {s.liquidity_sweep}",
        f"Entry Zone: {s.entry_zone}",
        f"Entry: {_fmt(s.entry)}",
        f"SL: {_fmt(s.stop)}",
        f"TP1: {_fmt(s.tp1)}",
        f"TP2: {_fmt(s.tp2)}",
        f"TP3: {_fmt(s.tp3)}",
        f"Risk/Reward: 1:{s.rr:.1f} (إلى TP2)",
        f"Setup Score: {s.score:.0f}/100",
        f"Invalidation: {_fmt(s.invalidation)} (إغلاق تحته يُلغي الفكرة)",
        f"Probability Assessment: {prob} — ليست ضمانًا (لا صفقة ناجحة 100%)",
        "",
        "Score Breakdown:",
        f"  HTF Bias {bd.get('HTF Bias',0):.0f}/20 | Liquidity {bd.get('Liquidity',0):.0f}/20 | "
        f"Structure {bd.get('Market Structure',0):.0f}/15 | Displacement {bd.get('Displacement',0):.0f}/15",
        f"  FVG/OB {bd.get('FVG/OB',0):.0f}/10 | Entry Conf {bd.get('Entry Confirmation',0):.0f}/10 | "
        f"R/R {bd.get('Risk/Reward',0):.0f}/10",
        "",
        "Reason for Trade:",
    ]
    lines += [f"  • {r}" for r in s.reasons]
    if s.blockers:
        lines.append("\nReasons NOT to Enter (راقبها):")
        lines += [f"  • {b}" for b in s.blockers]
    lines.append("\n⚙️ Trade Management:")
    lines.append("  • حرّك SL لنقطة الدخول بعد أول هدف (TP1) → صفقة بلا خسارة.")
    lines.append("  • أغلق 1/3 عند TP1، و1/3 عند TP2، وسيّب الباقي لـTP3.")
    lines.append("  • فعّل Trailing Stop (تحت كل قاع 1H جديد) بعد TP2.")
    lines.append("  • ألغِ الصفقة لو أغلقت شمعة 1H تحت Invalidation قبل الدخول.")
    lines.append("  • لا تدخل لو السعر طار بعيدًا عن منطقة الدخول (مطاردة).")
    lines.append("\n⚠️ تعليمي فقط، ليس نصيحة مالية. استخدم وقف الخسارة دائمًا "
                 "ولا تخاطر بأكثر مما تتحمّل خسارته.")
    return "\n".join(lines)


def scan_ict(markets, fetch_fn, resolve_fn, limit_symbols: int = 0) -> Tuple[Optional[ICTSetup], List[ICTSetup]]:
    """
    امسح الكون كله بمنهج ICT وأرجع (أفضل صفقة ≥العتبة أو None، كل المرشّحين مرتّبين).

    Runs the full ICT analysis on every symbol, keeps only the tradeable ones
    (score ≥ MIN, entry/RR valid), and returns the single best plus the ranked
    list. Quality over quantity — most symbols return NO TRADE, by design.
    """
    setups: List[ICTSetup] = []
    for market in markets:
        syms = resolve_fn(market, "auto")
        if limit_symbols:
            syms = syms[:limit_symbols]
        for sym in syms:
            s = analyze_ict(sym, fetch_fn, market)
            if s is not None:
                setups.append(s)
    setups.sort(key=lambda x: x.score, reverse=True)
    tradeable = [s for s in setups if s.is_tradeable]
    best = tradeable[0] if tradeable else None
    return best, setups

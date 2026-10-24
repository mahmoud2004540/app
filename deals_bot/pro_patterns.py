"""
نماذج احترافية مُختبرة — الوتد الهابط (يومي)، القاع المزدوج (يومي)، العلم الصاعد (4 ساعات).

التعريفات على طريقة المحترفين (Bulkowski / Edwards & Magee / Lo-Mamaysky-Wang):
  - القمم والقيعان من ZigZag مبني على ATR: الارتكاز يتأكد بس لما السعر يبعد عنه 2×ATR
    (مفيش نظر للمستقبل).
  - التأكيد = أول إغلاق فوق خط التأكيد (خط العنق / الخط العلوي / قمة العمود).
  - الوقف تحت أوطى نقطة في النموذج، والهدف = قاعدة القياس (ارتفاع النموذج فوق الكسر).
  - بنشتغل بس والسوق صاعد (BTC فوق EMA200 على نفس الفريم).
  - مفيش صفقة وقفها أبعد من 15% (قاعدة مخاطرة احترافية — رفعت التوقّع في التلاتة).

مقاس على الكريبتو بعد الرسوم (0.2%) بنفس الخروج ده (+ سوق صاعد + وقف ≤ 15%):
  الوتد الهابط يومي: 123 صفقة، نجاح 57%، +0.63R، ثابت في نصّين الفترة (+0.86/+0.42).
  القاع المزدوج يومي: 33 صفقة، نجاح 79%، +0.35R (عيّنة صغيرة).
  العلم الصاعد 4 ساعات: 187 صفقة، نجاح 56%، +0.49R (+0.41/+0.55).

دوال نقية (بلا شبكة) — قابلة للاختبار والباك-تِست.
"""

from __future__ import annotations

from typing import Dict, List, Optional

K = 2.0                       # انعكاس الـ ZigZag = K × ATR
TF_SECONDS = {"4h": 14400, "1d": 86400}
# الأنماط المعتمدة لكل فريم (اللي اتثبت إنها بتكسب عليه)
PATTERNS_BY_TF = {"1d": ("Falling wedge", "Double bottom"), "4h": ("Bull flag",)}
NAMES_AR = {"Falling wedge": "الوتد الهابط", "Double bottom": "القاع المزدوج", "Bull flag": "العلم الصاعد"}
MEASURED = {  # (صفقات، نجاح، توقّع R) من الباك-تِست مع السوق الصاعد ووقف ≤ 15%
    "Falling wedge": (123, 0.57, 0.63), "Double bottom": (33, 0.79, 0.35), "Bull flag": (187, 0.56, 0.49),
}
MAX_STOP_PCT = 15.0           # مفيش صفقة وقفها أبعد من كده


def ema(x: List[float], n: int) -> List[float]:
    out = [x[0]]
    k = 2 / (n + 1)
    for v in x[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def atr(h: List[float], l: List[float], c: List[float], n: int = 14) -> List[float]:
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, len(c))]
    return ema(tr, 2 * n - 1)


def zigzag(h: List[float], l: List[float], A: List[float]) -> List[tuple]:
    """ارتكازات: (نوع 'H'/'L'، فهرس الارتكاز، السعر، فهرس التأكيد)."""
    sw = []
    d = 0
    ext, ei, exl, eli = h[0], 0, l[0], 0
    for i in range(1, len(h)):
        if d >= 0:
            if h[i] > ext:
                ext, ei = h[i], i
            if d == 0 and l[i] < exl:
                exl, eli = l[i], i
            if ext - l[i] >= K * A[i] and (d == 1 or ei > eli):
                sw.append(("H", ei, ext, i))
                d = -1
                exl, eli = l[i], i
                continue
        if d <= 0:
            if l[i] < exl:
                exl, eli = l[i], i
            if h[i] - exl >= K * A[i] and (d == -1 or eli > ei):
                sw.append(("L", eli, exl, i))
                d = 1
                ext, ei = h[i], i
    return sw


def _line_at(i1, p1, i2, p2, t):
    return p1 + (p2 - p1) / (i2 - i1) * (t - i1) if i2 != i1 else p2


def detect_at(sw: List[tuple], t: int, c: List[float], A: List[float], timeframe: str) -> List[dict]:
    """
    النماذج اللي اتكسرت عند الشمعة t (إغلاق t). sw = الارتكازات المؤكَّدة حتى t.
    يرجّع [{pattern, breakout, low, height}].
    """
    out: List[dict] = []
    wanted = PATTERNS_BY_TF.get(timeframe, ())
    if len(sw) < 3:
        return out
    tolp = max(0.015, 0.75 * A[t] / c[t])
    k = [x[0] for x in sw]
    ix = [x[1] for x in sw]
    px = [x[2] for x in sw]
    last_i = ix[-1]

    def fresh(level):
        if not (c[t] > level >= c[t - 1]):
            return False
        return t - 1 <= last_i or max(c[last_i + 1:t]) <= level

    def near(a, b, f=1.0):
        return abs(a - b) / ((a + b) / 2) <= tolp * f

    if k[-1] == "L" and len(sw) >= 4 and k[-4] == "H":
        if "Double bottom" in wanted:
            h0, l1, h1, l2 = px[-4:]
            if near(l1, l2) and 10 <= ix[-1] - ix[-3] <= 150 and h0 > h1:
                bot = min(l1, l2)
                ht = h1 - bot
                if ht / h1 >= 0.05 and fresh(h1):
                    out.append({"pattern": "Double bottom", "breakout": h1, "low": bot, "height": ht})
        if "Falling wedge" in wanted:
            h1, l1, h2, l2 = px[-4:]
            i_h1, i_l1, i_h2, i_l2 = ix[-4:]
            if i_l2 - i_h1 >= 10 and h2 < h1 and l2 < l1:
                sh = (h2 - h1) / (i_h2 - i_h1) / h1
                sl = (l2 - l1) / max(1, i_l2 - i_l1) / l1
                up = _line_at(i_h1, h1, i_h2, h2, t)
                if sh < sl < 0 and fresh(up):
                    out.append({"pattern": "Falling wedge", "breakout": up, "low": l2, "height": h1 - l2})
    if "Bull flag" in wanted and len(sw) >= 3 and k[-1] == "L" and k[-3] == "L":
        l0, h1, l1 = px[-3:]
        i0, i1, _ = ix[-3:]
        pole = h1 - l0
        if pole >= 5 * A[i1] and i1 - i0 <= 20 and (h1 - l1) <= 0.5 * pole and 3 <= t - i1 <= 30 and fresh(h1):
            out.append({"pattern": "Bull flag", "breakout": h1, "low": l1, "height": pole})
    return out


def signals(candles, timeframe: str, start: int = 210):
    """كل الكسرات في السلسلة (للباك-تِست): يولّد (t، نموذج، دخول، وقف، هدف)."""
    h = [x.high for x in candles]
    l = [x.low for x in candles]
    c = [x.close for x in candles]
    A = atr(h, l, c)
    sw = zigzag(h, l, A)
    ptr = 0
    for t in range(start, len(c)):
        while ptr < len(sw) and sw[ptr][3] <= t:
            ptr += 1
        for d in detect_at(sw[max(0, ptr - 8):ptr], t, c, A, timeframe):
            yield t, d["pattern"], c[t], d["low"] - 0.25 * A[t], d["breakout"] + d["height"]


def market_bullish(btc_daily_candles) -> Optional[bool]:
    """BTC فوق EMA200 على آخر شمعة يومية مقفولة."""
    c = [x.close for x in btc_daily_candles]
    if len(c) < 200:
        return None
    return c[-1] > ema(c, 200)[-1]


def recent_setups(candles, timeframe: str, now_ts: float, max_age: int = 2) -> List[dict]:
    """
    الكسرات اللي حصلت في آخر max_age شمعة مقفولة، والسعر لسه مناسب للدخول
    (فوق الوقف، تحت الهدف، مش طالع أكتر من 0.5×ATR فوق سعر الكسر، والوقف ≤ 15%).
    """
    step = TF_SECONDS.get(timeframe, 86400)
    cs = [x for x in candles if x.ts + step <= now_ts]
    if len(cs) < 220:
        return []
    c = [x.close for x in cs]
    h = [x.high for x in cs]
    l = [x.low for x in cs]
    A = atr(h, l, c)
    n = len(cs)
    out = []
    for t, name, entry, stop, target in signals(cs, timeframe, start=max(210, n - 1 - max_age)):
        last = c[-1]
        if not (stop < last < target) or last > entry + 0.5 * A[-1]:
            continue
        risk = last - stop
        if risk / last * 100 > MAX_STOP_PCT:
            continue
        out.append({
            "symbol": "", "timeframe": timeframe, "pattern": name, "breakout_close": entry,
            "entry": last, "stop": stop, "target": target, "rr": (target - last) / risk,
            "risk_pct": risk / last * 100, "target_pct": (target / last - 1) * 100,
            "bars_ago": n - 1 - t, "breakout_ts": cs[t].ts,
        })
    return out


def _px(x: float) -> str:
    return f"{x:,.2f}" if x >= 1000 else (f"{x:.4f}" if x >= 1 else f"{x:.6g}")


def format_setup(d: Dict) -> str:
    n, wr, er = MEASURED[d["pattern"]]
    pair = d["symbol"].replace("-USD", "USDT")
    when = "على الشمعة الأخيرة" if d["bars_ago"] == 0 else f"من {d['bars_ago']} شمعة"
    return (
        f"📐 {NAMES_AR[d['pattern']]} — {pair} ({d['timeframe'].upper()})\n"
        f"اتأكد بإغلاق فوق خط الكسر {when}\n"
        f"🎯 الدخول: {_px(d['entry'])}\n"
        f"🛑 الوقف: {_px(d['stop'])} (−{d['risk_pct']:.1f}%) — تحت أوطى نقطة في النموذج\n"
        f"✅ الهدف المقاس: {_px(d['target'])} (+{d['target_pct']:.1f}%)\n"
        f"⚖️ العائد/المخاطرة: 1:{d['rr']:.1f}\n"
        f"📊 تاريخيًا (سوق صاعد): {n} صفقة، نجاح {wr:.0%}، متوسط {er:+.2f}R"
    )

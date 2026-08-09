"""
محرّك تقاطع الأدلة (Confluence) — قرار مبني على اتفاق عدة مدارس تحليلية.

Multi-school confluence engine. Each "school" that can be computed from OHLCV
data returns a directional verdict (bull / bear / neutral); schools that need
data we cannot fetch for free are reported as UNAVAILABLE rather than guessed
(per the risk rules). The decision comes from how many available schools agree.

Automatable here: Technical, Price-Action/Structure, Volume, Quantitative, and
(crypto) Sentiment via the Fear & Greed index. Not automatable for free and
marked unavailable: Fundamental, Macro/Intermarket, On-chain, COT, order-book /
funding depth, and reliable Elliott/Gann counts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from . import indicators as ind
from .models import Series

# إدارة المخاطر (غير قابلة للتفاوض)
RISK_PER_TRADE = 0.01     # 1% من المحفظة
MIN_RR = 2.0              # لا تقل نسبة العائد/المخاطرة عن 1:2
STOP_ATR = 1.5
T1_ATR = 3.0             # الهدف الأول (يحقّق ≥ 1:2 مع وقف 1.5 ATR)
T2_ATR = 5.0             # الهدف الثاني


@dataclass
class School:
    name: str
    available: bool
    direction: str = "n/a"        # "bull" | "bear" | "neutral" | "n/a"
    note: str = ""


@dataclass
class ConfluenceReport:
    symbol: str
    market: str
    timeframe: str
    price: float
    schools: List[School] = field(default_factory=list)
    agree_bull: int = 0
    agree_bear: int = 0
    available_count: int = 0
    decision: str = "انتظار"           # شراء | بيع | انتظار
    entry: float = 0.0
    stop_loss: float = 0.0
    targets: List[float] = field(default_factory=list)
    risk_reward: float = 0.0
    position_pct: float = 0.0
    confidence: str = "منخفض"          # منخفض | متوسط | عالٍ
    evidence_count: int = 0
    alternative: str = ""
    notes: List[str] = field(default_factory=list)


def _sign(net: float) -> str:
    if net > 0:
        return "bull"
    if net < 0:
        return "bear"
    return "neutral"


def _school_technical(closes, highs, lows) -> School:
    net = 0.0
    parts = []
    e9, e21, e50 = ind.ema(closes, 9), ind.ema(closes, 21), ind.ema(closes, 50)
    if e9 and e21 and e50:
        if e9 > e21 > e50:
            net += 2; parts.append("EMA متصاعدة")
        elif e9 < e21 < e50:
            net -= 2; parts.append("EMA متهابطة")
        elif e9 > e21:
            net += 1
        elif e9 < e21:
            net -= 1
    rsi = ind.rsi(closes, 14)
    if rsi is not None:
        if rsi >= 55:
            net += 1; parts.append(f"RSI {rsi:.0f}")
        elif rsi <= 45:
            net -= 1; parts.append(f"RSI {rsi:.0f}")
    macd = ind.macd(closes)
    if macd:
        net += 1 if macd[2] > 0 else -1
        parts.append("MACD " + ("+" if macd[2] > 0 else "−"))
    bb = ind.bollinger(closes, 20)
    if bb:
        low, mid, up = bb
        if closes[-1] > mid:
            net += 1
        else:
            net -= 1
        if closes[-1] >= up:
            parts.append("عند الحد العلوي (تشبّع)")
        elif closes[-1] <= low:
            parts.append("عند الحد السفلي (تشبّع بيعي)")
    st = ind.stochastic(highs, lows, closes, 14)
    if st is not None:
        net += 1 if st > 50 else -1
        parts.append(f"ستوكاستك {st:.0f}")
    note = "، ".join(parts) if parts else "بيانات محدودة"
    return School("فني", True, _sign(net), note)


def _school_structure(highs, lows, closes) -> School:
    ph, pl = ind.swing_points(highs, lows, 2, 2)
    if len(ph) < 2 or len(pl) < 2:
        return School("حركة سعر/بنية", True, "neutral", "بنية غير واضحة بعد")
    hh = ph[-1][1] > ph[-2][1]
    hl = pl[-1][1] > pl[-2][1]
    lh = ph[-1][1] < ph[-2][1]
    ll = pl[-1][1] < pl[-2][1]
    price = closes[-1]
    bos = ""
    if price > ph[-1][1]:
        bos = " + كسر بنية صاعد (BOS)"
    elif price < pl[-1][1]:
        bos = " + كسر بنية هابط (BOS)"
    if hh and hl:
        return School("حركة سعر/بنية", True, "bull", "قمم وقيعان صاعدة (HH/HL)" + bos)
    if lh and ll:
        return School("حركة سعر/بنية", True, "bear", "قمم وقيعان هابطة (LH/LL)" + bos)
    return School("حركة سعر/بنية", True, "neutral", "نطاق عرضي" + bos)


def _poc(highs, lows, closes, volumes, bins: int = 20) -> Optional[float]:
    """نقطة التحكم (POC): مستوى السعر الأكثر تداولًا (تقريبيًا من الحجم)."""
    n = len(closes)
    if n < 30:
        return None
    lo, hi = min(lows[-100:]), max(highs[-100:])
    if hi <= lo:
        return None
    width = (hi - lo) / bins
    buckets = [0.0] * bins
    for i in range(max(0, n - 100), n):
        idx = min(bins - 1, int((closes[i] - lo) / width))
        buckets[idx] += volumes[i]
    top = buckets.index(max(buckets))
    return lo + (top + 0.5) * width


def _school_volume(highs, lows, closes, volumes) -> School:
    if sum(volumes[-20:]) == 0:
        return School("حجم/تدفق أوامر", False, "n/a",
                      "لا يتوفّر حجم موثوق (شائع في الفوركس)")
    net = 0.0
    parts = []
    vs = ind.volume_surge(volumes, 20)
    if vs is not None and vs > 1.3:
        up = closes[-1] >= closes[-2]
        net += 1 if up else -1
        parts.append(f"حجم ×{vs:.1f}")
    mfi = ind.mfi(highs, lows, closes, volumes, 14)
    if mfi is not None:
        if mfi >= 55:
            net += 1; parts.append(f"MFI {mfi:.0f}")
        elif mfi <= 45:
            net -= 1; parts.append(f"MFI {mfi:.0f}")
    poc = _poc(highs, lows, closes, volumes)
    if poc:
        if closes[-1] > poc:
            net += 1; parts.append("فوق POC")
        else:
            net -= 1; parts.append("تحت POC")
    parts.append("دفتر الأوامر/التمويل غير متوفّر")
    return School("حجم/تدفق أوامر", True, _sign(net), "، ".join(parts))


def _school_quant(closes, highs, lows) -> School:
    mom = ind.momentum_pct(closes, 10)
    atr = ind.atr(highs, lows, closes, 14)
    parts = []
    net = 0.0
    if mom is not None:
        net += 1 if mom > 1.0 else (-1 if mom < -1.0 else 0)
        parts.append(f"زخم {mom:+.1f}%")
    if atr and closes[-1]:
        atr_pct = atr / closes[-1] * 100
        parts.append(f"تذبذب ATR {atr_pct:.1f}%")
    return School("كمّي", True, _sign(net), "، ".join(parts) if parts else "—")


def _school_sentiment(market: str, fear_greed: Optional[int]) -> School:
    if market != "crypto" or fear_greed is None:
        return School("مشاعر", False, "n/a",
                      "مؤشر الخوف/الطمع وCOT ونسب Long/Short غير متوفّرة")
    if fear_greed <= 25:
        return School("مشاعر", True, "bull", f"خوف شديد ({fear_greed}) — فرصة عكسية")
    if fear_greed >= 75:
        return School("مشاعر", True, "bear", f"طمع شديد ({fear_greed}) — حذر من التصحيح")
    return School("مشاعر", True, "neutral", f"محايد ({fear_greed})")


def _unavailable_schools(market: str) -> List[School]:
    out = [
        School("أساسي", False, "n/a", "الأرباح/الميزانية غير متاحة آليًا مجانًا"),
        School("كلّي/بيني", False, "n/a", "التقويم الاقتصادي والارتباطات غير متوفّرة"),
        School("إليوت/جان", False, "n/a", "يصعب أتمتة العدّ بدقة — يحتاج مراجعة يدوية"),
    ]
    if market == "crypto":
        out.append(School("أونشين", False, "n/a", "MVRV/SOPR/تدفّقات المنصات تحتاج اشتراكًا"))
    return out


def analyze_confluence(
    series: Series,
    timeframe: str = "1h",
    fear_greed: Optional[int] = None,
    balance_risk_pct: float = RISK_PER_TRADE,
) -> ConfluenceReport:
    """حلّل أصلًا واحدًا عبر كل المدارس المتاحة وابنِ قرار تقاطع الأدلة."""
    closes, highs, lows, vols = series.closes(), series.highs(), series.lows(), series.volumes()
    price = closes[-1] if closes else 0.0
    rep = ConfluenceReport(series.symbol, series.market, timeframe, price)

    if len(closes) < 60:
        rep.notes.append("بيانات غير كافية (نحتاج 60 شمعة على الأقل).")
        return rep

    schools = [
        _school_technical(closes, highs, lows),
        _school_structure(highs, lows, closes),
        _school_volume(highs, lows, closes, vols),
        _school_quant(closes, highs, lows),
        _school_sentiment(series.market, fear_greed),
    ]
    schools += _unavailable_schools(series.market)
    rep.schools = schools

    avail = [s for s in schools if s.available and s.direction in ("bull", "bear", "neutral")]
    rep.available_count = len(avail)
    rep.agree_bull = sum(1 for s in avail if s.direction == "bull")
    rep.agree_bear = sum(1 for s in avail if s.direction == "bear")

    atr = ind.atr(highs, lows, closes, 14) or (price * 0.01)

    # القرار: يتطلّب تفوّق واضح (تقاطع) — وإلا انتظار
    diff = rep.agree_bull - rep.agree_bear
    if diff >= 2:
        rep.decision = "شراء"
        rep.entry = price
        rep.stop_loss = price - STOP_ATR * atr
        rep.targets = [price + T1_ATR * atr, price + T2_ATR * atr]
        rep.evidence_count = rep.agree_bull
        rep.alternative = (
            f"إبطال الفكرة بإغلاق تحت {rep.stop_loss:.6g} → انقلاب لهبوط "
            "واستهداف القاع السابق."
        )
    elif diff <= -2:
        rep.decision = "بيع"
        rep.entry = price
        rep.stop_loss = price + STOP_ATR * atr
        rep.targets = [price - T1_ATR * atr, price - T2_ATR * atr]
        rep.evidence_count = rep.agree_bear
        rep.alternative = (
            f"إبطال الفكرة بإغلاق فوق {rep.stop_loss:.6g} → انقلاب لصعود."
        )
    else:
        rep.decision = "انتظار"
        rep.notes.append("لا يوجد تقاطع أدلة كافٍ (تعارض/حياد بين المدارس) — لا صفقة.")
        rep.confidence = "منخفض"
        return rep

    risk = abs(rep.entry - rep.stop_loss)
    reward = abs(rep.targets[0] - rep.entry)
    rep.risk_reward = round((reward / risk) if risk > 0 else 0.0, 2)

    # بوابة إدارة المخاطر: لا تقل عن 1:2
    if rep.risk_reward < MIN_RR:
        rep.notes.append(
            f"نسبة العائد/المخاطرة ({rep.risk_reward}) أقل من 1:{MIN_RR:.0f} — "
            "يفضّل الانتظار لدخول أفضل أو تقليل الحجم."
        )

    # الثقة حسب عدد المدارس المتفقة
    agree = max(rep.agree_bull, rep.agree_bear)
    if agree >= 4 and rep.risk_reward >= MIN_RR:
        rep.confidence = "عالٍ"
    elif agree >= 3:
        rep.confidence = "متوسط"
    else:
        rep.confidence = "منخفض"

    # حجم المركز: مخاطرة ثابتة من المحفظة
    rep.position_pct = round(balance_risk_pct * 100, 2)

    return rep

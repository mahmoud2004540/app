"""
نماذج كلاسيكية: القاع المزدوج (Double Bottom).

النموذج: هبوط → قاع أول → ارتداد لقمّة (خط العنق) → قاع تاني قريب من الأول →
كسر خط العنق لفوق → (غالبًا) رجوع لاختباره من فوق ← هنا الدخول.
الهدف المقاس = خط العنق + ارتفاع النموذج (من أعمق قاع لخط العنق).

Pure functions (no network) so they can be tested and backtested offline.
"""

from __future__ import annotations

from typing import List, Optional

from . import indicators as ind
from .models import Series

TF_SECONDS = {"1h": 3600, "4h": 14400, "6h": 21600, "1d": 86400}


def closed(series: Series, timeframe: str, now_ts: Optional[float]) -> Series:
    """احذف الشمعة اللي لسه مفتوحة (القرار على شموع مقفولة بس)."""
    if now_ts is None:
        return series
    step = TF_SECONDS.get(timeframe, 86400)
    return Series(series.symbol, series.market, [c for c in series.candles if c.ts + step <= now_ts])


def detect_double_bottom(series: Series, timeframe: str = "1d", now_ts: Optional[float] = None,
                         tol: float = 0.06, min_gap: int = 10, max_gap: int = 150,
                         min_height: float = 0.10, max_breakout_age: int = 60,
                         pivot: int = 5) -> Optional[dict]:
    """
    ابحث عن قاع مزدوج مكسور خط عنقه والسعر حاليًا في منطقة إعادة الاختبار.

    الشروط:
      - قاعين (نقاط ارتكاز) الفرق بينهم ≤ tol، والمسافة بينهم min_gap..max_gap شمعة.
      - مفيش قاع أوطى منهم بينهم، وقبل القاع الأول كان السعر أعلى من خط العنق (هبوط سابق).
      - ارتفاع النموذج ≥ min_height من خط العنق.
      - إغلاق فوق خط العنق بعد القاع التاني، خلال آخر max_breakout_age شمعة،
        ومن ساعتها ما قفلش تحت نص النموذج (وإلا النموذج فشل).
      - السعر الحالي بين 96% من خط العنق و خط العنق + 30% من الارتفاع (مش متمدّد).
    يرجّع dict بالدخول/الوقف/الأهداف والدرجة، أو None.
    """
    s = closed(series, timeframe, now_ts)
    c = s.candles
    n = len(c)
    if n < 80:
        return None
    highs, lows, closes, vols = s.highs(), s.lows(), s.closes(), s.volumes()
    ph, pl = ind.swing_points(highs, lows, pivot, pivot)
    a = ind.atr(highs, lows, closes, 14)
    if not a:
        return None
    last = closes[-1]
    best = None
    for k in range(len(pl) - 1, 0, -1):
        i2, l2 = pl[k]
        if n - 1 - i2 > max_gap + max_breakout_age:
            break
        for j in range(k - 1, -1, -1):
            i1, l1 = pl[j]
            gap = i2 - i1
            if gap < min_gap:
                continue
            if gap > max_gap:
                break
            if abs(l2 - l1) / l1 > tol:
                continue
            bottom = min(l1, l2)
            if min(lows[i1:i2 + 1]) < bottom - 1e-12:
                continue                                  # فيه قاع أوطى بينهم
            neck = max(highs[i1:i2 + 1])
            height = neck - bottom
            if height / neck < min_height:
                continue
            pre = highs[max(0, i1 - 60):i1]
            if not pre or max(pre) < neck:
                continue                                  # مفيش هبوط قبل النموذج
            # الكسر: أول إغلاق فوق خط العنق بعد القاع التاني
            b = next((t for t in range(i2 + 1, n) if closes[t] > neck), None)
            if b is None or n - 1 - b > max_breakout_age:
                continue
            if min(closes[b:]) < neck - 0.5 * height:
                continue                                  # النموذج فشل
            if not (neck * 0.96 <= last <= neck + 0.30 * height):
                continue                                  # بعيد عن منطقة إعادة الاختبار
            retest_low = min(lows[b:])
            stop = min(retest_low, neck * 0.96) - 0.5 * a
            risk = last - stop
            if risk <= 0:
                continue
            tp1 = neck + 0.5 * height
            tp2 = neck + height
            rr = (tp2 - last) / risk
            if rr < 2.0:
                continue
            # الدرجة: تطابق القاعين، القاع التاني أعلى، فوليوم الكسر، تباعد RSI
            score = 60
            score += 10 if abs(l2 - l1) / l1 <= tol / 2 else 0
            score += 10 if l2 >= l1 else 0
            avg_v = sum(vols[max(0, b - 20):b]) / max(1, len(vols[max(0, b - 20):b]))
            score += 10 if avg_v > 0 and vols[b] > 1.5 * avg_v else 0
            r1 = ind.rsi(closes[:i1 + 1], 14)
            r2 = ind.rsi(closes[:i2 + 1], 14)
            score += 10 if r1 is not None and r2 is not None and r2 > r1 else 0
            cand = {
                "symbol": s.symbol, "market": s.market, "timeframe": timeframe,
                "bottom1": l1, "bottom2": l2, "neck": neck, "height": height,
                "entry": last, "stop": stop, "tp1": tp1, "tp2": tp2, "rr": rr,
                "score": score, "breakout_ago": n - 1 - b, "signal_ts": c[-1].ts,
                "target_pct": (tp2 / last - 1) * 100,
            }
            if best is None or cand["score"] > best["score"]:
                best = cand
        if best:
            break
    return best


def _px(x: float) -> str:
    return f"{x:,.2f}" if x >= 1000 else (f"{x:.4f}" if x >= 1 else f"{x:.6g}")


def format_double_bottom(d: dict) -> str:
    pair = d["symbol"].replace("-USD", "USDT") if d["market"] == "crypto" else d["symbol"]
    risk_pct = (d["entry"] - d["stop"]) / d["entry"] * 100
    return (
        f"📐 قاع مزدوج — {pair} ({d['timeframe'].upper()})\n"
        f"القاعين: {_px(d['bottom1'])} و {_px(d['bottom2'])} | خط العنق: {_px(d['neck'])}\n"
        f"اتكسر خط العنق من {d['breakout_ago']} شمعة — السعر دلوقتي في منطقة إعادة الاختبار\n"
        f"🎯 الدخول: {_px(d['entry'])}\n"
        f"🛑 وقف الخسارة: {_px(d['stop'])} (−{risk_pct:.1f}%)\n"
        f"✅ TP1: {_px(d['tp1'])} (نص النموذج — انقل الوقف للدخول)\n"
        f"✅ TP2: {_px(d['tp2'])} (الهدف المقاس +{d['target_pct']:.0f}%)\n"
        f"⚖️ العائد/المخاطرة: 1:{d['rr']:.1f} | 🔒 الدرجة: {d['score']}/100"
    )

"""
جلب تاريخ مُعدّل التمويل (Funding Rate) من OKX — لقياس هل يضيف ميزة للبوت.

⚠️ للقياس فقط (backtest)، لا يُستدعى في المسار الحيّ قبل ما نثبت بالأرقام إنه
يرفع التوقّع. Funding = تكلفة/عائد الاحتفاظ بعقد دائم (perp): موجب = المضاربون
على الصعود يدفعون (ازدحام على الشراء)، سالب = العكس. الفرضية: الازدحام المتطرّف
غالبًا يسبق تصحيحًا، فقد يكون فلترًا مفيدًا. نقيسها، لا نفترضها.

المصدر: OKX يوصل من السيرفر (أثبتناه في fundingprobe). endpoint عام بلا مفتاح:
    /api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP&limit=100&after=<ms>
الترقيم للخلف: نمرّر after=أقدم fundingTime رأيناه، ونكرّر حتى ننتهي.
"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

_OKX_HIST = "https://www.okx.com/api/v5/public/funding-rate-history"
_HEADERS = {"User-Agent": "Mozilla/5.0"}


def symbol_to_okx_inst(symbol: str) -> Optional[str]:
    """'BTC-USD' → 'BTC-USDT-SWAP' (عقد OKX الدائم). None لو الصيغة غير مفهومة."""
    if not symbol:
        return None
    base = symbol.split("-")[0].strip().upper()
    if not base:
        return None
    return f"{base}-USDT-SWAP"


def _get_json(url: str, timeout: int = 15) -> Optional[dict]:
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001 - الجلب best-effort؛ نتعامل مع الفشل بالخارج
        return None


def fetch_funding_history(
    symbol: str,
    max_pages: int = 40,
    pause: float = 0.12,
) -> List[Tuple[float, float]]:
    """
    يرجّع تاريخ funding لعملة كـ [(ts_seconds, rate), ...] مرتّبًا تصاعديًا بالزمن.

    max_pages صفحة × 100 سجلّ × 8 ساعات ≈ يغطّي حتى ~1300 يوم كحدّ أقصى.
    قائمة فارغة = العملة ليس لها عقد OKX دائم أو الجلب فشل (نتعامل بأمان).
    """
    inst = symbol_to_okx_inst(symbol)
    if not inst:
        return []
    out: Dict[int, float] = {}
    after: Optional[int] = None  # fundingTime (ms) — نطلب أقدم منه
    for _ in range(max_pages):
        url = f"{_OKX_HIST}?instId={inst}&limit=100"
        if after is not None:
            url += f"&after={after}"
        body = _get_json(url)
        if not body or body.get("code") != "0":
            break
        rows = body.get("data") or []
        if not rows:
            break
        oldest = None
        for r in rows:
            try:
                ft = int(r["fundingTime"])          # ms
                rate = float(r["fundingRate"])
            except (KeyError, TypeError, ValueError):
                continue
            out[ft] = rate
            if oldest is None or ft < oldest:
                oldest = ft
        if oldest is None:
            break
        # نتقدّم للخلف: الصفحة التالية أقدم من أقدم سجلّ في الحالية
        if after is not None and oldest >= after:
            break  # حماية من حلقة لا نهائية
        after = oldest
        if len(rows) < 100:
            break  # وصلنا لبداية التاريخ المتاح
        time.sleep(pause)
    return sorted((ft / 1000.0, rate) for ft, rate in out.items())


class FundingLookup:
    """
    بحث سريع: عند توقيت دخول صفقة (ثوانٍ)، ما هو آخر funding سارٍ قبله؟

    نستخدم «آخر funding نُشر قبل الدخول» (لا تسريب مستقبلي: القيمة كانت معروفة
    وقت الدخول فعلًا).
    """

    def __init__(self, series: List[Tuple[float, float]]):
        self._ts = [t for t, _ in series]
        self._rate = [r for _, r in series]

    def __len__(self) -> int:
        return len(self._ts)

    def at(self, entry_ts: float) -> Optional[float]:
        """آخر معدّل funding نُشر عند/قبل entry_ts. None لو مفيش تاريخ سابق."""
        import bisect
        if not self._ts:
            return None
        idx = bisect.bisect_right(self._ts, entry_ts) - 1
        if idx < 0:
            return None
        return self._rate[idx]


def build_lookup(symbol: str, **kw) -> FundingLookup:
    """اختصار: اجلب التاريخ وابنِ باحثًا جاهزًا."""
    return FundingLookup(fetch_funding_history(symbol, **kw))

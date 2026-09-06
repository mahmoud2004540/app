"""
جالبات بيانات إضافية للقياس فقط (backtest): العقود المفتوحة (OI) ونشاط الشبكة
(on-chain). كلها مصادر عامة بلا مفتاح، أثبتنا وصولها + توفّر تاريخها في
datasourceprobe. لا تُستدعى حيًّا قبل ما نثبت بالأرقام إنها ترفع التوقّع.

بنفس أسلوب deals_bot/funding.py: نجلب سلسلة زمنية ونبني باحثًا بلا تسريب مستقبلي
(آخر قيمة معروفة عند/قبل توقيت الدخول).
"""

from __future__ import annotations

import bisect
import json
import time
import urllib.request
from typing import List, Optional, Tuple

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_OKX_OI = "https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-volume"
_BC_CHART = "https://api.blockchain.info/charts"


def _get_json(url: str, timeout: int = 15) -> Optional[dict]:
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001 - best-effort؛ نتعامل بالخارج
        return None


class SeriesLookup:
    """بحث بلا تسريب مستقبلي: آخر قيمة نُشرت عند/قبل توقيت الدخول (ثوانٍ)."""

    def __init__(self, series: List[Tuple[float, float]]):
        series = sorted(series)
        self._ts = [t for t, _ in series]
        self._val = [v for _, v in series]

    def __len__(self) -> int:
        return len(self._ts)

    def at(self, entry_ts: float) -> Optional[float]:
        if not self._ts:
            return None
        idx = bisect.bisect_right(self._ts, entry_ts) - 1
        if idx < 0:
            return None
        return self._val[idx]

    def change_at(self, entry_ts: float, lookback: int = 1) -> Optional[float]:
        """التغيّر النسبي للقيمة عند الدخول مقابل lookback نقطة قبلها (%)."""
        if not self._ts:
            return None
        idx = bisect.bisect_right(self._ts, entry_ts) - 1
        if idx - lookback < 0:
            return None
        prev = self._val[idx - lookback]
        if prev == 0:
            return None
        return (self._val[idx] / prev - 1.0) * 100.0


# ── العقود المفتوحة Open Interest (OKX rubik) ──────────────────────────────── #
def symbol_to_ccy(symbol: str) -> Optional[str]:
    """'BTC-USD' → 'BTC'."""
    if not symbol:
        return None
    base = symbol.split("-")[0].strip().upper()
    return base or None


def fetch_oi_history(symbol: str, period: str = "1D") -> List[Tuple[float, float]]:
    """
    تاريخ OI لعملة كـ [(ts_seconds, oi), ...] تصاعديًا. قائمة فارغة = لا بيانات.

    OKX يرجّع data كمصفوفات [ts_ms, oi, volume] (الأحدث أولًا).
    """
    ccy = symbol_to_ccy(symbol)
    if not ccy:
        return []
    body = _get_json(f"{_OKX_OI}?ccy={ccy}&period={period}")
    if not body or body.get("code") != "0":
        return []
    out: List[Tuple[float, float]] = []
    for row in body.get("data") or []:
        try:
            ts = float(row[0]) / 1000.0
            oi = float(row[1])
        except (IndexError, TypeError, ValueError):
            continue
        out.append((ts, oi))
    return sorted(out)


def build_oi_lookup(symbol: str, **kw) -> SeriesLookup:
    return SeriesLookup(fetch_oi_history(symbol, **kw))


# ── نشاط الشبكة On-chain (blockchain.com) ─────────────────────────────────── #
def fetch_onchain_series(chart: str, timespan: str = "3years") -> List[Tuple[float, float]]:
    """
    سلسلة on-chain عامة لشبكة BTC كـ [(ts_seconds, value), ...] تصاعديًا.

    chart أمثلة: 'n-transactions' (عدد المعاملات)، 'n-unique-addresses'
    (العناوين النشطة). سلسلة واحدة للشبكة كلها (تُستخدم كنظام سوق عام لا لكل عملة).
    """
    url = f"{_BC_CHART}/{chart}?timespan={timespan}&format=json&sampled=true"
    body = _get_json(url, timeout=25)
    if not body or "values" not in body:
        return []
    out: List[Tuple[float, float]] = []
    for pt in body.get("values") or []:
        try:
            out.append((float(pt["x"]), float(pt["y"])))
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(out)


def build_onchain_lookup(chart: str, **kw) -> SeriesLookup:
    return SeriesLookup(fetch_onchain_series(chart, **kw))

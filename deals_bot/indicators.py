"""
مؤشرات فنية مكتوبة ببايثون نقي (بدون مكتبات ثقيلة مثل TA-Lib).

Pure-Python technical indicators. Each function takes a list of floats and
returns either a single latest value or a full series. Kept dependency-free so
the analysis engine can be unit-tested offline without pandas/numpy.
"""

from __future__ import annotations

from typing import List, Optional, Tuple


def sma(values: List[float], period: int) -> Optional[float]:
    """المتوسط المتحرك البسيط لآخر `period` قيمة."""
    if period <= 0 or len(values) < period:
        return None
    window = values[-period:]
    return sum(window) / period


def ema_series(values: List[float], period: int) -> List[float]:
    """
    سلسلة المتوسط المتحرك الأسّي.

    Returns an EMA value for each input point (seeded with an SMA of the first
    `period` values, standard convention). Length == len(values); leading
    points before the seed are filled with the seed value.
    """
    if period <= 0 or len(values) < period:
        return []
    k = 2.0 / (period + 1)
    seed = sum(values[:period]) / period
    out: List[float] = [seed] * period
    prev = seed
    for v in values[period:]:
        prev = v * k + prev * (1 - k)
        out.append(prev)
    return out


def ema(values: List[float], period: int) -> Optional[float]:
    """أحدث قيمة للمتوسط المتحرك الأسّي."""
    s = ema_series(values, period)
    return s[-1] if s else None


def rsi(values: List[float], period: int = 14) -> Optional[float]:
    """
    مؤشر القوة النسبية (RSI) بطريقة Wilder للتنعيم.

    Returns latest RSI in 0..100, or None if not enough data.
    """
    if len(values) < period + 1:
        return None

    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        delta = values[i] - values[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain = gains / period
    avg_loss = losses / period

    for i in range(period + 1, len(values)):
        delta = values[i] - values[i - 1]
        gain = delta if delta > 0 else 0.0
        loss = -delta if delta < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd(
    values: List[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Optional[Tuple[float, float, float]]:
    """
    مؤشر MACD.

    Returns (macd_line, signal_line, histogram) using the latest values,
    or None if there is not enough data.
    """
    if len(values) < slow + signal:
        return None
    fast_s = ema_series(values, fast)
    slow_s = ema_series(values, slow)
    if not fast_s or not slow_s:
        return None
    # align lengths (both are len(values))
    macd_line_series = [f - s for f, s in zip(fast_s, slow_s)]
    signal_series = ema_series(macd_line_series, signal)
    if not signal_series:
        return None
    macd_line = macd_line_series[-1]
    signal_line = signal_series[-1]
    return macd_line, signal_line, macd_line - signal_line


def macd_hist_rising(values: List[float]) -> bool:
    """هل هيستوجرام الـ MACD في صعود (آخر قيمة أكبر من التي قبلها)؟"""
    fast_s = ema_series(values, 12)
    slow_s = ema_series(values, 26)
    if len(fast_s) < 2 or len(slow_s) < 2:
        return False
    line = [f - s for f, s in zip(fast_s, slow_s)]
    sig = ema_series(line, 9)
    if len(sig) < 2:
        return False
    hist = [l - s for l, s in zip(line, sig)]
    return hist[-1] > hist[-2]


def atr(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 14,
) -> Optional[float]:
    """
    متوسط المدى الحقيقي (ATR) — مقياس للتذبذب، يُستخدم لحساب وقف الخسارة.

    Wilder's Average True Range. Returns latest ATR or None.
    """
    n = len(closes)
    if n < period + 1 or len(highs) != n or len(lows) != n:
        return None

    trs: List[float] = []
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)

    if len(trs) < period:
        return None

    atr_val = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr_val = (atr_val * (period - 1) + tr) / period
    return atr_val


def momentum_pct(values: List[float], lookback: int) -> Optional[float]:
    """نسبة التغيّر المئوية على مدى `lookback` شمعة."""
    if lookback <= 0 or len(values) <= lookback:
        return None
    past = values[-lookback - 1]
    if past == 0:
        return None
    return (values[-1] / past - 1.0) * 100.0


def volume_surge(volumes: List[float], period: int = 20) -> Optional[float]:
    """
    نسبة حجم آخر شمعة إلى متوسط الحجم — أعلى من 1 يعني اهتمام متزايد.

    Ratio of latest volume to the average of the previous `period` bars.
    """
    if len(volumes) < period + 1:
        return None
    base = sum(volumes[-period - 1:-1]) / period
    if base == 0:
        return None
    return volumes[-1] / base


def bollinger(values: List[float], period: int = 20, mult: float = 2.0):
    """نطاقات بولنجر: (السفلي، الوسط، العلوي) لأحدث قيمة، أو None."""
    if len(values) < period:
        return None
    window = values[-period:]
    mid = sum(window) / period
    var = sum((x - mid) ** 2 for x in window) / period
    sd = var ** 0.5
    return mid - mult * sd, mid, mid + mult * sd


def stochastic(
    highs: List[float], lows: List[float], closes: List[float], k: int = 14
) -> Optional[float]:
    """مذبذب ستوكاستك %K لأحدث قيمة (0..100)، أو None."""
    n = len(closes)
    if n < k or len(highs) < k or len(lows) < k:
        return None
    hh = max(highs[-k:])
    ll = min(lows[-k:])
    if hh == ll:
        return 50.0
    return (closes[-1] - ll) / (hh - ll) * 100.0


def swing_points(highs: List[float], lows: List[float], left: int = 2, right: int = 2):
    """
    استخرج نقاط الارتكاز (القمم/القيعان) بطريقة الفراكتال.

    Returns (pivot_highs, pivot_lows) as lists of (index, price), oldest first.
    A pivot high at i is a high greater than `left` bars before and `right` after.
    """
    n = len(highs)
    ph, pl = [], []
    for i in range(left, n - right):
        seg_h = highs[i - left:i + right + 1]
        seg_l = lows[i - left:i + right + 1]
        if highs[i] == max(seg_h) and seg_h.count(highs[i]) == 1:
            ph.append((i, highs[i]))
        if lows[i] == min(seg_l) and seg_l.count(lows[i]) == 1:
            pl.append((i, lows[i]))
    return ph, pl


def mfi(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    volumes: List[float],
    period: int = 14,
) -> Optional[float]:
    """
    مؤشر تدفّق الأموال (Money Flow Index) — يقيس ضغط الشراء/البيع بالمال.

    Unlike RSI, MFI weights each move by its traded value (price × volume), so it
    reflects where the *money* is flowing — a good free proxy for institutional /
    "whale" pressure. Returns 0..100, or None if volume data is unusable
    (e.g. forex, where yfinance reports zero volume).
    """
    n = len(closes)
    if n < period + 1 or len(highs) != n or len(lows) != n or len(volumes) != n:
        return None

    typical = [(highs[i] + lows[i] + closes[i]) / 3.0 for i in range(n)]
    pos_flow = 0.0
    neg_flow = 0.0
    for i in range(max(1, n - period), n):
        raw = typical[i] * volumes[i]
        if typical[i] > typical[i - 1]:
            pos_flow += raw
        elif typical[i] < typical[i - 1]:
            neg_flow += raw

    if pos_flow + neg_flow == 0:
        return None
    if neg_flow == 0:
        return 100.0
    ratio = pos_flow / neg_flow
    return 100.0 - (100.0 / (1.0 + ratio))

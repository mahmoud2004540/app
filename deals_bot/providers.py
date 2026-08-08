"""
مزوّدات البيانات: جلب الشموع السعرية من مصادر مجانية.

Market-data providers. Each provider fetches OHLCV candles for a symbol and
returns a `Series`. Two backends are supported:

  * yfinance  — يغطي الأسواق الثلاثة (كريبتو/أسهم/فوركس) بدون مفتاح API.
  * coinbase  — كريبتو فقط، أسعار لحظية، بدون مفتاح API.
  * binance   — كريبتو فقط، بدون مفتاح API (قد يُحظر من بعض الخوادم).
  * auto      — كريبتو: Coinbase اللحظي ثم Yahoo احتياطيًا؛ غيره: Yahoo.

Network access is required at run time; if a dependency is missing or a request
fails, a clear RuntimeError is raised so the CLI/bot can report it per-symbol.
"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import List

from .models import Candle, Series

# فترات yfinance حسب الإطار الزمني: (interval, period)
_YF_RANGE = {
    "1m": ("1m", "5d"),
    "5m": ("5m", "1mo"),
    "15m": ("15m", "1mo"),
    "1h": ("60m", "3mo"),
    "1d": ("1d", "2y"),
}

# فترات Binance
_BINANCE_INTERVAL = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "1d": "1d"}


# --------------------------------------------------------------------------- #
# yfinance provider (crypto + stocks + forex)
# --------------------------------------------------------------------------- #
def fetch_yf(symbol: str, market: str, timeframe: str = "1h", limit: int = 300) -> Series:
    """
    اجلب الشموع عبر yfinance.

    Examples of symbols:
      crypto : "BTC-USD", "ETH-USD"
      stocks : "AAPL", "MSFT"
      forex  : "EURUSD=X", "GBPUSD=X"
    """
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "مكتبة yfinance غير مثبّتة. ثبّتها بـ: pip install yfinance"
        ) from exc

    interval, period = _YF_RANGE.get(timeframe, ("60m", "3mo"))
    df = yf.download(
        symbol,
        interval=interval,
        period=period,
        progress=False,
        auto_adjust=False,
        threads=False,
    )
    if df is None or len(df) == 0:
        raise RuntimeError(f"لا توجد بيانات لِـ {symbol} من yfinance.")

    candles: List[Candle] = []
    for ts, row in df.iterrows():
        try:
            candles.append(
                Candle(
                    ts=ts.timestamp(),
                    open=float(_cell(row, "Open")),
                    high=float(_cell(row, "High")),
                    low=float(_cell(row, "Low")),
                    close=float(_cell(row, "Close")),
                    volume=float(_cell(row, "Volume") or 0.0),
                )
            )
        except (TypeError, ValueError):
            continue

    candles = candles[-limit:]
    return Series(symbol=symbol, market=market, candles=candles)


def _cell(row, name):
    """اقرأ خلية من صف pandas مع التعامل مع الأعمدة متعددة المستويات."""
    val = row[name]
    # MultiIndex columns from yfinance can yield a Series for a single field.
    if hasattr(val, "iloc"):
        val = val.iloc[0]
    return val


# --------------------------------------------------------------------------- #
# Binance provider (crypto only, no API key)
# --------------------------------------------------------------------------- #
def fetch_binance(symbol: str, timeframe: str = "1h", limit: int = 300) -> Series:
    """
    اجلب شموع الكريبتو من Binance عبر REST العام (بدون مفتاح).

    symbol example: "BTCUSDT", "ETHUSDT".
    """
    interval = _BINANCE_INTERVAL.get(timeframe, "1h")
    limit = max(60, min(1000, limit))
    url = (
        "https://api.binance.com/api/v3/klines"
        f"?symbol={symbol.upper()}&interval={interval}&limit={limit}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "deals-bot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - surface any network/parse error
        raise RuntimeError(f"فشل جلب {symbol} من Binance: {exc}") from exc

    candles: List[Candle] = []
    for k in raw:
        # kline: [openTime, open, high, low, close, volume, closeTime, ...]
        candles.append(
            Candle(
                ts=float(k[0]) / 1000.0,
                open=float(k[1]),
                high=float(k[2]),
                low=float(k[3]),
                close=float(k[4]),
                volume=float(k[5]),
            )
        )
    return Series(symbol=symbol, market="crypto", candles=candles)


# --------------------------------------------------------------------------- #
# Coinbase provider (crypto only, real-time, no API key)
# --------------------------------------------------------------------------- #
# دقّة الشموع بالثواني حسب الإطار الزمني
_COINBASE_GRAN = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400}


def _parse_coinbase(raw, symbol: str, limit: int = 300) -> Series:
    """حوّل استجابة Coinbase إلى Series (دالة نقية قابلة للاختبار بدون شبكة)."""
    candles: List[Candle] = []
    for k in raw:
        # صيغة Coinbase: [time, low, high, open, close, volume]
        candles.append(
            Candle(
                ts=float(k[0]),
                open=float(k[3]),
                high=float(k[2]),
                low=float(k[1]),
                close=float(k[4]),
                volume=float(k[5]),
            )
        )
    candles.sort(key=lambda c: c.ts)   # Coinbase يرجع الأحدث أولًا → نرتّب تصاعديًا
    candles = candles[-limit:]
    return Series(symbol=symbol, market="crypto", candles=candles)


def fetch_coinbase(symbol: str, timeframe: str = "1h", limit: int = 300) -> Series:
    """
    اجلب شموع الكريبتو اللحظية من Coinbase (بدون مفتاح، أسعار محدّثة).

    symbol example: "BTC-USD", "ETH-USD" (نفس صيغة yfinance للأزواج الدولارية).
    """
    gran = _COINBASE_GRAN.get(timeframe, 3600)
    url = (
        f"https://api.exchange.coinbase.com/products/{symbol.upper()}/candles"
        f"?granularity={gran}"
    )
    req = urllib.request.Request(
        url, headers={"User-Agent": "deals-bot/1.0", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - surface any network/parse error
        raise RuntimeError(f"فشل جلب {symbol} من Coinbase: {exc}") from exc
    if not isinstance(raw, list) or not raw:
        raise RuntimeError(f"لا توجد بيانات لِـ {symbol} من Coinbase.")
    return _parse_coinbase(raw, symbol, limit=limit)


# --------------------------------------------------------------------------- #
# Unified dispatch
# --------------------------------------------------------------------------- #
def fetch(symbol: str, market: str, source: str, timeframe: str, limit: int = 300) -> Series:
    """
    نقطة دخول موحّدة لاختيار المزوّد المناسب.

    source:
      "yfinance" (افتراضي، كل الأسواق)
      "binance"  (كريبتو فقط)
      "coinbase" (كريبتو فقط، لحظي)
      "auto"     (كريبتو: Coinbase لحظي ثم Yahoo احتياطيًا؛ غيره: Yahoo)
    """
    if source == "binance":
        return fetch_binance(symbol, timeframe=timeframe, limit=limit)
    if source == "coinbase":
        return fetch_coinbase(symbol, timeframe=timeframe, limit=limit)
    if source == "auto":
        return fetch_best(symbol, market, timeframe=timeframe, limit=limit)
    return fetch_yf(symbol, market, timeframe=timeframe, limit=limit)


def fetch_best(symbol: str, market: str, timeframe: str = "1h", limit: int = 300) -> Series:
    """
    أفضل مصدر متاح: للكريبتو نجرّب Coinbase اللحظي ثم نرجع لـ Yahoo عند الفشل.

    Prefer the real-time Coinbase source for crypto (fresher prices), and fall
    back to Yahoo Finance per-symbol if Coinbase doesn't list it or errors.
    """
    if market == "crypto":
        try:
            s = fetch_coinbase(symbol, timeframe=timeframe, limit=limit)
            if len(s) >= 60:
                return s
        except Exception:  # noqa: BLE001 - fall back gracefully
            pass
    return fetch_yf(symbol, market, timeframe=timeframe, limit=limit)


def fetch_many(
    symbols: List[str],
    market: str,
    source: str,
    timeframe: str,
    limit: int = 300,
    pause: float = 0.0,
) -> List[Series]:
    """
    اجلب عدة رموز، متجاهلًا الرموز التي تفشل (مع طباعتها كتحذير).

    Returns only the series that fetched successfully; failures are collected
    and reported by the caller via the returned list length vs. input.
    """
    out: List[Series] = []
    for sym in symbols:
        try:
            s = fetch(sym, market, source, timeframe, limit=limit)
            if len(s) >= 60:
                out.append(s)
        except Exception as exc:  # noqa: BLE001
            print(f"  ⚠️  تخطّي {sym}: {exc}")
        if pause:
            time.sleep(pause)
    return out

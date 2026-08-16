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
import os
import time
import urllib.error
import urllib.request
from typing import List, Optional

from .models import Candle, Series


def _http_json(url: str, timeout: int = 20, retries: int = 4):
    """
    GET يُرجع JSON مع إعادة محاولة عند الحظر المؤقت (429) أو أخطاء عابرة.

    Retries with exponential backoff on HTTP 429 (rate limit) and transient
    network errors — essential when sweeping hundreds of symbols.
    """
    headers = {"User-Agent": "deals-bot/1.0", "Accept": "application/json"}
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (429, 418, 502, 503) and attempt < retries - 1:
                time.sleep(0.6 * (2 ** attempt))
                continue
            raise
        except Exception as exc:  # noqa: BLE001 - transient network
            last = exc
            if attempt < retries - 1:
                time.sleep(0.4 * (2 ** attempt))
                continue
            raise
    raise last if last else RuntimeError("فشل الطلب")

# فترات yfinance حسب الإطار الزمني: (interval, period)
_YF_RANGE = {
    "1m": ("1m", "5d"),
    "5m": ("5m", "1mo"),
    "15m": ("15m", "1mo"),
    "1h": ("60m", "3mo"),
    "6h": ("1h", "6mo"),     # yfinance لا يدعم 6h؛ نقرّبها بـ 1h (Coinbase يدعم 6h فعليًا)
    "1d": ("1d", "2y"),
}

# فترات Binance
_BINANCE_INTERVAL = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "6h": "6h", "1d": "1d"}


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
_COINBASE_GRAN = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "6h": 21600, "1d": 86400}


def list_coinbase_usd_products(quote: str = "USD") -> List[str]:
    """
    اجلب قائمة كل أزواج الكريبتو المتاحة بالدولار من Coinbase (ديناميكيًا).

    Returns every online, tradable <BASE>-USD product id — effectively "all
    crypto" the exchange lists. Falls back to raising on network error.
    """
    data = _http_json("https://api.exchange.coinbase.com/products", timeout=30, retries=5)
    out: List[str] = []
    for p in data:
        if (
            p.get("quote_currency") == quote
            and p.get("status") == "online"
            and not p.get("trading_disabled")
            and not p.get("post_only")
            and not p.get("limit_only")
            and not p.get("cancel_only")
        ):
            out.append(p["id"])
    return sorted(out)


def fetch_fear_greed() -> int:
    """
    مؤشر الخوف والطمع للكريبتو (0..100) من alternative.me (مجاني، بدون مفتاح).

    Returns the latest crypto Fear & Greed value. Raises on failure so callers
    can mark the sentiment school as unavailable instead of guessing.
    """
    url = "https://api.alternative.me/fng/?limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "deals-bot/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return int(data["data"][0]["value"])


def _parse_gainers(raw, top: int = 15, min_vol_usd: float = 3_000_000.0):
    """
    رتّب استجابة CoinGecko لأكبر الرابحين خلال 24 ساعة (دالة نقية للاختبار).

    Filters by minimum 24h USD volume (to skip illiquid noise), sorts by 24h %
    change descending, and returns the top movers as simple dicts.
    """
    rows = []
    for c in raw:
        chg = c.get("price_change_percentage_24h")
        vol = c.get("total_volume") or 0.0
        if chg is None or vol < min_vol_usd:
            continue
        rows.append({
            "symbol": (c.get("symbol") or "").upper(),
            "name": c.get("name") or "",
            "price": float(c.get("current_price") or 0.0),
            "change_24h": float(chg),
            "volume": float(vol),
        })
    rows.sort(key=lambda r: r["change_24h"], reverse=True)
    return rows[:top]


def fetch_top_gainers(top: int = 15, min_vol_usd: float = 3_000_000.0):
    """
    أكبر العملات ارتفاعًا الآن عبر السوق كله (CoinGecko) — يشمل عملات Binance.

    Surfaces the biggest 24h movers across the whole market (not just one
    exchange). Free, global source; raises on failure so callers can note it.
    """
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        "?vs_currency=usd&order=volume_desc&per_page=250&page=1"
        "&price_change_percentage=24h"
    )
    raw = _http_json(url, timeout=25, retries=4)
    if not isinstance(raw, list):
        raise RuntimeError("استجابة CoinGecko غير متوقعة.")
    return _parse_gainers(raw, top=top, min_vol_usd=min_vol_usd)


def _parse_trending(raw):
    """رتّب استجابة CoinGecko للعملات الرائجة (الأكثر بحثًا/اهتمامًا)."""
    out = []
    for it in raw.get("coins", []):
        d = it.get("item", {}) or {}
        data = d.get("data", {}) or {}
        chg = (data.get("price_change_percentage_24h") or {}).get("usd")
        out.append({
            "symbol": (d.get("symbol") or "").upper(),
            "name": d.get("name") or "",
            "rank": d.get("market_cap_rank"),
            "change_24h": float(chg) if chg is not None else None,
        })
    return out


def fetch_trending():
    """
    العملات الرائجة الآن (الأكثر بحثًا) من CoinGecko — غالبًا عملات جديدة/مُهيّجة.

    Trending = the coins people are searching most right now, which usually
    surfaces newly listed / freshly hyped tokens (the ones that pump). Free.
    """
    raw = _http_json("https://api.coingecko.com/api/v3/search/trending", timeout=20)
    if not isinstance(raw, dict):
        raise RuntimeError("استجابة CoinGecko غير متوقعة.")
    return _parse_trending(raw)


def _base_asset(symbol: str) -> str:
    """استخرج رمز الأصل الأساسي: BTC-USD→BTC، ETHUSDT→ETH، EURUSD=X→EUR."""
    s = symbol.upper().replace("=X", "")
    for suf in ("-USD", "-USDT", "-USDC", "USDT", "USDC", "USD"):
        if s.endswith(suf) and len(s) > len(suf):
            return s[: -len(suf)]
    return s


def _parse_sentiment(raw: dict, asset: str) -> dict:
    """
    لخّص مشاعر أخبار CryptoPanic لأصل معيّن: أصوات إيجابية مقابل سلبية.

    Aggregates positive/negative community votes across recent posts. Returns a
    dict with score, counts, a label, and how many posts were considered.
    """
    results = raw.get("results", []) if isinstance(raw, dict) else []
    pos = neg = posts = 0
    for it in results:
        votes = it.get("votes", {}) or {}
        pos += int(votes.get("positive", 0) or 0)
        neg += int(votes.get("negative", 0) or 0)
        posts += 1
    score = pos - neg
    if score > 0:
        label = "🟢 إيجابي"
    elif score < 0:
        label = "🔴 سلبي"
    else:
        label = "⚪ محايد"
    return {"asset": asset, "score": score, "positive": pos,
            "negative": neg, "posts": posts, "label": label}


def fetch_sentiment(symbol: str, token: str = None, limit: int = 30) -> Optional[dict]:
    """
    مشاعر الأخبار لعملة عبر CryptoPanic (مجّاني، يحتاج CRYPTOPANIC_TOKEN).

    Free news/sentiment. Returns a summary dict or None if no token / no data.
    NOTE: only *current* news is available on the free tier — this is live
    enrichment, not a backtestable signal.
    """
    token = token or os.environ.get("CRYPTOPANIC_TOKEN")
    if not token:
        return None
    asset = _base_asset(symbol)
    url = (f"https://cryptopanic.com/api/v1/posts/?auth_token={token}"
           f"&currencies={asset}&public=true")
    try:
        raw = _http_json(url, timeout=15, retries=2)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(raw, dict):
        return None
    return _parse_sentiment(raw, asset)


def _to_binance_symbol(symbol: str) -> str:
    """حوّل صيغة yfinance/Coinbase إلى صيغة Binance: BTC-USD → BTCUSDT."""
    base = symbol.upper().split("-")[0].replace("USDT", "").replace("USD", "")
    return f"{base}USDT"


def fetch_spot_binance(symbol: str) -> float:
    """
    السعر الفوري من Binance (المرجع الأشهر لدى كثير من المتداولين).

    symbol example: "BTC-USD" → يُحوّل إلى "BTCUSDT". قد يُحجب من بعض الخوادم
    السحابية (يُرجع خطأ فيُستخدم مصدر بديل).
    """
    sym = _to_binance_symbol(symbol)
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={sym}"
    req = urllib.request.Request(url, headers={"User-Agent": "deals-bot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"فشل جلب السعر الفوري لِـ {sym} من Binance: {exc}") from exc
    price = data.get("price")
    if price is None:
        raise RuntimeError(f"لا يوجد سعر فوري لِـ {sym} من Binance.")
    return float(price)


def fetch_spot_coinbase(symbol: str) -> float:
    """
    السعر الفوري (spot) الحالي من Coinbase — أحدث من إغلاق آخر شمعة.

    Returns the live traded price for a product (e.g. "BTC-USD"). Used to display
    an up-to-the-second price instead of the last completed candle's close.
    """
    url = f"https://api.exchange.coinbase.com/products/{symbol.upper()}/ticker"
    req = urllib.request.Request(
        url, headers={"User-Agent": "deals-bot/1.0", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"فشل جلب السعر الفوري لِـ {symbol}: {exc}") from exc
    price = data.get("price")
    if price is None:
        raise RuntimeError(f"لا يوجد سعر فوري لِـ {symbol}.")
    return float(price)


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
    try:
        raw = _http_json(url, timeout=20, retries=4)
    except Exception as exc:  # noqa: BLE001 - surface any network/parse error
        raise RuntimeError(f"فشل جلب {symbol} من Coinbase: {exc}") from exc
    if not isinstance(raw, list) or not raw:
        raise RuntimeError(f"لا توجد بيانات لِـ {symbol} من Coinbase.")
    return _parse_coinbase(raw, symbol, limit=limit)


# أطر زمنية غير مدعومة أصلًا من المزوّدين → تُبنى بدمج إطار أصغر.
# 30m = دمج كل شمعتَي 15m (Coinbase لا يوفّر 30m أصلًا).
_RESAMPLE_FROM = {"30m": ("15m", 2)}


def resample_candles(candles: List[Candle], factor: int) -> List[Candle]:
    """
    ادمج كل «factor» شمعة متتالية في شمعة واحدة أكبر (دالة نقية قابلة للاختبار).

    Merge groups of `factor` consecutive candles into one higher-timeframe candle
    (open=first, close=last, high=max, low=min, volume=sum). Grouping is anchored
    to the newest candle so the latest merged candle is always complete; any
    leftover oldest candles that don't fill a full group are dropped.
    """
    if factor <= 1 or not candles:
        return list(candles)
    ordered = sorted(candles, key=lambda c: c.ts)
    out: List[Candle] = []
    # نجمّع من الأحدث للأقدم لضمان اكتمال آخر شمعة، ثم نعكس الترتيب تصاعديًا.
    for end in range(len(ordered), 0, -factor):
        start = end - factor
        if start < 0:
            break
        group = ordered[start:end]
        out.append(Candle(
            ts=group[0].ts,
            open=group[0].open,
            high=max(c.high for c in group),
            low=min(c.low for c in group),
            close=group[-1].close,
            volume=sum(c.volume for c in group),
        ))
    out.reverse()
    return out


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

    الأطر غير الأصلية (مثل 30m) تُبنى بجلب إطار أصغر ثم دمجه.
    """
    if timeframe in _RESAMPLE_FROM:
        base_tf, factor = _RESAMPLE_FROM[timeframe]
        base = fetch(symbol, market, source, base_tf, limit=limit * factor + factor)
        merged = resample_candles(base.candles, factor)[-limit:]
        return Series(symbol=base.symbol, market=base.market, candles=merged)
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

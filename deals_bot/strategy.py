"""
منسّق الاستراتيجية: يجمع الجلب + التحليل + التأكيد + الفلترة + إدارة المخاطر.

High-level orchestration used by both the CLI and the scheduled digest so the
logic lives in one place:

  1. fetch each symbol on the base timeframe and analyze it
  2. (optional) confirm the signal against a higher timeframe
  3. filter out weak signals below `min_confidence`
  4. attach position sizing from account balance + risk-per-trade
  5. rank and return the strongest deals
"""

from __future__ import annotations

import time
from typing import List, Optional

import config
from . import indicators as ind
from .analyzer import (
    STOP_ATR_MULT,
    TARGET_ATR_MULT,
    add_position_sizing,
    analyze_symbol,
    detect_accumulation,
    detect_early_pump,
    detect_pre_pump,
    detect_trend_pullback,
)
from .models import Deal
from .providers import (
    fetch,
    fetch_spot_binance,
    fetch_spot_coinbase,
    list_coinbase_usd_products,
)


def resolve_symbols(market: str, source: str) -> List[str]:
    """
    حدّد قائمة الرموز للسوق: كل عملات Coinbase عند نطاق "all"، وإلا القوائم المعرّفة.
    """
    if market == "crypto":
        if source == "binance":
            return config.BINANCE_WATCHLIST
        if getattr(config, "CRYPTO_UNIVERSE", "watchlist") == "all":
            try:
                syms = list_coinbase_usd_products()
                cap = getattr(config, "MAX_CRYPTO_SYMBOLS", 400)
                return syms[:cap]
            except Exception as exc:  # noqa: BLE001 - fall back to the short list
                print(f"  ⚠️ تعذّر جلب كل عملات Coinbase ({exc}) — استخدام القائمة القصيرة.")
                return config.WATCHLISTS["crypto"]
        return config.WATCHLISTS["crypto"]
    if market == "forex":
        return getattr(config, "FOREX_UNIVERSE", None) or config.WATCHLISTS["forex"]
    if market == "stocks":
        return getattr(config, "STOCKS_UNIVERSE", None) or config.WATCHLISTS["stocks"]
    return config.WATCHLISTS.get(market, [])


def _accumulation_deal(sym: str, market: str, acc: dict) -> Deal:
    """ابنِ صفقة تجميع من نتيجة الكاشف."""
    price = acc["price"]
    base_low = acc["base_low"]
    base_high = acc["base_high"]
    width = max(base_high - base_low, price * 0.001)
    stop = base_low * 0.98
    target = max(base_high + 2.0 * width, price * 1.12)
    risk = abs(price - stop)
    reward = abs(target - price)
    return Deal(
        symbol=sym, market=market, direction="BUY",
        score=acc["score"], confidence=acc["score"], price=price,
        entry=round(price, 8), stop_loss=round(stop, 8), take_profit=round(target, 8),
        risk_reward=round((reward / risk) if risk > 0 else 0.0, 2),
        reasons=acc["reasons"], accumulation=True,
    )


def _early_pump_deal(sym: str, market: str, ep: dict) -> Deal:
    """ابنِ صفقة «بداية اندفاع» من نتيجة الكاشف — وقف تحت مستوى الكسر."""
    price = ep["price"]
    base_high = ep["base_high"]
    base_low = ep["base_low"]
    width = max(base_high - base_low, price * 0.001)
    # وقف الخسارة تحت مستوى الكسر مباشرةً (المقاومة المكسورة تصبح دعمًا)
    stop = min(base_high * 0.985, price * 0.97)
    target = max(base_high + 1.5 * width, price * 1.10)
    risk = abs(price - stop)
    reward = abs(target - price)
    return Deal(
        symbol=sym, market=market, direction="BUY",
        score=ep["score"], confidence=ep["score"], price=price,
        entry=round(price, 8), stop_loss=round(stop, 8), take_profit=round(target, 8),
        risk_reward=round((reward / risk) if risk > 0 else 0.0, 2),
        reasons=ep["reasons"], early_pump=True, pump=True,
    )


def _trend_pullback_deal(sym: str, market: str, tp: dict) -> Deal:
    """ابنِ صفقة «ارتداد داخل اتجاه صاعد» من نتيجة الكاشف (الإعداد الرابح)."""
    price = tp["price"]
    stop = tp["stop"]
    target = tp["target"]
    risk = abs(price - stop)
    reward = abs(target - price)
    return Deal(
        symbol=sym, market=market, direction="BUY",
        score=tp["score"], confidence=tp["score"], price=price,
        entry=round(price, 8), stop_loss=round(stop, 8), take_profit=round(target, 8),
        risk_reward=round((reward / risk) if risk > 0 else 0.0, 2),
        reasons=tp["reasons"], trend=True,
    )


def market_is_bullish(timeframe: str, source: str = "auto", symbol: str = "BTC-USD") -> Optional[bool]:
    """
    حالة السوق العام: هل البيتكوين فوق متوسّطه (EMA50) على هذا الإطار؟

    Market-regime gate (matches the backtested filter): returns True if BTC is
    trading above its EMA50 — a tailwind for long setups on other coins. Returns
    None if it can't be determined (then callers shouldn't hard-block on it).
    """
    try:
        s = fetch(symbol, "crypto", source, timeframe, limit=200)
    except Exception:  # noqa: BLE001
        return None
    closes = s.closes()
    if len(closes) < 55:
        return None
    e50 = ind.ema(closes, 50)
    if not e50:
        return None
    return closes[-1] > e50


def top_picks(
    markets: List[str],
    timeframe: str = None,
    top: int = None,
    source: str = None,
    min_score: float = None,
    use_regime: bool = None,
    rr: float = None,
    balance: float = None,
    risk_pct: float = None,
):
    """
    أفضل 1-2 صفقة من فحص كل العملات — الإعداد الرابح المُثبت بالباك-تِست.

    Scans the whole universe once, keeps only high-conviction trend-pullback
    setups (score >= min_score), optionally gated by market regime (only when
    BTC is above its EMA50), then returns the single best `top` picks. This is
    the positive-expectancy configuration found via backtest (+0.28R/trade at
    score>=85 with the regime filter on 1h data).

    Returns (picks, market_bullish) so the caller can explain an empty result.
    """
    timeframe = timeframe or config.DEFAULT_TIMEFRAME
    top = top or getattr(config, "TREND_TOP", 2)
    source = source or config.DEFAULT_SOURCE
    min_score = getattr(config, "TREND_MIN_SCORE", 85) if min_score is None else min_score
    if use_regime is None:
        use_regime = getattr(config, "TREND_MARKET_REGIME", True)
    rr = getattr(config, "TREND_RR", 2.0) if rr is None else rr
    balance = config.ACCOUNT_BALANCE if balance is None else balance
    risk_pct = config.RISK_PER_TRADE if risk_pct is None else risk_pct

    # بوّابة حالة السوق: لا نشتري في سوق هابط (أهم عامل في التوقّع الموجب)
    market_bullish = None
    if use_regime and "crypto" in markets:
        market_bullish = market_is_bullish(timeframe)
        if market_bullish is False:
            print("  🛑 السوق العام (BTC) تحت متوسّطه — لا صفقات شراء الآن (فلتر السوق).")
            return [], market_bullish

    picks: List[Deal] = []
    for market in markets:
        src = source if (market == "crypto" and source in ("binance", "coinbase")) else \
            ("yfinance" if market != "crypto" else "auto")
        symbols = resolve_symbols(market, src)
        print(f"  🔭 فحص {len(symbols)} رمزًا في «{market}» ({timeframe}) عن أقوى الإعدادات...")
        pause = 0.05 if market == "crypto" else 0.0
        found = 0
        for sym in symbols:
            try:
                series = fetch(sym, market, src, timeframe, limit=300)
            except Exception:  # noqa: BLE001
                if pause:
                    time.sleep(pause)
                continue
            if pause:
                time.sleep(pause)
            if len(series) < 60:
                continue
            tp = detect_trend_pullback(series, rr=rr)
            if tp and tp["score"] >= min_score:
                picks.append(_trend_pullback_deal(sym, market, tp))
                found += 1
        print(f"  ✅ «{market}»: {found} إعداد فوق الدرجة {min_score:.0f}.")

    picks.sort(key=lambda d: d.confidence, reverse=True)
    picks = picks[:top]
    for d in picks:
        _refresh_live_price(d)
        add_position_sizing(d, balance, risk_pct)
    return picks, market_bullish


def _htf_confirm_prepump(symbol: str, market: str, src: str, base_tf: str) -> bool:
    """
    تأكيد من إطار زمني أعلى: استبعد «السكينة الساقطة».

    Rejects setups where the higher timeframe is still crashing / making fresh
    lows (a falling knife). Returns True to keep, False to reject. On any fetch
    problem it returns True (don't penalize on missing data).
    """
    htf = config.HIGHER_TIMEFRAME.get(base_tf, base_tf)
    if htf == base_tf:
        return True
    try:
        hs = fetch(symbol, market, src, htf, limit=200)
    except Exception:  # noqa: BLE001
        return True
    hc = hs.closes()
    if len(hc) < 30:
        return True
    from .analyzer import ind  # reuse indicators module
    mom = ind.momentum_pct(hc, 5)
    if mom is not None and mom < -12.0:          # الفريم الأعلى ينهار → ارفض
        return False
    # قاع جديد على آخر شمعة في الفريم الأعلى = ما زال يهبط
    if hc[-1] <= min(hc[-15:-1]) * 1.001:
        return False
    return True


def _finalize_prepump(deals: List[Deal], timeframe: str, top: int,
                      min_score: float, htf_confirm: bool) -> List[Deal]:
    """بوابة الجودة + تأكيد الإطار الأعلى + الترتيب، لقوائم «ما قبل الاندفاع»."""
    # بوابة الجودة أولًا
    cand = [d for d in deals if d.confidence >= min_score]
    cand.sort(key=lambda d: d.confidence, reverse=True)
    if not htf_confirm:
        return cand[:top]
    out: List[Deal] = []
    for d in cand[: top * 3]:                     # نؤكّد أقوى المرشّحين فقط (توفير طلبات)
        src = "auto" if d.market == "crypto" else "yfinance"
        if _htf_confirm_prepump(d.symbol, d.market, src, timeframe):
            d.confirmed = True
            d.confidence = min(100.0, d.confidence + 6.0)
            d.score = d.confidence
            out.append(d)
        if len(out) >= top:
            break
    out.sort(key=lambda d: d.confidence, reverse=True)
    return out[:top]


def scan_universe(
    markets: List[str],
    timeframe: str = None,
    top: int = None,
    direction: str = "any",
    source: str = None,
    min_confidence: float = None,
    balance: float = None,
    risk_pct: float = None,
):
    """
    فحص واسع بمرور واحد: يجلب كل رمز مرة واحدة ويستخرج منه إشارة صفقة + تجميع.

    Efficient single-pass scan over a large universe: one fetch per symbol feeds
    both the trade-signal analysis and the accumulation detector. Returns
    (signals_top, accumulation_top). Designed for hundreds of symbols.
    """
    timeframe = timeframe or config.DEFAULT_TIMEFRAME
    top = top or config.DEFAULT_TOP
    source = source or config.DEFAULT_SOURCE
    min_confidence = config.MIN_CONFIDENCE if min_confidence is None else min_confidence
    balance = config.ACCOUNT_BALANCE if balance is None else balance
    risk_pct = config.RISK_PER_TRADE if risk_pct is None else risk_pct

    signals: List[Deal] = []
    accums: List[Deal] = []
    earlies: List[Deal] = []

    for market in markets:
        if market == "crypto":
            src = source if source in ("binance", "coinbase") else "auto"
        else:
            src = "yfinance"
        symbols = resolve_symbols(market, src)
        print(f"  🔭 فحص {len(symbols)} رمزًا في «{market}» ({timeframe})...")
        scanned = 0
        # تباطؤ بسيط بين طلبات الكريبتو لتفادي الحظر المؤقت من Coinbase
        pause = 0.05 if market == "crypto" else 0.0
        for sym in symbols:
            try:
                series = fetch(sym, market, src, timeframe, limit=300)
            except Exception:  # noqa: BLE001 - skip unavailable symbols quietly
                if pause:
                    time.sleep(pause)
                continue
            if pause:
                time.sleep(pause)
            if len(series) < 60:
                continue
            scanned += 1
            deal = analyze_symbol(series)
            if deal.is_actionable() and deal.confidence >= min_confidence:
                if direction == "any" or deal.direction.lower() == direction:
                    signals.append(deal)
            acc = detect_accumulation(series)
            if acc:
                accums.append(_accumulation_deal(sym, market, acc))
            else:
                # الانضغاط قبل الاندفاع (لا يشترط هبوطًا سابقًا) — نفس قسم «قبل الاندفاع»
                pre = detect_pre_pump(series)
                if pre:
                    accums.append(_accumulation_deal(sym, market, pre))
            ep = detect_early_pump(series)
            if ep:
                earlies.append(_early_pump_deal(sym, market, ep))
        print(f"  ✅ «{market}»: فُحص {scanned} رمزًا فعليًا.")

    signals.sort(key=lambda d: (d.pump, d.whale, d.confidence), reverse=True)
    sig_top = signals[:top]

    # دقة أعلى لإشارات «ما قبل الاندفاع»: بوابة جودة + تأكيد إطار أعلى + ترتيب
    prepump_min = getattr(config, "PREPUMP_MIN_SCORE", 70)
    htf = getattr(config, "PREPUMP_HTF_CONFIRM", True)
    acc_top = _finalize_prepump(accums, timeframe, top, prepump_min, htf)
    early_top = _finalize_prepump(earlies, timeframe, top, prepump_min, htf)

    for d in sig_top + acc_top + early_top:
        _refresh_live_price(d)
        add_position_sizing(d, balance, risk_pct)
    return sig_top, acc_top, early_top


def apply_live_price(deal: Deal, live: float) -> Deal:
    """
    حدّث سعر الصفقة إلى السعر الفوري وأعِد حساب الدخول/الوقف/الهدف منه.

    Pure helper (offline-testable): sets the displayed price and entry to the
    live spot price, then rebuilds stop-loss / take-profit from the same ATR so
    the levels stay consistent with the current price.
    """
    if not deal.is_actionable() or live <= 0:
        return deal
    atr = deal.indicators.get("atr")
    deal.price = round(live, 8)
    deal.entry = round(live, 8)
    if atr:
        if deal.direction == "BUY":
            deal.stop_loss = round(live - STOP_ATR_MULT * atr, 8)
            deal.take_profit = round(live + TARGET_ATR_MULT * atr, 8)
        else:  # SELL
            deal.stop_loss = round(live + STOP_ATR_MULT * atr, 8)
            deal.take_profit = round(live - TARGET_ATR_MULT * atr, 8)
        risk = abs(deal.entry - deal.stop_loss)
        reward = abs(deal.take_profit - deal.entry)
        deal.risk_reward = round((reward / risk) if risk > 0 else 0.0, 2)
    return deal


def _refresh_live_price(deal: Deal) -> None:
    """
    اجلب السعر الفوري للكريبتو: Binance أولًا (المرجع الأشهر) ثم Coinbase.

    Keeps the candle-based price only if both live sources fail.
    """
    if deal.market != "crypto" or not deal.is_actionable():
        return
    for name, fn in (("Binance", fetch_spot_binance), ("Coinbase", fetch_spot_coinbase)):
        try:
            live = fn(deal.symbol)
        except Exception as exc:  # noqa: BLE001 - try the next source
            print(f"  ⚠️ {deal.symbol}: {name} غير متاح: {exc}")
            continue
        print(f"  💹 {deal.symbol}: سعر فوري {live} (المصدر: {name})")
        apply_live_price(deal, live)
        return


def _confirm_symbol(
    symbol: str,
    market: str,
    source: str,
    base_tf: str,
) -> Optional[Deal]:
    """حلّل رمزًا واحدًا مع تأكيد اختياري من إطار أعلى. يرجع None عند الفشل."""
    try:
        base = fetch(symbol, market, source, base_tf)
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️  تخطّي {symbol}: {exc}")
        return None
    if len(base) < 60:
        return None

    deal = analyze_symbol(base)
    if not deal.is_actionable():
        return deal

    if config.CONFIRM_HIGHER_TIMEFRAME:
        higher_tf = config.HIGHER_TIMEFRAME.get(base_tf, base_tf)
        if higher_tf != base_tf:
            try:
                higher = fetch(symbol, market, source, higher_tf)
                if len(higher) >= 60:
                    hdeal = analyze_symbol(higher)
                    deal.confirmed = hdeal.direction == deal.direction
                    if deal.confirmed:
                        deal.reasons.insert(
                            0, f"✅ مؤكّد على الإطار الأعلى ({higher_tf})"
                        )
                    else:
                        deal.reasons.append(
                            f"⚠️ غير مؤكّد على الإطار الأعلى ({higher_tf})"
                        )
            except Exception:  # noqa: BLE001 - confirmation is best-effort
                deal.confirmed = None

    return deal


def best_deals(
    markets: List[str],
    timeframe: str = None,
    top: int = None,
    direction: str = "any",
    source: str = None,
    min_confidence: float = None,
    balance: float = None,
    risk_pct: float = None,
    require_confirmed: bool = None,
    whale_only: bool = None,
) -> List[Deal]:
    """
    أرجع أفضل الصفقات عبر الأسواق المطلوبة بعد كل الفلاتر.

    Any argument left as None falls back to the value in config.py.
    """
    timeframe = timeframe or config.DEFAULT_TIMEFRAME
    top = top or config.DEFAULT_TOP
    source = source or config.DEFAULT_SOURCE
    min_confidence = config.MIN_CONFIDENCE if min_confidence is None else min_confidence
    balance = config.ACCOUNT_BALANCE if balance is None else balance
    risk_pct = config.RISK_PER_TRADE if risk_pct is None else risk_pct
    if require_confirmed is None:
        require_confirmed = config.CONFIRM_HIGHER_TIMEFRAME
    if whale_only is None:
        whale_only = getattr(config, "WHALE_ONLY", False)

    collected: List[Deal] = []
    for market in markets:
        # للكريبتو: مصدر لحظي (Coinbase) مع رجوع تلقائي لـ Yahoo، إلا لو المستخدم
        # فرض Binance صراحةً. لغير الكريبتو: Yahoo.
        if market == "crypto":
            src = source if source in ("binance", "coinbase") else "auto"
        else:
            src = "yfinance"
        symbols = (
            config.BINANCE_WATCHLIST
            if (market == "crypto" and src == "binance")
            else config.WATCHLISTS.get(market, [])
        )
        for sym in symbols:
            deal = _confirm_symbol(sym, market, src, timeframe)
            if deal and deal.is_actionable():
                collected.append(deal)

    # فلتر الجودة
    filtered = [d for d in collected if d.confidence >= min_confidence]
    # فلتر التأكيد من الإطار الأعلى (إن وُجد تأكيد صريح بأنها غير مؤكّدة نستبعدها)
    if require_confirmed:
        filtered = [d for d in filtered if d.confirmed is not False]
    # وضع الحيتان فقط: نعرض الصفقات التي بها نشاط حيتان واضح
    if whale_only:
        filtered = [d for d in filtered if d.whale]

    # اتجاه — الاندفاعات (Pump) ثم الحيتان تتصدّر دائمًا، ثم الأقوى ثقةً
    if direction == "buy":
        filtered = [d for d in filtered if d.direction == "BUY"]
        filtered.sort(key=lambda d: (d.pump, d.whale, d.score), reverse=True)
    elif direction == "sell":
        filtered = [d for d in filtered if d.direction == "SELL"]
        # للبيع: الاندفاع/الحيتان أولًا ثم الأكثر سلبية
        filtered.sort(key=lambda d: (d.pump, d.whale, -d.score), reverse=True)
    else:
        filtered.sort(key=lambda d: (d.pump, d.whale, d.confidence), reverse=True)

    top_deals = filtered[:top]
    # تحديث السعر الفوري (للكريبتو) ثم إدارة المخاطر
    for d in top_deals:
        _refresh_live_price(d)
        add_position_sizing(d, balance, risk_pct)
    return top_deals


def accumulation_deals(
    markets: List[str],
    timeframe: str = "1h",
    top: int = None,
    source: str = None,
    balance: float = None,
    risk_pct: float = None,
) -> List[Deal]:
    """
    ابحث عن العملات في مرحلة التجميع بعد هبوط (بانتظار الاندفاع).

    Scans a higher timeframe for accumulation bases and returns them as BUY
    "watch" setups: entry at the current price, stop below the base, and a
    measured-move target above the range (the anticipated pump).
    """
    top = top or config.DEFAULT_TOP
    source = source or config.DEFAULT_SOURCE
    balance = config.ACCOUNT_BALANCE if balance is None else balance
    risk_pct = config.RISK_PER_TRADE if risk_pct is None else risk_pct

    out: List[Deal] = []
    for market in markets:
        if market == "crypto":
            src = source if source in ("binance", "coinbase") else "auto"
        else:
            src = "yfinance"
        symbols = (
            config.BINANCE_WATCHLIST
            if (market == "crypto" and src == "binance")
            else config.WATCHLISTS.get(market, [])
        )
        for sym in symbols:
            try:
                series = fetch(sym, market, src, timeframe, limit=300)
            except Exception as exc:  # noqa: BLE001
                print(f"  ⚠️  تخطّي {sym}: {exc}")
                continue
            acc = detect_accumulation(series)
            if not acc:
                continue

            price = acc["price"]
            base_low = acc["base_low"]
            base_high = acc["base_high"]
            width = max(base_high - base_low, price * 0.001)
            stop = base_low * 0.98                      # أسفل قاع النطاق مباشرةً
            # هدف الاندفاع: حركة مقيسة من النطاق، وبحدّ أدنى +12٪ (نتوقّع اندفاعًا)
            target = max(base_high + 2.0 * width, price * 1.12)
            risk = abs(price - stop)
            reward = abs(target - price)
            rr = round((reward / risk) if risk > 0 else 0.0, 2)

            out.append(
                Deal(
                    symbol=sym,
                    market=market,
                    direction="BUY",
                    score=acc["score"],
                    confidence=acc["score"],
                    price=price,
                    entry=round(price, 8),
                    stop_loss=round(stop, 8),
                    take_profit=round(target, 8),
                    risk_reward=rr,
                    reasons=acc["reasons"],
                    accumulation=True,
                )
            )

    out.sort(key=lambda d: d.confidence, reverse=True)
    top_deals = out[:top]
    for d in top_deals:
        _refresh_live_price(d)
        add_position_sizing(d, balance, risk_pct)
    return top_deals

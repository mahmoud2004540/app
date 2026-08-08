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

from typing import List, Optional

import config
from .analyzer import add_position_sizing, analyze_symbol
from .models import Deal
from .providers import fetch


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
    # إدارة المخاطر
    for d in top_deals:
        add_position_sizing(d, balance, risk_pct)
    return top_deals

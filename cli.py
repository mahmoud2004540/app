#!/usr/bin/env python3
"""
واجهة سطر الأوامر لبوت الصفقات.

Command-line interface. Run it to print the best trading deals for a market.

أمثلة / Examples:
    python cli.py                          # أفضل صفقات الكريبتو (افتراضي)
    python cli.py --market stocks --top 5
    python cli.py --market forex --timeframe 1d
    python cli.py --market crypto --source binance
    python cli.py --market all --direction buy
"""

from __future__ import annotations

import argparse
import sys

import config
from deals_bot import rank_deals
from deals_bot.formatter import format_deals
from deals_bot.providers import fetch_many


def _symbols_for(market: str, source: str) -> list[str]:
    if market == "crypto" and source == "binance":
        return config.BINANCE_WATCHLIST
    return config.WATCHLISTS[market]


def run(market: str, source: str, timeframe: str, top: int, direction: str) -> int:
    markets = ["crypto", "stocks", "forex"] if market == "all" else [market]

    all_deals = []
    for mkt in markets:
        # مصدر binance يدعم الكريبتو فقط؛ نرجع لـ yfinance لغيره
        src = source
        if mkt != "crypto" and src == "binance":
            src = "yfinance"

        symbols = _symbols_for(mkt, src)
        print(f"⏳ جاري تحليل {len(symbols)} رمزًا في سوق «{mkt}» (المصدر: {src})...")
        series = fetch_many(symbols, mkt, src, timeframe)
        if not series:
            print(f"  ⚠️  لم أستطع جلب بيانات لسوق «{mkt}».")
            continue
        deals = rank_deals(series, top=top, direction=direction)
        all_deals.extend(deals)

    # عند تحليل كل الأسواق، أعِد الترتيب النهائي حسب الثقة
    if market == "all":
        if direction == "buy":
            all_deals.sort(key=lambda d: d.score, reverse=True)
        elif direction == "sell":
            all_deals.sort(key=lambda d: d.score)
        else:
            all_deals.sort(key=lambda d: d.confidence, reverse=True)
        all_deals = all_deals[:top]

    title = f"أفضل الصفقات — {market} ({timeframe})"
    print()
    print(format_deals(all_deals, title=title))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="بوت يعطيك أفضل صفقات التداول (كريبتو / أسهم / فوركس).",
    )
    parser.add_argument(
        "--market", "-m",
        choices=["crypto", "stocks", "forex", "all"],
        default="crypto",
        help="السوق المطلوب تحليله (افتراضي: crypto).",
    )
    parser.add_argument(
        "--source", "-s",
        choices=["yfinance", "binance"],
        default=config.DEFAULT_SOURCE,
        help="مصدر البيانات (binance للكريبتو فقط).",
    )
    parser.add_argument(
        "--timeframe", "-t",
        choices=["1m", "5m", "15m", "1h", "1d"],
        default=config.DEFAULT_TIMEFRAME,
        help="الإطار الزمني للشموع (افتراضي: 1h).",
    )
    parser.add_argument(
        "--top", "-n",
        type=int,
        default=config.DEFAULT_TOP,
        help="عدد الصفقات المعروضة (افتراضي: 5).",
    )
    parser.add_argument(
        "--direction", "-d",
        choices=["any", "buy", "sell"],
        default="any",
        help="اتجاه الصفقات: any / buy / sell.",
    )
    args = parser.parse_args(argv)

    try:
        return run(args.market, args.source, args.timeframe, args.top, args.direction)
    except KeyboardInterrupt:
        print("\nتم الإيقاف.")
        return 130


if __name__ == "__main__":
    sys.exit(main())

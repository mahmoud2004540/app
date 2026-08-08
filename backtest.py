#!/usr/bin/env python3
"""
شغّل باك-تِست على بيانات حقيقية لقياس نسبة نجاح الاستراتيجية.

Run a backtest on real historical data to see the strategy's honest win rate and
expectancy — so your expectations are grounded in numbers, not hype.

أمثلة / Examples:
    python backtest.py --market crypto
    python backtest.py --market stocks --timeframe 1d
    python backtest.py --market all --timeframe 1h
"""

from __future__ import annotations

import argparse
import sys

import config
from deals_bot.backtester import backtest_series
from deals_bot.providers import fetch_many


def run(market: str, source: str, timeframe: str) -> int:
    markets = ["crypto", "stocks", "forex"] if market == "all" else [market]

    total_trades = total_wins = 0
    total_r = 0.0
    rows = []

    for mkt in markets:
        src = source if mkt == "crypto" else "yfinance"
        symbols = (
            config.BINANCE_WATCHLIST
            if (mkt == "crypto" and src == "binance")
            else config.WATCHLISTS[mkt]
        )
        print(f"⏳ باك-تِست {len(symbols)} رمزًا في «{mkt}» ({timeframe})...")
        series = fetch_many(symbols, mkt, src, timeframe, limit=1000)
        for s in series:
            res = backtest_series(s)
            if res.n == 0:
                continue
            rows.append(res)
            total_trades += res.n
            total_wins += res.wins
            total_r += res.total_r
            print(
                f"  {s.symbol:<12} صفقات={res.n:<3} "
                f"نجاح={res.win_rate:5.1f}%  "
                f"عامل الربح={res.profit_factor:4.2f}  "
                f"إجمالي={res.total_r:+.1f}R"
            )

    print("\n" + "=" * 48)
    if total_trades == 0:
        print("لا توجد صفقات كافية في الفترة المختارة.")
        return 0
    win_rate = total_wins / total_trades * 100.0
    expectancy = total_r / total_trades
    print(f"الإجمالي: {total_trades} صفقة")
    print(f"نسبة النجاح: {win_rate:.1f}%")
    print(f"العائد المتوقّع لكل صفقة: {expectancy:+.2f}R")
    print(f"إجمالي العائد: {total_r:+.1f}R")
    print("=" * 48)
    print(
        "\nℹ️ ملاحظة: R = مضاعف المخاطرة. عائد +0.2R لكل صفقة يعني استراتيجية "
        "رابحة على المدى الطويل حتى لو نسبة النجاح أقل من 100%."
    )
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="باك-تِست لاستراتيجية بوت الصفقات.")
    p.add_argument("--market", "-m", choices=["crypto", "stocks", "forex", "all"], default="crypto")
    p.add_argument("--source", "-s", choices=["yfinance", "binance"], default=config.DEFAULT_SOURCE)
    p.add_argument("--timeframe", "-t", choices=["1m", "5m", "15m", "1h", "1d"], default="1h")
    args = p.parse_args(argv)
    return run(args.market, args.source, args.timeframe)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
تحليل مؤسسي متعدد المدارس (تقاطع الأدلة) لأصل واحد.

Institutional multi-school confluence analysis for a single asset — prints the
full structured report (each school's verdict, agreement count, decision,
entry/stop/targets, R:R, position size, confidence, alternative scenario, and
risk notes). Schools whose data is unavailable are labelled, never guessed.

أمثلة / Examples:
    python analyze.py --symbol BTC-USD --market crypto --timeframe 1h
    python analyze.py -s AAPL -m stocks -t 1d
    python analyze.py -s EURUSD=X -m forex
"""

from __future__ import annotations

import argparse
import sys

from deals_bot.confluence import analyze_confluence
from deals_bot.formatter import format_confluence
from deals_bot.providers import fetch_best, fetch_fear_greed


def run(symbol: str, market: str, timeframe: str) -> int:
    print(f"⏳ تحليل {symbol} ({market}) على فريم {timeframe}...\n")
    try:
        series = fetch_best(symbol, market, timeframe=timeframe, limit=300)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ تعذّر جلب البيانات: {exc}")
        return 1
    if len(series) < 60:
        print("❌ بيانات غير كافية للتحليل.")
        return 1

    fg = None
    if market == "crypto":
        try:
            fg = fetch_fear_greed()
        except Exception:  # noqa: BLE001 - sentiment stays unavailable
            fg = None

    report = analyze_confluence(series, timeframe=timeframe, fear_greed=fg)
    print(format_confluence(report))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="تحليل تقاطع الأدلة متعدد المدارس لأصل واحد.")
    p.add_argument("--symbol", "-s", required=True, help="الرمز، مثل BTC-USD أو AAPL")
    p.add_argument("--market", "-m", choices=["crypto", "stocks", "forex"], default="crypto")
    p.add_argument("--timeframe", "-t", choices=["1m", "5m", "15m", "1h", "1d"], default="1h")
    args = p.parse_args(argv)
    return run(args.symbol, args.market, args.timeframe)


if __name__ == "__main__":
    sys.exit(main())

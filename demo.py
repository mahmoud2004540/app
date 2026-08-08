#!/usr/bin/env python3
"""
عرض توضيحي بدون إنترنت: يولّد بيانات اصطناعية ويعرض شكل مخرجات البوت.

Offline demo — generates synthetic price series and runs them through the real
analysis + formatting pipeline, so you can see exactly what the bot outputs
without needing a live network connection.

    python demo.py
"""

from __future__ import annotations

import math

from deals_bot import rank_deals
from deals_bot.formatter import format_deals
from deals_bot.models import Candle, Series


def _make_series(symbol, market, start, slope, wiggle, vol_mult=1.0, n=140):
    candles = []
    ts = 0.0
    for i in range(n):
        base = start + slope * i + wiggle * math.sin(i / 3.0)
        high = base * 1.006
        low = base * 0.994
        vol = 1000.0 * vol_mult * (1.4 if i > n - 3 else 1.0)
        candles.append(Candle(ts=ts, open=base, high=high, low=low, close=base, volume=vol))
        ts += 3600
    return Series(symbol=symbol, market=market, candles=candles)


def main() -> None:
    series = [
        _make_series("BTC-USD", "crypto", 60000, 90, 400, vol_mult=1.6),   # strong up
        _make_series("ETH-USD", "crypto", 3000, 6, 25, vol_mult=1.2),      # mild up
        _make_series("SOL-USD", "crypto", 150, -0.35, 3.0),               # down
        _make_series("AAPL", "stocks", 190, 0.4, 2.0, vol_mult=1.3),       # up
        _make_series("EURUSD=X", "forex", 1.08, -0.0009, 0.006),          # down
    ]
    deals = rank_deals(series, top=5, direction="any")
    print(format_deals(deals, title="عرض توضيحي — أفضل الصفقات (بيانات اصطناعية)"))


if __name__ == "__main__":
    main()

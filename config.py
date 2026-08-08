"""
الإعدادات: قوائم المتابعة الافتراضية لكل سوق + الإطار الزمني الافتراضي.

Default watchlists and settings. Edit these lists to track the symbols you care
about. Symbol formats depend on the data source:

  yfinance:
    crypto : BTC-USD, ETH-USD, SOL-USD ...
    stocks : AAPL, MSFT, NVDA ...
    forex  : EURUSD=X, GBPUSD=X, USDJPY=X ...
  binance (crypto only):
    BTCUSDT, ETHUSDT, SOLUSDT ...
"""

# قوائم المتابعة عند استخدام مصدر yfinance (الافتراضي)
WATCHLISTS = {
    "crypto": [
        "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD",
        "ADA-USD", "DOGE-USD", "AVAX-USD", "LINK-USD", "MATIC-USD",
    ],
    "stocks": [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL",
        "META", "TSLA", "AMD", "NFLX", "JPM",
    ],
    "forex": [
        "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X",
        "USDCHF=X", "USDCAD=X", "NZDUSD=X", "EURGBP=X",
    ],
}

# قائمة الكريبتو عند استخدام مصدر binance
BINANCE_WATCHLIST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "MATICUSDT",
]

DEFAULT_TIMEFRAME = "1h"
DEFAULT_TOP = 5
DEFAULT_SOURCE = "yfinance"   # or "binance" (crypto only)

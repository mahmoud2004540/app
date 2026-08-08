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

# --- فلتر الجودة: لا تُعرض إلا الصفقات القوية ---
# أقل درجة ثقة (0..100) تُقبل بها الصفقة. ارفعها لصفقات أنضف وأقل عددًا.
# مضبوطة على 70 لتوازن بين الجودة وعدد الصفقات (كانت 75).
MIN_CONFIDENCE = 70

# --- تأكيد من إطار زمني أعلى ---
# تُقبل الصفقة فقط إذا اتفق اتجاهها مع الإطار الأعلى المقابل.
CONFIRM_HIGHER_TIMEFRAME = True
HIGHER_TIMEFRAME = {
    "1m": "15m",
    "5m": "1h",
    "15m": "1h",
    "1h": "1d",
    "1d": "1d",
}

# --- إدارة المخاطر ---
# رأس المال الافتراضي ونسبة المخاطرة لكل صفقة (لحساب حجم الصفقة المقترح).
ACCOUNT_BALANCE = 1000.0   # بعملتك (دولار مثلًا)
RISK_PER_TRADE = 0.01      # 1% من رأس المال لكل صفقة

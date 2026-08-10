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

# --- نطاق الفحص ---
# "all" = افحص كل عملات الكريبتو المتاحة بالدولار على Coinbase (مئات العملات،
#         تُجلب ديناميكيًا) + قوائم الأسهم/الفوركس الموسّعة أدناه.
# "watchlist" = اكتفِ بالقوائم القصيرة أعلاه (أسرع).
CRYPTO_UNIVERSE = "all"

# كم عملة كريبتو نفحص كحدّ أقصى عند "all" (حماية من الإفراط في الطلبات/الوقت)
MAX_CRYPTO_SYMBOLS = 400

# قائمة فوركس موسّعة (رئيسية + ثانوية + بعض المتقاطعات)
FOREX_UNIVERSE = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCHF=X", "USDCAD=X",
    "NZDUSD=X", "EURGBP=X", "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "EURAUD=X",
    "EURCHF=X", "EURCAD=X", "GBPCHF=X", "GBPCAD=X", "AUDCAD=X", "AUDNZD=X",
    "CADJPY=X", "CHFJPY=X", "NZDJPY=X", "USDSGD=X", "USDHKD=X", "USDMXN=X",
    "USDZAR=X", "USDTRY=X", "USDSEK=X", "USDNOK=X", "EURNZD=X", "GBPAUD=X",
]

# قائمة أسهم موسّعة (أكبر وأنشط الأسهم الأمريكية) — لا يمكن جلب كل الآلاف مجانًا
STOCKS_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", "NFLX", "JPM",
    "AVGO", "ORCL", "CRM", "ADBE", "INTC", "CSCO", "QCOM", "TXN", "AMAT", "MU",
    "BAC", "WFC", "GS", "MS", "C", "V", "MA", "PYPL", "SQ", "COIN",
    "DIS", "CMCSA", "T", "VZ", "KO", "PEP", "MCD", "SBUX", "NKE", "WMT",
    "COST", "HD", "LOW", "TGT", "PG", "JNJ", "PFE", "MRK", "ABBV", "LLY",
    "UNH", "CVX", "XOM", "BA", "CAT", "GE", "F", "GM", "UBER", "ABNB",
    "PLTR", "SNOW", "SHOP", "MRNA", "RIVN", "LCID", "SOFI", "DKNG", "ROKU", "ZM",
]

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

# --- دقة إشارات «ما قبل الاندفاع» ---
# أقل درجة لقبول إعداد قبل الاندفاع (تجميع/انضغاط/بداية كسر) بعد كل التأكيدات.
PREPUMP_MIN_SCORE = 70
# تأكيد من إطار زمني أعلى (يستبعد «السكينة الساقطة» — لسه بتنزل بقوة).
PREPUMP_HTF_CONFIRM = True

# --- أفضل الصفقات (الإعداد الرابح المُثبت بالباك-تِست) ---
# استراتيجية «الارتداد داخل الاتجاه الصاعد» بانتقائية شديدة أعطت توقّعًا موجبًا
# (+0.28R لكل صفقة، نجاح ~43%) على بيانات 1h حقيقية عند درجة ≥85 + فلتر السوق.
# البوت يفحص كل العملات ويعرض أفضل صفقة أو اثنتين فقط من هذا الصفّ الرابح.
TREND_MIN_SCORE = 85          # لا نعرض إلا أقوى الإعدادات (مصدر الأفضلية)
TREND_MARKET_REGIME = True    # لا نشتري إلا حين يكون السوق (BTC) فوق متوسّطه
TREND_TOP = 2                 # أفضل 1-2 صفقة فقط
TREND_RR = 2.0                # نسبة الهدف/المخاطرة (2:1)
# فلتر الاتجاه بعيد المدى: لا ندخل إلا لو السعر فوق EMA200 (اتجاه صاعد راسخ).
# يُفعَّل بعد إثبات فائدته عبر `backtest.py --strategy optimize`.
TREND_REQUIRE_EMA200 = False

# --- نشاط الحيتان (تدفّق الأموال الكبير) ---
# صفقات الحيتان (حجم ضخم + تدفّق أموال قوي) تتصدّر القائمة دائمًا وتُعلَّم بـ 🐋.
# اجعلها True لعرض صفقات الحيتان فقط (أندر لكن أقوى إشارة).
WHALE_ONLY = False

# --- إدارة المخاطر ---
# رأس المال الافتراضي ونسبة المخاطرة لكل صفقة (لحساب حجم الصفقة المقترح).
ACCOUNT_BALANCE = 1000.0   # بعملتك (دولار مثلًا)
RISK_PER_TRADE = 0.01      # 1% من رأس المال لكل صفقة

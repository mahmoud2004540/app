"""
اختبارات محلّل ICT / Smart Money Concepts — كلها من شموع مُصنّعة، بلا شبكة.

نتأكد إن كل عنصر يُحسب من الشموع فعلًا (هيكل، سيولة، FVG، OB، اندفاع،
بريميوم/ديسكاونت، كنس)، وإن المُنسّق يطبع NO TRADE تحت العتبة والقالب الكامل فوقها.
"""

from deals_bot import ict
from deals_bot.models import Candle, Series


def _series(symbol, rows, market="crypto"):
    """rows = (open, high, low, close, volume)."""
    candles = []
    ts = 0.0
    for o, h, l, c, v in rows:
        candles.append(Candle(ts=ts, open=o, high=h, low=l, close=c, volume=v))
        ts += 3600
    return Series(symbol=symbol, market=market, candles=candles)


import math


def _uptrend(n=120, start=100.0, slope=0.5):
    # ميل صاعد + تمويج → قمم/قيعان صاعدة حقيقية (higher highs & higher lows)
    rows = []
    for i in range(n):
        p = start + slope * i + 2.0 * math.sin(i / 3.0)
        rows.append((p - 0.2, p + 0.8, p - 0.8, p + 0.2, 1000.0))
    return _series("UP", rows)


def _downtrend(n=120, start=200.0, slope=0.5):
    rows = []
    for i in range(n):
        p = start - slope * i + 2.0 * math.sin(i / 3.0)
        rows.append((p + 0.2, p + 0.8, p - 0.8, p - 0.2, 1000.0))
    return _series("DOWN", rows)


# ------------------------------ structure --------------------------------- #
def test_structure_bullish_and_bearish():
    up = ict.market_structure(_uptrend())
    dn = ict.market_structure(_downtrend())
    assert up["bias"] == "bullish"
    assert dn["bias"] == "bearish"


# ------------------------------ liquidity --------------------------------- #
def test_prev_period_levels():
    rows = [(10, 12, 9, 11, 100) for _ in range(10)]
    rows[-2] = (10, 15, 8, 11, 100)          # اليوم السابق: قمة 15 قاع 8
    lv = ict.prev_period_levels(_series("X", rows))
    assert lv["pdh"] == 15 and lv["pdl"] == 8
    assert lv["pwh"] is not None and lv["pwl"] is not None


def test_equal_levels_clusters_repeats():
    # قمّتان متساويتان عند ~50 (سيولة مكدّسة)
    rows = []
    for i in range(40):
        base = 40 + (10 if i in (10, 24) else 0)   # قمّتان عند 50
        rows.append((base - 1, base + (0.02 if i in (10, 24) else 0.0), base - 1, base, 100))
    eq_h, _eq_l = ict.equal_levels(_series("EQ", rows), tol=0.01, left=1, right=1)
    assert any(abs(h - 50) < 1 for h in eq_h)


# --------------------------- price delivery ------------------------------- #
def test_displacement_detects_big_candle():
    rows = [(100, 100.5, 99.5, 100, 100) for _ in range(20)]
    rows.append((100, 110, 100, 109, 500))     # شمعة اندفاع ضخمة صاعدة
    bull, bear, strength = ict.displacement(_series("D", rows))
    assert bull is True and strength > 1.5


def test_bullish_fvg_zone_found():
    rows = [(10, 10.5, 9.5, 10, 100) for _ in range(6)]
    # فجوة صاعدة: high شمعة A < low شمعة C
    rows += [(10, 10.5, 9.5, 10, 100), (10, 13, 10, 12.8, 300), (12.9, 13.5, 11.0, 13.2, 200)]
    z = ict.find_bullish_fvg(_series("F", rows))
    assert z is not None and z.kind == "fvg" and z.high > z.low


def test_bullish_ob_found():
    rows = [(10, 10.4, 9.6, 10, 100) for _ in range(6)]
    rows.append((10.2, 10.3, 9.7, 9.8, 100))   # شمعة هابطة (مرشّح OB)
    rows.append((9.9, 11.5, 9.9, 11.3, 300))   # اندفاع يكسر قمّتها (10.3)
    z = ict.find_bullish_ob(_series("O", rows))
    assert z is not None and z.kind == "ob"


def test_premium_discount_zone():
    up = ict.premium_discount(_uptrend())
    assert up["zone"] in ("premium", "discount")
    assert up["eq"] is not None and up["high"] > up["low"]


def test_liquidity_sweep_detected():
    rows = [(10, 10.5, 9.5, 10, 100) for _ in range(6)]
    rows.append((10, 10.2, 8.5, 10.1, 100))    # كنس تحت 9.5 ثم إغلاق فوقه
    assert ict.liquidity_sweep_of(_series("S", rows), 9.5) is True
    assert ict.liquidity_sweep_of(_series("S", rows), 5.0) is False


# --------------------------- end-to-end + format -------------------------- #
def test_analyze_ict_runs_via_fetch_stub():
    def _fetch(sym, market, tf, limit):
        # نفس السلسلة الصاعدة لكل الفريمات (يكفي لتشغيل المسار كاملًا بلا خطأ)
        return _uptrend(n=max(limit, 120))
    s = ict.analyze_ict("UP-USD", _fetch)
    assert s is not None
    assert 0 <= s.score <= 100
    assert set(s.breakdown.keys()) >= {"HTF Bias", "Liquidity", "Market Structure",
                                       "Displacement", "FVG/OB", "Entry Confirmation",
                                       "Risk/Reward"}


def test_format_no_trade_below_threshold():
    s = ict.ICTSetup(symbol="X-USD", market="crypto", price=1.0,
                     htf_bias="ranging", score=55.0,
                     blockers=["لا كنس سيولة واضح"])
    out = ict.format_ict(s)
    assert "NO TRADE" in out
    assert "55/100" in out


def test_format_tradeable_full_template():
    s = ict.ICTSetup(
        symbol="BTC-USD", market="crypto", price=100.0, htf_bias="bullish",
        entry=98.0, stop=95.0, tp1=104.0, tp2=110.0, tp3=116.0, invalidation=95.0,
        rr=4.0, score=88.0, liquidity_target="buy-side 104", liquidity_sweep="96 (تم الكنس)",
        entry_zone="FVG 97–99 (discount)",
        breakdown={"HTF Bias": 20, "Liquidity": 20, "Market Structure": 13,
                   "Displacement": 15, "FVG/OB": 10, "Entry Confirmation": 6,
                   "Risk/Reward": 10},
        reasons=["HTF Bias صاعد", "كنس سيولة"], blockers=[])
    out = ict.format_ict(s)
    for tag in ("Market:", "HTF Bias:", "Entry:", "SL:", "TP1:", "TP2:", "TP3:",
                "Setup Score:", "Invalidation:", "Risk/Reward:"):
        assert tag in out
    assert "88/100" in out

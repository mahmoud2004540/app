"""اختبارات تحكّم مخاطر المحفظة المحترف: heat + correlation — offline."""

import math

from deals_bot import indicators as ind
from deals_bot import paper_trading as pt
from deals_bot.bot_loop import run_cycle
from deals_bot.models import Candle, Series
from deals_bot.risk_engine import RiskConfig, RiskEngine


def test_returns_correlation_extremes():
    up_a = [100 + i for i in range(60)]
    up_b = [50 + 0.5 * i for i in range(60)]
    assert ind.returns_correlation(up_a, up_b, 50) > 0.99
    zig = [100 + (1 if i % 2 else -1) for i in range(60)]
    zag = [100 - (1 if i % 2 else -1) for i in range(60)]
    assert ind.returns_correlation(zig, zag, 50) < -0.99


def test_returns_correlation_none_when_short():
    assert ind.returns_correlation([1, 2, 3], [1, 2, 3], 50) is None


def _uptrend(n=600, seed=0.0):
    out = []
    for i in range(n):
        base = 100 + i * 0.4 + seed + (-3.0 if (i % 20) in (10, 11) else 0.0)
        out.append(Candle(ts=i, open=base, high=max(base, base + 0.5) + 0.8,
                          low=min(base, base + 0.5) - 1.2, close=base + 0.5, volume=1000.0))
    return out


def _engine(**kw):
    cfg = dict(risk_per_trade=0.005, max_open_positions=10, fee_rate=0.0,
               slippage_rate=0.0, min_rr=2.0, max_portfolio_heat=0.02,
               max_correlation=0.85)
    cfg.update(kw)
    return RiskEngine(RiskConfig(**cfg))


def test_portfolio_heat_caps_concurrent_positions():
    # heat 2% مع مخاطرة 0.5%/صفقة → أقصى 4 صفقات مفتوحة
    acc = pt.PaperAccount(equity=1000.0, starting_equity=1000.0, day_start_equity=1000.0)
    # 4 عملات صاعدة مختلفة قليلًا (غير مرتبطة تمامًا لتفادي فلتر الارتباط)
    data = {f"C{i}-USD": _uptrend(seed=i * 5) for i in range(6)}
    # كسر الارتباط: نضيف تذبذبًا مختلفًا لكل عملة
    for i, (sym, candles) in enumerate(data.items()):
        for j, c in enumerate(candles):
            bump = ((j * (i + 1)) % 7 - 3) * 0.15
            c.close += bump
            c.high = max(c.high, c.close + 0.1)
            c.low = min(c.low, c.close - 0.1)
    fetch = lambda s, m, tf, l: Series(s, "crypto", data[s])
    run_cycle(acc, list(data), fetch, now_ts=86400 * 2, engine=_engine(),
              fetch_confirm=fetch)
    # لا يتجاوز حدّ المحفظة: 4 صفقات كحدّ أقصى (2% / 0.5%)
    assert len(acc.positions) <= 4


def test_correlation_blocks_second_identical_coin():
    acc = pt.PaperAccount(equity=1000.0, starting_equity=1000.0, day_start_equity=1000.0)
    # عملتان متطابقتان تمامًا → الثانية يجب أن تُرفض للارتباط
    candles = _uptrend()
    data = {"AAA-USD": candles, "BBB-USD": [Candle(**vars(c)) for c in candles]}
    fetch = lambda s, m, tf, l: Series(s, "crypto", data[s])
    run_cycle(acc, ["AAA-USD", "BBB-USD"], fetch, now_ts=86400 * 2,
              engine=_engine(max_portfolio_heat=0.10), fetch_confirm=fetch)
    # مش هيفتح الاتنين (متطابقين) — واحدة بحدّ أقصى
    assert len(acc.positions) <= 1

"""اختبار تقرير الأداء لتيليجرام — offline."""

from deals_bot import paper_trading as pt
from deals_bot.performance import compute
from deals_bot.report import build_report

_RISK = {"risk_pct": 0.5, "daily": 1.5, "consec": 3, "rr": 2.0, "max_open": 5}


def test_report_contains_sections_empty_account():
    acc = pt.PaperAccount(equity=1000.0, starting_equity=1000.0)
    txt = build_report(acc, compute(acc), [], _RISK)
    assert "لوحة أداء بوت التداول" in txt
    assert "التداول الحقيقي: مُعطَّل" in txt
    assert "محرّك المخاطر" in txt
    assert "لا صفقات مفتوحة" in txt
    assert "الأفضلية المُثبتة" in txt


def test_report_shows_open_position_and_metrics():
    acc = pt.PaperAccount(equity=1020.0, starting_equity=1000.0)
    pt.open_position(acc, "SOL-USD", "crypto", "BUY", 100.0, 98.0, 104.0, 2.5, 1,
                     fee_rate=0.0, slippage_rate=0.0, ai_score=88.0)
    acc.closed = [pt.ClosedTrade("X", "BUY", 100, 104, 1, 20.0, 0.0, 2.0, "target", 0, 1)]
    txt = build_report(acc, compute(acc), [], _RISK)
    assert "SOL-USD" in txt and "AI 88" in txt
    assert "نسبة النجاح: 100%" in txt

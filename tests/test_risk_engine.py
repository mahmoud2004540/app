"""اختبارات محرّك المخاطر المستقل — النواة الحرجة للأمان (offline)."""

import math

from deals_bot.risk_engine import DailyState, RiskConfig, RiskEngine


def _engine():
    return RiskEngine(RiskConfig(
        risk_per_trade=0.005, max_daily_loss_pct=0.015,
        max_consecutive_losses=3, min_rr=2.0, max_open_positions=5,
        fee_rate=0.0, slippage_rate=0.0,
    ))


def test_position_size_risks_half_percent():
    eng = _engine()
    # رأس مال 1000، مخاطرة 0.5% = 5؛ خسارة الوحدة عند الوقف = 2 → 2.5 وحدة
    qty, risk_amount = eng.position_size(1000.0, entry=100.0, stop=98.0)
    assert math.isclose(risk_amount, 5.0, rel_tol=1e-9)
    assert math.isclose(qty, 2.5, rel_tol=1e-9)


def test_position_size_accounts_for_fees_and_slippage():
    eng = RiskEngine(RiskConfig(risk_per_trade=0.005, fee_rate=0.001, slippage_rate=0.0005))
    qty, risk_amount = eng.position_size(1000.0, entry=100.0, stop=98.0)
    # التكلفة الإضافية تُصغّر الحجم مقارنةً بلا رسوم (2.5)
    assert qty < 2.5 and risk_amount == 5.0


def test_daily_loss_limit_blocks_new_trades():
    eng = _engine()
    # خسارة يومية 1.6% > 1.5% → يُمنع
    daily = DailyState(starting_equity=1000.0, current_equity=984.0)
    assert eng.can_open_new_trade(daily).approved is False
    # خسارة 1.0% < 1.5% → يُسمح
    ok = DailyState(starting_equity=1000.0, current_equity=990.0)
    assert eng.can_open_new_trade(ok).approved is True


def test_three_consecutive_losses_stops_bot():
    eng = _engine()
    daily = DailyState(starting_equity=1000.0, current_equity=1000.0, consecutive_losses=3)
    assert eng.can_open_new_trade(daily).approved is False
    daily2 = DailyState(starting_equity=1000.0, current_equity=1000.0, consecutive_losses=2)
    assert eng.can_open_new_trade(daily2).approved is True


def test_max_open_positions_blocks():
    eng = _engine()
    daily = DailyState(starting_equity=1000.0, current_equity=1000.0, open_positions=5)
    assert eng.can_open_new_trade(daily).approved is False


def test_reward_risk_gate_rejects_below_1_to_2():
    eng = _engine()
    # RR = 1.0 < 2 → مرفوض
    assert eng.check_reward_risk(100.0, 98.0, 102.0).approved is False
    # RR = 2.0 → مقبول
    assert eng.check_reward_risk(100.0, 98.0, 104.0).approved is True


def test_stop_move_cannot_increase_risk():
    eng = _engine()
    # شراء: خفض الوقف من 98 إلى 96 يزيد المخاطرة → ممنوع
    assert eng.validate_stop_move("BUY", 100.0, 98.0, 96.0).approved is False
    # رفع الوقف إلى 99 (نحو التعادل) يقلّل المخاطرة → مسموح
    assert eng.validate_stop_move("BUY", 100.0, 98.0, 99.0).approved is True


def test_risk_engine_is_independent_of_ai():
    # محرّك المخاطر لا يستورد الـ AI/الاستراتيجية إطلاقًا
    import deals_bot.risk_engine as re
    src = open(re.__file__, encoding="utf-8").read()
    assert "analyzer" not in src and "confluence" not in src

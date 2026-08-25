"""اختبارات قسم «بداية الاندفاع» المنفصل المُرفَق برسائل الدخول الفوري (بدون شبكة)."""

import send_digest as sd
from deals_bot.models import Deal


def _deal(symbol, tf="1h"):
    d = Deal(
        symbol=symbol, market="crypto", direction="BUY",
        score=88, confidence=88, price=100.0,
        entry=100.0, stop_loss=95.0, take_profit=115.0, risk_reward=3.0,
        reasons=["بداية كسر بحجم"],
    )
    d.timeframe = tf
    return d


def _isolate_state(monkeypatch, tmp_path):
    monkeypatch.setattr(sd, "SENT_STATE", str(tmp_path / "sent.json"))
    monkeypatch.setattr(sd, "_heartbeat_due", lambda *a, **k: False)
    # السوق صاعد افتراضيًا حتى لا يتخطّى القسم بسبب فلتر السوق
    monkeypatch.setattr(sd, "market_is_bullish", lambda *a, **k: True)


def test_prepump_section_renders_new_setups_with_warning(monkeypatch, tmp_path):
    _isolate_state(monkeypatch, tmp_path)
    monkeypatch.setattr(sd, "scan_universe",
                        lambda *a, **k: ([], [_deal("AAA")], [_deal("BBB")]))
    out = sd._prepump_alert_section(["crypto"], "1h")
    assert out is not None
    assert "بداية اندفاع" in out
    assert "عالية المخاطرة" in out          # التحذير ظاهر
    assert "AAA" in out and "BBB" in out
    # سُجّلت الحالة بمفتاح PP: المنفصل
    sent = sd._load_sent()
    assert any(k.startswith("PP:") for k in sent)


def test_prepump_section_not_resent(monkeypatch, tmp_path):
    _isolate_state(monkeypatch, tmp_path)
    monkeypatch.setattr(sd, "scan_universe",
                        lambda *a, **k: ([], [], [_deal("BBB")]))
    first = sd._prepump_alert_section(["crypto"], "1h")
    assert first is not None
    # نفس الإعداد تاني → لا إعادة إرسال
    second = sd._prepump_alert_section(["crypto"], "1h")
    assert second is None


def test_prepump_section_skipped_in_bear_market(monkeypatch, tmp_path):
    _isolate_state(monkeypatch, tmp_path)
    monkeypatch.setattr(sd, "market_is_bullish", lambda *a, **k: False)
    called = {"n": 0}
    monkeypatch.setattr(sd, "scan_universe",
                        lambda *a, **k: called.__setitem__("n", called["n"] + 1) or ([], [], []))
    out = sd._prepump_alert_section(["crypto"], "1h")
    assert out is None
    assert called["n"] == 0                 # لم يُفحص الكون أصلًا في السوق الهابط


def test_prepump_section_none_when_no_setups(monkeypatch, tmp_path):
    _isolate_state(monkeypatch, tmp_path)
    monkeypatch.setattr(sd, "scan_universe", lambda *a, **k: ([], [], []))
    assert sd._prepump_alert_section(["crypto"], "1h") is None


def test_prepump_keys_do_not_collide_with_trend(monkeypatch, tmp_path):
    """مفاتيح PP: منفصلة عن مفاتيح الاتجاه (نفس العملة تظهر في القسمين بلا تعارض)."""
    _isolate_state(monkeypatch, tmp_path)
    monkeypatch.setattr(sd, "scan_universe",
                        lambda *a, **k: ([], [], [_deal("AAA", "1h")]))
    sd._prepump_alert_section(["crypto"], "1h")
    # صفقة اتجاه بنفس العملة تُرسَل عاديًا (مفتاح 1h:AAA غير PP:1h:AAA)
    td = _deal("AAA", "1h")
    td.confirmed = False
    msg = sd._alert_immediate_message([td], "1h", True)
    assert msg is not None and "AAA" in msg
    sent = sd._load_sent()
    assert "PP:1h:AAA" in sent and "1h:AAA" in sent

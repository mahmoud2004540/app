"""اختبارات وضع الإرسال الفوري + متابعة التأكيد (بدون شبكة)."""

import os

import send_digest as sd
from deals_bot.models import Deal


def _deal(symbol, tf, confirmed=None):
    d = Deal(
        symbol=symbol, market="crypto", direction="BUY",
        score=90, confidence=90, price=100.0,
        entry=100.0, stop_loss=95.0, take_profit=110.0, risk_reward=2.0,
        reasons=["اتجاه صاعد + ارتداد"],
    )
    d.timeframe = tf
    d.confirmed = confirmed
    return d


def _isolate_state(monkeypatch, tmp_path):
    monkeypatch.setattr(sd, "SENT_STATE", str(tmp_path / "sent.json"))
    # عطّل النبضة حتى يرجع None بوضوح حين لا جديد
    monkeypatch.setattr(sd, "_heartbeat_due", lambda *a, **k: False)


def test_new_pending_pick_is_sent_and_recorded(monkeypatch, tmp_path):
    _isolate_state(monkeypatch, tmp_path)
    d = _deal("AAA", "1h", confirmed=False)
    msg = sd._alert_immediate_message([d], "1h", True)
    assert msg is not None
    assert "AAA" in msg
    assert "بانتظار تأكيد" in msg
    sent = sd._load_sent()
    assert sent["1h:AAA"]["status"] == "pending"


def test_same_pending_pick_not_resent(monkeypatch, tmp_path):
    _isolate_state(monkeypatch, tmp_path)
    d = _deal("AAA", "1h", confirmed=False)
    sd._alert_immediate_message([d], "1h", True)
    # لا تأكيد بعد → لا متابعة، ولا إعادة إرسال لنفس الإعداد
    monkeypatch.setattr(sd, "_confirm_setup", lambda *a, **k: False)
    msg2 = sd._alert_immediate_message([d], "1h", True)
    assert msg2 is None


def test_followup_sent_when_pending_confirms(monkeypatch, tmp_path):
    import config
    monkeypatch.setattr(config, "ALERT_CONFIRM_FOLLOWUP", True)
    _isolate_state(monkeypatch, tmp_path)
    d = _deal("AAA", "1h", confirmed=False)
    sd._alert_immediate_message([d], "1h", True)      # أُرسلت معلّقة
    # الآن اكتمل التأكيد
    monkeypatch.setattr(sd, "_confirm_setup", lambda *a, **k: True)
    msg = sd._alert_immediate_message(None, "1h", True)   # لا فحص جديد
    assert msg is not None
    assert "اكتمل تأكيد" in msg and "AAA" in msg
    # الحالة أصبحت مؤكّدة (لا تتكرّر المتابعة)
    assert sd._load_sent()["1h:AAA"]["status"] == "confirmed"
    # نداء تالٍ لا يعيد المتابعة
    assert sd._alert_immediate_message(None, "1h", True) is None


def test_followup_disabled_sends_nothing(monkeypatch, tmp_path):
    """لما نطفّي المتابعة: الصفقة المعلّقة تتأكّد بس مفيش رسالة متابعة."""
    import config
    monkeypatch.setattr(config, "ALERT_CONFIRM_FOLLOWUP", False)
    _isolate_state(monkeypatch, tmp_path)
    d = _deal("AAA", "1h", confirmed=False)
    sd._alert_immediate_message([d], "1h", True)          # أُرسلت معلّقة
    monkeypatch.setattr(sd, "_confirm_setup", lambda *a, **k: True)
    assert sd._alert_immediate_message(None, "1h", True) is None   # لا متابعة


def test_confirmed_at_first_sight_no_followup(monkeypatch, tmp_path):
    import config
    monkeypatch.setattr(config, "ALERT_CONFIRM_FOLLOWUP", True)
    _isolate_state(monkeypatch, tmp_path)
    d = _deal("BBB", "1d", confirmed=True)
    msg = sd._alert_immediate_message([d], "1h", True)
    assert "BBB" in msg
    assert sd._load_sent()["1d:BBB"]["status"] == "confirmed"
    # لا متابعة لاحقة لأنها كانت مؤكّدة من البداية
    monkeypatch.setattr(sd, "_confirm_setup", lambda *a, **k: True)
    assert sd._alert_immediate_message(None, "1h", True) is None


def test_expired_setup_dropped(monkeypatch, tmp_path):
    _isolate_state(monkeypatch, tmp_path)
    import config
    monkeypatch.setattr(config, "SETUP_RESEND_HOURS", 12)
    # اكتب حالة قديمة جدًا
    sd._save_sent({"1h:OLD": {"sent_ts": 0, "status": "pending", "symbol": "OLD",
                              "market": "crypto", "timeframe": "1h",
                              "entry": 1, "stop": 0.9, "take_profit": 1.2, "score": 90}})
    # زمن كبير ⇒ العنصر منتهٍ ويُحذف؛ لا متابعة
    called = {"n": 0}
    monkeypatch.setattr(sd, "_confirm_setup",
                        lambda *a, **k: called.__setitem__("n", called["n"] + 1) or True)
    msg = sd._alert_immediate_message(None, "1h", True)
    assert msg is None
    assert called["n"] == 0                 # لم يُفحص المنتهي أصلًا
    assert "1h:OLD" not in sd._load_sent()

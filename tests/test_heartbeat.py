"""اختبارات النبضة اليومية في وضع «الدخول فقط» (offline بلا شبكة)."""

import os

import send_digest as sd


def test_heartbeat_due_then_not(tmp_path):
    sp = os.path.join(tmp_path, "hb.json")
    assert sd._heartbeat_due(sp) is True          # الملف مفقود → مستحقّة
    sd._mark_heartbeat(sp)
    assert sd._heartbeat_due(sp) is False          # سُجّلت اليوم → غير مستحقّة


def test_heartbeat_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr(sd.config, "HEARTBEAT_DAILY", False)
    sp = os.path.join(tmp_path, "hb.json")
    assert sd._heartbeat_due(sp) is False          # معطّلة → لا نبضة أبدًا


def test_heartbeat_message_mentions_entries_only():
    msg = sd._heartbeat_message("السوق العام: هابط")
    assert "الدخول فقط" in msg and "✅" in msg
    assert "هابط" in msg


def test_alert_only_defaults_to_config(monkeypatch):
    monkeypatch.delenv("ALERT_ONLY", raising=False)
    monkeypatch.setattr(sd.config, "ALERT_ONLY", True)
    assert sd._alert_only() is True
    monkeypatch.setenv("ALERT_ONLY", "0")          # البيئة تتجاوز config
    assert sd._alert_only() is False

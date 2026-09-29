from deals_bot import settings_store as ss


def test_save_clamps_and_locks_live(tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "PATH", str(tmp_path / "control_settings.json"))
    out = ss.save({"TREND_MIN_SCORE": 99, "LIVE_TRADING_ENABLED": True, "nope": 1})
    assert out["TREND_MIN_SCORE"] == 95
    assert "nope" not in out
    assert out["LIVE_TRADING_ENABLED"] is False


def test_apply_overrides(tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "PATH", str(tmp_path / "control_settings.json"))
    ss.save({"ALERT_ONLY": False, "TREND_RR": 2.0})

    class C:
        ALERT_ONLY = True
        TREND_RR = 1.5
        LIVE_TRADING_ENABLED = False

    ss.apply_overrides(C)
    assert C.ALERT_ONLY is False
    assert C.TREND_RR == 2.0
    assert C.LIVE_TRADING_ENABLED is False

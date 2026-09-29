"""مخزن إعدادات لوحة التحكم — يتجاوز قيم config ويرفع على main."""
from __future__ import annotations
import json, os, subprocess
from typing import Any
PATH = os.path.join("journal", "control_settings.json")
SCHEMA = {
    "TREND_MIN_SCORE": {"type": "float", "min": 50, "max": 95},
    "TREND_RR": {"type": "float", "min": 1.0, "max": 3.5},
    "INVESTMENT_RR": {"type": "float", "min": 0, "max": 4},
    "TREND_RSI_MAX": {"type": "float", "min": 50, "max": 80},
    "TREND_STOCH_MAX": {"type": "float", "min": 50, "max": 90},
    "TREND_FIB_MIN": {"type": "float", "min": 0.2, "max": 0.8},
    "TREND_FIB_MAX": {"type": "float", "min": 0.4, "max": 0.9},
    "TREND_VOL_SURGE_MIN": {"type": "float", "min": 1.0, "max": 3.0},
    "TREND_STOP_BUFFER_ATR": {"type": "float", "min": 0, "max": 2.5},
    "TREND_TRAIL_ACTIVATE_R": {"type": "float", "min": 0, "max": 2},
    "TREND_TRAIL_ATR": {"type": "float", "min": 1, "max": 4},
    "RISK_PER_TRADE_PRO": {"type": "float", "min": 0.001, "max": 0.02},
    "MAX_DAILY_LOSS_PCT": {"type": "float", "min": 0.005, "max": 0.05},
    "MAX_CONSECUTIVE_LOSSES": {"type": "int", "min": 1, "max": 8},
    "MIN_RISK_REWARD": {"type": "float", "min": 1.0, "max": 3.0},
    "MAX_OPEN_POSITIONS": {"type": "int", "min": 1, "max": 10},
    "ACCOUNT_BALANCE": {"type": "float", "min": 50, "max": 100000},
    "ICT_MIN_SCORE": {"type": "float", "min": 60, "max": 95},
    "CONFIRM_VOLUME_MULT": {"type": "float", "min": 1.0, "max": 2.5},
    "SETUP_RESEND_HOURS": {"type": "float", "min": 1, "max": 72},
    "STREAK_WARN_THRESHOLD": {"type": "int", "min": 2, "max": 8},
    "MAX_CRYPTO_SYMBOLS": {"type": "int", "min": 50, "max": 2000},
    "TREND_REQUIRE_EMA200": {"type": "bool"},
    "TREND_REQUIRE_MACD": {"type": "bool"},
    "TREND_REQUIRE_MOMENTUM": {"type": "bool"},
    "TREND_ANTI_REVERSAL": {"type": "bool"},
    "TREND_MARKET_REGIME": {"type": "bool"},
    "ALERT_REQUIRE_CONFIRM": {"type": "bool"},
    "ALERT_CONFIRM_FOLLOWUP": {"type": "bool"},
    "ALERT_ONLY": {"type": "bool"},
    "ALERT_SCAN_REPORT": {"type": "bool"},
    "HEARTBEAT_DAILY": {"type": "bool"},
    "CORR_FILTER_ENABLED": {"type": "bool"},
    "STREAK_WARN_ENABLED": {"type": "bool"},
}
LOCKED = ("LIVE_TRADING_ENABLED",)
ALWAYS = {"CRYPTO_UNIVERSE": "all", "MAX_CRYPTO_SYMBOLS": 1000, "LIVE_TRADING_ENABLED": False}

def load() -> dict:
    try:
        with open(PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def persist_to_main() -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    try:
        subprocess.run(["git", "config", "user.name", "trading-bot"], check=False)
        subprocess.run(["git", "config", "user.email", "bot@users.noreply.github.com"], check=False)
        subprocess.run(["git", "add", PATH], check=False)
        diff = subprocess.run(["git", "diff", "--cached", "--quiet", PATH])
        if diff.returncode == 0:
            return
        subprocess.run(["git", "commit", "-m", "chore(settings): persist controls [skip ci]"], check=False)
        branch = os.environ.get("GITHUB_REF_NAME") or "main"
        subprocess.run(["git", "pull", "--rebase", "origin", branch], check=False)
        subprocess.run(["git", "push", "origin", f"HEAD:{branch}"], check=False)
        print("settings pushed to", branch)
    except Exception as exc:
        print("persist failed", exc)

def save(updates: dict) -> dict:
    current = load()
    cleaned = {}
    for key, raw in updates.items():
        if key not in SCHEMA or key in LOCKED:
            continue
        spec = SCHEMA[key]
        try:
            if spec["type"] == "bool":
                cleaned[key] = bool(raw) if not isinstance(raw, str) else raw.lower() in ("1", "true", "yes", "on")
            elif spec["type"] == "int":
                val = int(float(raw))
                val = max(int(spec["min"]), min(int(spec["max"]), val))
                cleaned[key] = val
            else:
                val = float(raw)
                val = max(float(spec["min"]), min(float(spec["max"]), val))
                cleaned[key] = val
        except (TypeError, ValueError):
            continue
    current.update(cleaned)
    current.update(ALWAYS)
    os.makedirs(os.path.dirname(PATH) or ".", exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(current, fh, ensure_ascii=False, indent=2)
    persist_to_main()
    return current

def apply_overrides(module: Any) -> None:
    data = load()
    data.update(ALWAYS)
    for key, val in data.items():
        if key in SCHEMA or key in ALWAYS:
            setattr(module, key, val)
    setattr(module, "LIVE_TRADING_ENABLED", False)
    setattr(module, "CRYPTO_UNIVERSE", "all")

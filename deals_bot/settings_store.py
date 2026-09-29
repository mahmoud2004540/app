"""مخزن إعدادات لوحة التحكم — يتجاوز قيم config بدون تعديل الملف الأصلي."""

from __future__ import annotations

import json
import os
from typing import Any

PATH = os.path.join("journal", "control_settings.json")

SCHEMA = {
    "TREND_MIN_SCORE": {"group": "دخول", "label": "أدنى درجة دخول", "type": "float", "min": 50, "max": 95, "step": 1},
    "TREND_RR": {"group": "دخول", "label": "العائد/المخاطرة", "type": "float", "min": 1.0, "max": 3.5, "step": 0.1},
    "INVESTMENT_RR": {"group": "دخول", "label": "هدف استثماري أبعد (0=إخفاء)", "type": "float", "min": 0, "max": 4, "step": 0.1},
    "TREND_RSI_MAX": {"group": "فلاتر", "label": "سقف RSI", "type": "float", "min": 50, "max": 80, "step": 1},
    "TREND_STOCH_MAX": {"group": "فلاتر", "label": "سقف Stochastic", "type": "float", "min": 50, "max": 90, "step": 1},
    "TREND_FIB_MIN": {"group": "فلاتر", "label": "فيبوناتشي من", "type": "float", "min": 0.2, "max": 0.8, "step": 0.01},
    "TREND_FIB_MAX": {"group": "فلاتر", "label": "فيبوناتشي إلى", "type": "float", "min": 0.4, "max": 0.9, "step": 0.01},
    "TREND_VOL_SURGE_MIN": {"group": "فلاتر", "label": "أقل اندفاع حجم (×)", "type": "float", "min": 1.0, "max": 3.0, "step": 0.1},
    "TREND_STOP_BUFFER_ATR": {"group": "مخاطر", "label": "هامش الوقف (×ATR)", "type": "float", "min": 0, "max": 2.5, "step": 0.1},
    "TREND_TRAIL_ACTIVATE_R": {"group": "مخاطر", "label": "تفعيل التتبع بعد (R)", "type": "float", "min": 0, "max": 2, "step": 0.1},
    "TREND_TRAIL_ATR": {"group": "مخاطر", "label": "مسافة التتبع (×ATR)", "type": "float", "min": 1, "max": 4, "step": 0.1},
    "RISK_PER_TRADE_PRO": {"group": "مخاطر", "label": "مخاطرة الصفقة (كسر عشري)", "type": "float", "min": 0.001, "max": 0.02, "step": 0.001},
    "MAX_DAILY_LOSS_PCT": {"group": "مخاطر", "label": "أقصى خسارة يومية", "type": "float", "min": 0.005, "max": 0.05, "step": 0.001},
    "MAX_CONSECUTIVE_LOSSES": {"group": "مخاطر", "label": "إيقاف بعد خسائر متتالية", "type": "int", "min": 1, "max": 8, "step": 1},
    "MIN_RISK_REWARD": {"group": "مخاطر", "label": "أقل RR لمحرّك المخاطر", "type": "float", "min": 1.0, "max": 3.0, "step": 0.1},
    "MAX_OPEN_POSITIONS": {"group": "مخاطر", "label": "أقصى صفقات مفتوحة", "type": "int", "min": 1, "max": 10, "step": 1},
    "ACCOUNT_BALANCE": {"group": "حساب", "label": "رأس المال الورقي", "type": "float", "min": 50, "max": 100000, "step": 10},
    "ICT_MIN_SCORE": {"group": "ICT", "label": "أدنى درجة ICT", "type": "float", "min": 60, "max": 95, "step": 1},
    "CONFIRM_VOLUME_MULT": {"group": "تأكيد", "label": "مضاعف حجم التأكيد", "type": "float", "min": 1.0, "max": 2.5, "step": 0.1},
    "SETUP_RESEND_HOURS": {"group": "تنبيه", "label": "ساعات منع إعادة الإرسال", "type": "float", "min": 1, "max": 72, "step": 1},
    "STREAK_WARN_THRESHOLD": {"group": "تنبيه", "label": "عتبة تنبيه سلسلة الخسارة", "type": "int", "min": 2, "max": 8, "step": 1},
    "TREND_REQUIRE_EMA200": {"group": "بوابات", "label": "يشترط EMA200", "type": "bool"},
    "TREND_REQUIRE_MACD": {"group": "بوابات", "label": "يشترط MACD صاعد", "type": "bool"},
    "TREND_REQUIRE_MOMENTUM": {"group": "بوابات", "label": "يشترط زخم مع الصفقة", "type": "bool"},
    "TREND_ANTI_REVERSAL": {"group": "بوابات", "label": "رفض شمعة الانعكاس", "type": "bool"},
    "TREND_MARKET_REGIME": {"group": "بوابات", "label": "لا شراء وسوق BTC هابط", "type": "bool"},
    "ALERT_REQUIRE_CONFIRM": {"group": "بوابات", "label": "أرسل بعد تأكيد الإطار الأدنى فقط", "type": "bool"},
    "ALERT_CONFIRM_FOLLOWUP": {"group": "بوابات", "label": "رسالة متابعة عند اكتمال التأكيد", "type": "bool"},
    "ALERT_ONLY": {"group": "بوابات", "label": "وضع الدخول فقط (صامت بدون صفقة)", "type": "bool"},
    "ALERT_SCAN_REPORT": {"group": "بوابات", "label": "تقرير بعد كل فحص", "type": "bool"},
    "HEARTBEAT_DAILY": {"group": "بوابات", "label": "نبضة يومية", "type": "bool"},
    "CORR_FILTER_ENABLED": {"group": "بوابات", "label": "فلتر الارتباط", "type": "bool"},
    "STREAK_WARN_ENABLED": {"group": "بوابات", "label": "تنبيه سلسلة الخسارة", "type": "bool"},
}

LOCKED = ("LIVE_TRADING_ENABLED",)


def load() -> dict:
    try:
        with open(PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


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
    current["LIVE_TRADING_ENABLED"] = False
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(current, fh, ensure_ascii=False, indent=2)
    return current


def apply_overrides(module: Any) -> None:
    data = load()
    for key, val in data.items():
        if key in SCHEMA:
            setattr(module, key, val)
    setattr(module, "LIVE_TRADING_ENABLED", False)

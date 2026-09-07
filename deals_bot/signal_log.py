"""
تسجيل صامت لميزات الإشارة (funding / OI / on-chain) عند إرسال كل صفقة حقيقية.

الهدف: نجمع بيانات *حيّة نظيفة* مع كل صفقة A+ يبعتها البوت، عشان بعد شهور (لمّا
تتجمّع ~50-100 صفقة بنتيجتها) نقيس هل أيٌّ من هذه الإشارات يتنبّأ بالنتيجة فعلًا.

⚠️ تسجيل فقط — لا يغيّر أي قرار للبوت. كله best-effort: أي فشل في الجلب لا يوقف
الإرسال ولا يكسر أي شيء (نسجّل None ونكمل). النتيجة (outcome) تُترك None وتُحسب
لاحقًا بإعادة تشغيل السعر من نقطة الدخول (عندنا entry/stop/target/التوقيت).
"""

from __future__ import annotations

import json
import os
import time
from typing import Optional

FEATURES_PATH = os.path.join("journal", "signal_features.jsonl")

# on-chain مقياس عام لشبكة BTC (نفس القيمة لكل الصفقات في نفس الدورة) → نخزّنه مؤقتًا.
_onchain_cache = {"ts": 0.0, "value": None}


def _onchain_change_7d(ttl: float = 3600.0) -> Optional[float]:
    now = time.time()
    if _onchain_cache["value"] is not None and now - _onchain_cache["ts"] < ttl:
        return _onchain_cache["value"]
    change = None
    try:
        from .altdata import build_onchain_lookup
        look = build_onchain_lookup("n-transactions", timespan="60days")
        change = look.change_at(now, lookback=7)
    except Exception:  # noqa: BLE001 - best-effort
        change = None
    _onchain_cache.update(ts=now, value=change)
    return change


def _funding_now(symbol: str) -> Optional[float]:
    try:
        from .funding import build_lookup
        return build_lookup(symbol, max_pages=1).at(time.time())
    except Exception:  # noqa: BLE001 - best-effort
        return None


def _oi_change_now(symbol: str) -> Optional[float]:
    try:
        from .altdata import build_oi_lookup
        return build_oi_lookup(symbol).change_at(time.time(), lookback=1)
    except Exception:  # noqa: BLE001 - best-effort
        return None


def log_signal_features(deal, timeframe: str, ts: Optional[float] = None) -> None:
    """اكتب سطرًا واحدًا بميزات الإشارة لصفقة كريبتو جديدة (يُستدعى مرّة لكل صفقة)."""
    if getattr(deal, "market", None) != "crypto":
        return  # funding/OI/on-chain كلها مقاييس كريبتو
    ts = ts if ts is not None else time.time()
    rec = {
        "logged_ts": ts,
        "symbol": deal.symbol,
        "timeframe": getattr(deal, "timeframe", None) or timeframe,
        "entry": getattr(deal, "entry", None),
        "stop": getattr(deal, "stop_loss", None),
        "target": getattr(deal, "take_profit", None),
        "direction": getattr(deal, "direction", "BUY"),
        "score": getattr(deal, "confidence", None),
        "funding": _funding_now(deal.symbol),
        "oi_change_pct": _oi_change_now(deal.symbol),
        "onchain_tx_change_7d_pct": _onchain_change_7d(),
        "outcome": None,   # تُحسب لاحقًا (win/loss) بإعادة تشغيل السعر
    }
    try:
        os.makedirs("journal", exist_ok=True)
        with open(FEATURES_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"📝 سُجّلت ميزات إشارة {deal.symbol} "
              f"(funding={rec['funding']}, oiΔ={rec['oi_change_pct']}, "
              f"onchainΔ={rec['onchain_tx_change_7d_pct']}).")
    except Exception as exc:  # noqa: BLE001 - التسجيل إضافة، لا يُفشل الإرسال
        print(f"⚠️ تعذّر تسجيل ميزات الإشارة: {exc}")

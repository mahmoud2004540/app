#!/usr/bin/env python3
"""أوامر تيليجرام من الموبايل — بدون كمبيوتر. التداول الحقيقي مقفول."""
from __future__ import annotations
import json, os, sys, urllib.parse, urllib.request
import config
from deals_bot.settings_store import apply_overrides, save
OFFSET_PATH = os.path.join("journal", "tg_offset.json")
HELP = (
    "🎛️ تحكم البوت من هنا (موبايل).\n"
    "/status الحالة\n"
    "/strict تشديد: تأكيد + زخم + منع انعكاس\n"
    "/normal الوضع العادي\n"
    "/scan_on تقرير كل فحص\n"
    "/scan_off صمت إلا الصفقة\n"
    "/help\n\n"
    "التداول الحقيقي مقفول. مفيش ضمان ربح."
)

def _api(token, method, params=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode("utf-8") if params else None
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _offset():
    try:
        with open(OFFSET_PATH, encoding="utf-8") as fh:
            return int(json.load(fh).get("offset", 0))
    except Exception:
        return 0

def _save_offset(value):
    os.makedirs("journal", exist_ok=True)
    with open(OFFSET_PATH, "w", encoding="utf-8") as fh:
        json.dump({"offset": value}, fh)

def _status():
    apply_overrides(config)
    keys = ["TREND_MIN_SCORE", "TREND_RR", "ALERT_REQUIRE_CONFIRM", "TREND_REQUIRE_MOMENTUM", "TREND_ANTI_REVERSAL", "ALERT_ONLY", "ALERT_SCAN_REPORT"]
    lines = ["📊 حالة البوت"]
    for k in keys:
        lines.append(f"{k} = {getattr(config, k, '—')}")
    lines.append("التداول الحقيقي: مقفول")
    return "\n".join(lines)

def _handle(text):
    cmd = (text or "").strip().split()[0].lower().split("@", 1)[0]
    if cmd in ("/start", "/help"):
        return HELP + "\n\n" + _status()
    if cmd == "/status":
        return _status()
    if cmd == "/strict":
        save({"ALERT_REQUIRE_CONFIRM": True, "TREND_REQUIRE_MOMENTUM": True, "TREND_ANTI_REVERSAL": True, "ALERT_ONLY": True})
        apply_overrides(config)
        return "✅ تم التشديد.\n" + _status()
    if cmd == "/normal":
        save({"ALERT_REQUIRE_CONFIRM": False, "TREND_REQUIRE_MOMENTUM": False, "TREND_ANTI_REVERSAL": False, "ALERT_ONLY": True})
        apply_overrides(config)
        return "✅ الوضع العادي.\n" + _status()
    if cmd == "/scan_on":
        save({"ALERT_SCAN_REPORT": True})
        return "✅ تقرير بعد كل فحص."
    if cmd == "/scan_off":
        save({"ALERT_SCAN_REPORT": False})
        return "✅ صامت إلا عند صفقة."
    if cmd.startswith("/"):
        return "أمر مش معروف.\n" + HELP
    return None

def process_inbox():
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = str(os.environ.get("TELEGRAM_CHAT_ID") or "")
    if not token or not chat_id:
        print("تخطي الأوامر")
        return 0
    apply_overrides(config)
    off = _offset()
    upd = _api(token, "getUpdates", {"timeout": "0", "limit": "50", "offset": str(off)})
    if not upd.get("ok"):
        print(upd)
        return 1
    max_id = off
    n = 0
    for item in upd.get("result") or []:
        uid = int(item.get("update_id") or 0)
        max_id = max(max_id, uid + 1)
        msg = item.get("message") or {}
        chat = str((msg.get("chat") or {}).get("id") or "")
        text = msg.get("text") or ""
        if chat != chat_id:
            continue
        reply = _handle(text)
        if not reply:
            continue
        _api(token, "sendMessage", {"chat_id": chat_id, "text": reply})
        n += 1
        print("cmd", text[:40])
    if max_id != off:
        _save_offset(max_id)
    print("done", n)
    return 0

if __name__ == "__main__":
    sys.exit(process_inbox())

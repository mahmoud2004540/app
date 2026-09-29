#!/usr/bin/env python3
"""أوامر تيليجرام من الموبايل."""
from __future__ import annotations
import json, os, sys, urllib.parse, urllib.request
import config
from deals_bot.settings_store import apply_overrides, save
OFFSET_PATH = os.path.join("journal", "tg_offset.json")
KEYBOARD = json.dumps({
    "keyboard": [["فحص الآن", "الحالة"], ["تشديد", "عادي"]],
    "resize_keyboard": True,
    "persistent": True,
}, ensure_ascii=False)
HELP = (
    "اضغط الأزرار تحت، أو اكتب:\n"
    "/سcan أو فحص الآن\n/status\n/strict\n/normal"
).replace("/سcan", "/scan")

def _api(token, method, params=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode("utf-8") if params else None
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))

def send_text(token, chat_id, text):
    return _api(token, "sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": KEYBOARD,
    })

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

def _quick_scan() -> str:
    apply_overrides(config)
    old_uni = getattr(config, "CRYPTO_UNIVERSE", "watchlist")
    config.CRYPTO_UNIVERSE = "watchlist"
    try:
        from deals_bot.formatter import format_picks
        from deals_bot.strategy import top_picks
        tf = (getattr(config, "TREND_TIMEFRAMES", None) or ["6h"])[0]
        picks, cands, bull = top_picks(["crypto"], timeframe=tf, top=3)
        state = "صاعد" if bull else ("هابط" if bull is False else "غير محدد")
        if picks:
            return f"🚨 فحص سريع ({tf}) — السوق {state}\n\n" + format_picks(picks)
        n = len(cands or [])
        return (
            f"🔕 مفيش صفقة دلوقتي.\n"
            f"الفحص اتعمل على القائمة المختصرة ({tf}).\n"
            f"السوق: {state}\n"
            f"مرشحين تحت العتبة: {n}\n"
            "البوت شغال وهيبعت لما تظهر صفقة مؤهلة."
        )
    except Exception as exc:
        return f"⚠️ الفحص فشل: {exc}"
    finally:
        config.CRYPTO_UNIVERSE = old_uni

def _norm(text):
    t = (text or "").strip().lower()
    t = t.split("@", 1)[0]
    aliases = {
        "حالة": "/status", "status": "/status",
        "تشديد": "/strict", "strict": "/strict",
        "عادي": "/normal", "normal": "/normal",
        "فحص الآن": "/scan", "فحص": "/scan", "scan": "/scan",
        "تقرير": "/scan_on",
        "صمت": "/scan_off",
        "مساعدة": "/help", "help": "/help", "start": "/start",
    }
    if t in aliases:
        return aliases[t]
    return t.split()[0] if t else ""

def _handle(text):
    cmd = _norm(text)
    if cmd in ("/start", "/help"):
        return HELP + "\n\n" + _status()
    if cmd == "/status":
        return _status()
    if cmd == "/scan":
        return _quick_scan()
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
    try:
        _api(token, "setMyCommands", {"commands": json.dumps([
            {"command": "scan", "description": "فحص الصفقات الآن"},
            {"command": "status", "description": "حالة البوت"},
            {"command": "strict", "description": "تشديد"},
            {"command": "normal", "description": "عادي"},
            {"command": "start", "description": "القائمة"},
        ], ensure_ascii=False)})
    except Exception as exc:
        print("setMyCommands", exc)
    if os.environ.get("ANNOUNCE") == "1":
        send_text(token, chat_id, "الأزرار ظهرت تحت. اضغط فحص الآن.\n" + HELP)
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
        send_text(token, chat_id, reply)
        n += 1
        print("cmd", text[:40])
    if max_id != off:
        _save_offset(max_id)
    print("done", n)
    return 0

if __name__ == "__main__":
    sys.exit(process_inbox())

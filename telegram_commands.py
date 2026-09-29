#!/usr/bin/env python3
"""أوامر تيليجرام من الموبايل."""
from __future__ import annotations
import json, os, sys, urllib.parse, urllib.request
import config
from deals_bot.settings_store import apply_overrides, save
OFFSET_PATH = os.path.join("journal", "tg_offset.json")
KEYBOARD = json.dumps({
    "keyboard": [
        ["فحص الآن", "صفقات سريعة"],
        ["الحالة", "تشديد", "عادي"],
    ],
    "resize_keyboard": True,
    "persistent": True,
}, ensure_ascii=False)
HELP = (
    "فحص الآن = 6س / يومي\n"
    "صفقات سريعة = 15د + نص ساعة + ساعة"
)

def _api(token, method, params=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode("utf-8") if params else None
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))

def send_text(token, chat_id, text):
    return _api(token, "sendMessage", {"chat_id": chat_id, "text": text, "reply_markup": KEYBOARD})

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

def _enable_30m():
    try:
        from deals_bot import providers
        providers._YF_RANGE["30m"] = ("30m", "1mo")
        providers._BINANCE_INTERVAL["30m"] = "30m"
        providers._COINBASE_GRAN["30m"] = 1800
        if hasattr(providers, "_OKX_BAR"):
            providers._OKX_BAR["30m"] = "30m"
    except Exception:
        pass
    htf = dict(getattr(config, "HIGHER_TIMEFRAME", {}) or {})
    htf["30m"] = "1h"
    config.HIGHER_TIMEFRAME = htf

def _status():
    apply_overrides(config)
    lines = ["📊 حالة البوت"]
    for k in ["TREND_MIN_SCORE", "TREND_RR", "ALERT_REQUIRE_CONFIRM", "TREND_ANTI_REVERSAL"]:
        lines.append(f"{k} = {getattr(config, k, '—')}")
    lines.append("التداول الحقيقي: مقفول")
    return "\n".join(lines)

def _fmt_none(picks, cands, bull, title, tfs, rr):
    state = "صاعد" if bull else ("هابط" if bull is False else "غير محدد")
    if picks:
        from deals_bot.formatter import format_picks
        return f"{title}\nالسوق {state} | {', '.join(tfs)} | هدف 1:{rr:g}\n\n" + format_picks(picks)
    n = len(cands or [])
    return (
        f"🔕 مفيش صفقة دلوقتي.\n{title}\n"
        f"الفريم: {', '.join(tfs)} | هدف 1:{rr:g} | السوق {state}\n"
        f"مرشحين تحت العتبة: {n}"
    )

def _run_scan(tfs, rr, title):
    apply_overrides(config)
    _enable_30m()
    old_uni = getattr(config, "CRYPTO_UNIVERSE", "watchlist")
    old_rr = getattr(config, "TREND_RR", 1.5)
    config.CRYPTO_UNIVERSE = "watchlist"
    config.TREND_RR = rr
    try:
        from deals_bot.strategy import top_picks, top_picks_multi
        if len(tfs) == 1:
            picks, cands, bull = top_picks(["crypto"], timeframe=tfs[0], top=3, rr=rr)
        else:
            picks, cands, bull = top_picks_multi(["crypto"], timeframes=tfs, top=3, rr=rr)
        return _fmt_none(picks, cands, bull, title, tfs, rr)
    except Exception as exc:
        return f"⚠️ الفحص فشل: {exc}"
    finally:
        config.CRYPTO_UNIVERSE = old_uni
        config.TREND_RR = old_rr

def _quick_scan():
    return _run_scan(list(getattr(config, "TREND_TIMEFRAMES", None) or ["6h", "1d"]), float(getattr(config, "TREND_RR", 1.5)), "🔍 فحص عادي")

def _fast_scan():
    return _run_scan(["15m", "30m", "1h"], 1.0, "⚡ صفقات سريعة — 15د / نص ساعة / ساعة")

def _norm(text):
    t = (text or "").strip().lower().split("@", 1)[0]
    aliases = {
        "حالة": "/status", "status": "/status",
        "تشديد": "/strict", "strict": "/strict",
        "عادي": "/normal", "normal": "/normal",
        "فحص الآن": "/scan", "فحص": "/scan", "scan": "/scan",
        "صفقات سريعة": "/fast", "سريع": "/fast", "fast": "/fast",
        "start": "/start", "help": "/help", "مساعدة": "/help",
    }
    return aliases.get(t, t.split()[0] if t else "")

def _handle(text):
    cmd = _norm(text)
    if cmd in ("/start", "/help"):
        return HELP + "\n\n" + _status()
    if cmd == "/status":
        return _status()
    if cmd == "/scan":
        return _quick_scan()
    if cmd == "/fast":
        return _fast_scan()
    if cmd == "/strict":
        save({"ALERT_REQUIRE_CONFIRM": True, "TREND_REQUIRE_MOMENTUM": True, "TREND_ANTI_REVERSAL": True, "ALERT_ONLY": True})
        apply_overrides(config)
        return "✅ تم التشديد.\n" + _status()
    if cmd == "/normal":
        save({"ALERT_REQUIRE_CONFIRM": False, "TREND_REQUIRE_MOMENTUM": False, "TREND_ANTI_REVERSAL": False, "ALERT_ONLY": True})
        apply_overrides(config)
        return "✅ الوضع العادي.\n" + _status()
    if cmd.startswith("/"):
        return "أمر مش معروف.\n" + HELP
    return None

def process_inbox():
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = str(os.environ.get("TELEGRAM_CHAT_ID") or "")
    if not token or not chat_id:
        return 0
    apply_overrides(config)
    off = _offset()
    upd = _api(token, "getUpdates", {"timeout": "0", "limit": "50", "offset": str(off)})
    if not upd.get("ok"):
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
    if max_id != off:
        _save_offset(max_id)
    print("done", n)
    return 0

if __name__ == "__main__":
    sys.exit(process_inbox())

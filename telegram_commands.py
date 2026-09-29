#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys, urllib.parse, urllib.request
import config
from deals_bot.settings_store import apply_overrides, save
OFFSET_PATH = os.path.join("journal", "tg_offset.json")
KEYBOARD = json.dumps({
    "keyboard": [
        ["فحص الآن", "بداية اندفاع"],
        ["صفقات سريعة", "الحالة"],
        ["تشديد", "عادي"],
    ],
    "resize_keyboard": True,
    "persistent": True,
}, ensure_ascii=False)
HELP = (
    "فحص الآن = دقة اتجاه\n"
    "بداية اندفاع = تجميع من القاع / أول الكسر\n"
    "مش بعد ما السعر يطلع 30%"
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
    for k in ["TREND_MIN_SCORE", "ALERT_REQUIRE_CONFIRM", "PREPUMP_ALERT_APPEND"]:
        lines.append(f"{k} = {getattr(config, k, '—')}")
    lines.append("التداول الحقيقي: مقفول")
    return "\n".join(lines)

def _still_at_start(deal) -> bool:
    """رفض العملة لو السعر اتمد بعيد عن منطقة الدخول."""
    price = float(getattr(deal, "price", 0) or 0)
    entry = float(getattr(deal, "entry", 0) or 0)
    stop = float(getattr(deal, "stop_loss", 0) or 0)
    if price <= 0 or entry <= 0:
        return False
    if price > entry * 1.06:
        return False
    if stop > 0:
        risk = abs(entry - stop)
        if risk > 0 and (price - entry) / risk > 0.35:
            return False
    return True

def _fmt_none(picks, cands, bull, title, tfs, rr):
    state = "صاعد" if bull else ("هابط" if bull is False else "غير محدد")
    if picks:
        from deals_bot.formatter import format_picks
        return f"{title}\nالسوق {state} | {', '.join(tfs)}\n\n" + format_picks(picks)
    n = len(cands or [])
    return f"🔕 مفيش صفقة دلوقتي.\n{title}\nالسوق {state}\nمرشحين: {n}"

def _run_scan(tfs, rr, title):
    apply_overrides(config)
    _enable_30m()
    old_uni = getattr(config, "CRYPTO_UNIVERSE", "all")
    config.CRYPTO_UNIVERSE = "all"
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

def _pump_scan():
    apply_overrides(config)
    config.CRYPTO_UNIVERSE = "all"
    save({"PREPUMP_ALERT_APPEND": True})
    try:
        from deals_bot.strategy import scan_universe
        from deals_bot.formatter import format_digest
        _signals, accums, earlies = scan_universe(["crypto"], timeframe="6h", top=8)
        accums = [d for d in (accums or []) if _still_at_start(d)][:3]
        earlies = [d for d in (earlies or []) if _still_at_start(d)][:2]
        parts = [
            "🚀 من البداية — تجميع/أول الكسر فقط",
            "مش بعد الصعود. لو السعر بعد عن القاع بأكتر من 6% بتتشال.",
            "نجاح المسار قريب ~27%. مش ضمان بمب.",
            "",
        ]
        if accums:
            parts.append(format_digest(accums, title="تجميع عند القاع (سعر البداية)"))
        if earlies:
            parts.append(format_digest(earlies, title="أول الكسر ولسه قريب من القاع"))
        if not accums and not earlies:
            parts.append("🔕 مفيش تجميع عند البداية دلوقتي. الشغلات اللي زي NMR بعد +30% متترفض.")
        return "\n".join(parts)
    except Exception as exc:
        return f"⚠️ فحص الاندفاع فشل: {exc}"

def _quick_scan():
    return _run_scan(list(getattr(config, "TREND_TIMEFRAMES", None) or ["6h", "1d"]), float(getattr(config, "TREND_RR", 1.5)), "🔍 فحص دقة")

def _fast_scan():
    return _run_scan(["15m", "30m", "1h"], 1.0, "⚡ صفقات سريعة")

def _norm(text):
    t = (text or "").strip().lower().split("@", 1)[0]
    aliases = {
        "حالة": "/status", "status": "/status",
        "تشديد": "/strict", "strict": "/strict",
        "عادي": "/normal", "normal": "/normal",
        "فحص الآن": "/scan", "فحص": "/scan", "scan": "/scan",
        "صفقات سريعة": "/fast", "سريع": "/fast", "fast": "/fast",
        "بداية اندفاع": "/pump", "بمب": "/pump", "pump": "/pump",
        "start": "/start", "help": "/help",
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
    if cmd == "/pump":
        return _pump_scan()
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

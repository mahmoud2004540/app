#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys, urllib.parse, urllib.request
import config
from deals_bot.settings_store import apply_overrides, save
OFFSET_PATH = os.path.join("journal", "tg_offset.json")
KEYBOARD = json.dumps({
    "keyboard": [
        ["فحص الآن", "بداية اندفاع"],
        ["مرشح بعيد", "صفقات سريعة"],
        ["الحالة", "تشديد", "عادي"],
    ],
    "resize_keyboard": True,
    "persistent": True,
}, ensure_ascii=False)
HELP = (
    "فحص الآن = دقة اتجاه\n"
    "صفقات سريعة = أول حركة على 15د/نص ساعة/ساعة\n"
    "صعود فائق مش مضمون. اللي طلع خلاص بيتشال."
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

def _early_picks(timeframes, limit=3):
    from deals_bot.strategy import scan_universe
    found = []
    for tf in timeframes:
        _signals, accums, earlies = scan_universe(["crypto"], timeframe=tf, top=6)
        for d in list(earlies or []) + list(accums or []):
            if _still_at_start(d):
                d.timeframe = tf
                found.append(d)
    uniq = {}
    for d in found:
        prev = uniq.get(d.symbol)
        if prev is None or float(getattr(d, "confidence", 0) or 0) > float(getattr(prev, "confidence", 0) or 0):
            uniq[d.symbol] = d
    return sorted(uniq.values(), key=lambda d: float(getattr(d, "confidence", 0) or 0), reverse=True)[:limit]

def _pump_scan():
    apply_overrides(config)
    config.CRYPTO_UNIVERSE = "all"
    save({"PREPUMP_ALERT_APPEND": True})
    try:
        from deals_bot.formatter import format_digest
        picks = _early_picks(["6h"], 3)
        parts = [
            "🚀 من البداية — 6 ساعات",
            "مش بعد الصعود. نجاح المسار قريب ~27%.",
            "",
        ]
        parts.append(format_digest(picks, title="تجميع/أول كسر") if picks else "🔕 مفيش تجميع عند البداية دلوقتي.")
        return "\n".join(parts)
    except Exception as exc:
        return f"⚠️ فحص الاندفاع فشل: {exc}"

def _moon_scan():
    apply_overrides(config)
    config.CRYPTO_UNIVERSE = "all"
    try:
        from deals_bot.formatter import format_digest
        picks = _early_picks(["1d", "6h"], 3)
        parts = [
            "🚀 مرشح بعيد — مش توقع 100x",
            "أغلب المرشحين بتموت. اللي طلع خلاص متترفض.",
            "",
        ]
        parts.append(format_digest(picks, title="عند القاع فقط") if picks else "🔕 مفيش مرشح قريب من القاع دلوقتي.")
        return "\n".join(parts)
    except Exception as exc:
        return f"⚠️ فحص المرشح البعيد فشل: {exc}"

def _quick_scan():
    return _run_scan(list(getattr(config, "TREND_TIMEFRAMES", None) or ["6h", "1d"]), float(getattr(config, "TREND_RR", 1.5)), "🔍 فحص دقة")

def _fast_scan():
    apply_overrides(config)
    _enable_30m()
    config.CRYPTO_UNIVERSE = "all"
    try:
        from deals_bot.formatter import format_digest
        picks = _early_picks(["15m", "30m", "1h"], 3)
        parts = [
            "⚡ صفقات سريعة — أول الحركة | 15د / نص ساعة / ساعة",
            "صعود فائق مش مضمون. اللي بعد عن الدخول بأكتر من 6% بيتشال.",
            "",
        ]
        parts.append(format_digest(picks, title="أول كسر سريع") if picks else "🔕 مفيش حركة سريعة لسه في أولها دلوقتي.")
        return "\n".join(parts)
    except Exception as exc:
        return f"⚠️ الفحص السريع فشل: {exc}"

def _norm(text):
    t = (text or "").strip().lower().split("@", 1)[0]
    aliases = {
        "حالة": "/status", "status": "/status",
        "تشديد": "/strict", "strict": "/strict",
        "عادي": "/normal", "normal": "/normal",
        "فحص الآن": "/scan", "فحص": "/scan", "scan": "/scan",
        "صفقات سريعة": "/fast", "سريع": "/fast", "fast": "/fast",
        "بداية اندفاع": "/pump", "بمب": "/pump", "pump": "/pump",
        "مرشح بعيد": "/moon", "100x": "/moon", "moon": "/moon",
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
    if cmd == "/moon":
        return _moon_scan()
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

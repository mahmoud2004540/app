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
    "الصفقة مش بتتبعت غير لو: درجة 80+ وهدف 1:2 ومش مطاردة.\n"
    "لو الشروط ناقصة: NO TRADE.\n"
    "النسبة مش مضمونة 90%."
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
    lines.append("بوابة الإرسال: 80+ / هدف 1:2 / من غير مطاردة")
    lines.append("التداول الحقيقي: مقفول")
    return "\n".join(lines)

def _num(deal, *names):
    for name in names:
        val = getattr(deal, name, None)
        if val is None and isinstance(deal, dict):
            val = deal.get(name)
        try:
            if val not in (None, ""):
                return float(val)
        except (TypeError, ValueError):
            continue
    return 0.0

def _score(deal):
    return _num(deal, "confidence", "score")

def _reward_risk(deal):
    entry = _num(deal, "entry")
    stop = _num(deal, "stop_loss", "stop")
    tp = _num(deal, "target", "tp2", "tp")
    if tp <= 0:
        targets = getattr(deal, "targets", None) or getattr(deal, "take_profits", None) or []
        if targets:
            last = targets[-1]
            tp = _num(last, "price") if not isinstance(last, (int, float)) else float(last)
    risk = abs(entry - stop)
    if entry <= 0 or risk <= 0 or tp <= 0:
        return 0.0
    return abs(tp - entry) / risk

def _still_at_start(deal) -> bool:
    price = _num(deal, "price")
    entry = _num(deal, "entry")
    stop = _num(deal, "stop_loss", "stop")
    if price <= 0 or entry <= 0 or stop <= 0:
        return False
    if price > entry * 1.04:
        return False
    risk = abs(entry - stop)
    if risk > 0 and (price - entry) / risk > 0.25:
        return False
    return True

def _passes(deal) -> bool:
    if _score(deal) < 80:
        return False
    if not _still_at_start(deal):
        return False
    rr = _reward_risk(deal)
    if rr and rr < 2:
        return False
    return True

def _keep(deals, limit=3):
    out = [d for d in (deals or []) if _passes(d)]
    out.sort(key=_score, reverse=True)
    return out[:limit]

def _fmt_none(picks, cands, bull, title, tfs, rr):
    picks = _keep(picks)
    state = "صاعد" if bull else ("هابط" if bull is False else "غير محدد")
    if picks:
        from deals_bot.formatter import format_picks
        return f"{title}\nالسوق {state} | {', '.join(tfs)} | هدف 1:{rr:g}\n\n" + format_picks(picks)
    return (
        f"NO TRADE — مفيش صفقة تستحق المخاطرة.\n{title}\n"
        f"الشرط: درجة 80+ وهدف 1:2 والسعر لسه عند الدخول.\n"
        f"السوق {state} | مرشحين اترفضوا: {len(cands or [])}"
    )

def _run_scan(tfs, rr, title):
    apply_overrides(config)
    _enable_30m()
    old_uni = getattr(config, "CRYPTO_UNIVERSE", "all")
    config.CRYPTO_UNIVERSE = "all"
    config.TREND_RR = max(rr, 2.0)
    try:
        from deals_bot.strategy import top_picks, top_picks_multi
        if len(tfs) == 1:
            picks, cands, bull = top_picks(["crypto"], timeframe=tfs[0], top=5, rr=config.TREND_RR)
        else:
            picks, cands, bull = top_picks_multi(["crypto"], timeframes=tfs, top=5, rr=config.TREND_RR)
        return _fmt_none(picks, cands, bull, title, tfs, config.TREND_RR)
    except Exception as exc:
        return f"⚠️ الفحص فشل: {exc}"
    finally:
        config.CRYPTO_UNIVERSE = old_uni

def _early_picks(timeframes, limit=3):
    from deals_bot.strategy import scan_universe
    found = []
    for tf in timeframes:
        _signals, accums, earlies = scan_universe(["crypto"], timeframe=tf, top=8)
        for d in list(earlies or []) + list(accums or []):
            d.timeframe = tf
            found.append(d)
    uniq = {}
    for d in _keep(found, 20):
        prev = uniq.get(d.symbol)
        if prev is None or _score(d) > _score(prev):
            uniq[d.symbol] = d
    return sorted(uniq.values(), key=_score, reverse=True)[:limit]

def _pump_scan():
    apply_overrides(config)
    config.CRYPTO_UNIVERSE = "all"
    try:
        from deals_bot.formatter import format_digest
        picks = _early_picks(["6h"], 2)
        if not picks:
            return "NO TRADE — مفيش بداية اندفاع بدرجة 80 وهدف 1:2 ولسه عند الدخول."
        return "🚀 بداية اندفاع بعد البوابة\nمش ضمان نسبة. القياس القديم ~27%.\n\n" + format_digest(picks, title="عد البوابة")
    except Exception as exc:
        return f"⚠️ فحص الاندفاع فشل: {exc}"

def _moon_scan():
    apply_overrides(config)
    config.CRYPTO_UNIVERSE = "all"
    try:
        from deals_bot.formatter import format_digest
        picks = _early_picks(["1d", "6h"], 2)
        if not picks:
            return "NO TRADE — مفيش مرشح بعيد عد البوابة. مش توقع 100x."
        return "🚀 مرشح بعيد بعد البوابة\nمش توقع 100x ومش نسبة 90%.\n\n" + format_digest(picks, title="عند الدخول فقط")
    except Exception as exc:
        return f"⚠️ فحص المرشح البعيد فشل: {exc}"

def _quick_scan():
    return _run_scan(list(getattr(config, "TREND_TIMEFRAMES", None) or ["6h", "1d"]), 2.0, "🔍 فحص دقة")

def _fast_scan():
    apply_overrides(config)
    _enable_30m()
    config.CRYPTO_UNIVERSE = "all"
    try:
        from deals_bot.formatter import format_digest
        picks = _early_picks(["15m", "30m", "1h"], 2)
        if not picks:
            return "NO TRADE — مفيش صفقة سريعة بدرجة 80 وهدف 1:2 ولسه عند الدخول."
        return "⚡ صفقات سريعة بعد البوابة\n15د / نص ساعة / ساعة. مش ضمان صعود فائق.\n\n" + format_digest(picks, title="أول الحركة فقط")
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
        save({"ALERT_REQUIRE_CONFIRM": True, "TREND_REQUIRE_MOMENTUM": True, "TREND_ANTI_REVERSAL": True, "ALERT_ONLY": True, "TREND_RR": 2.0, "TREND_MIN_SCORE": 85})
        apply_overrides(config)
        return "✅ البوابة متشددة.\n" + _status()
    if cmd == "/normal":
        save({"ALERT_REQUIRE_CONFIRM": True, "TREND_REQUIRE_MOMENTUM": True, "TREND_ANTI_REVERSAL": True, "ALERT_ONLY": True})
        apply_overrides(config)
        return "✅ التأكيد فضل شغال. البوابة متشالتش.\n" + _status()
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

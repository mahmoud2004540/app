#!/usr/bin/env python3
from __future__ import annotations
import json, os, re, sys, urllib.parse, urllib.request
import config
from deals_bot.settings_store import apply_overrides, save
OFFSET_PATH = os.path.join("journal", "tg_offset.json")
KEYBOARD = json.dumps({
    "keyboard": [
        ["فحص الآن", "بداية اندفاع"],
        ["مرشح بعيد", "صفقات سريعة"],
        ["ورقي", "الحالة"],
        ["تشديد", "عادي"],
    ],
    "resize_keyboard": True,
    "persistent": True,
}, ensure_ascii=False)
HELP = (
    "ابعت اسم العملة (BTC / NMR) للتحليل.\n"
    "ورقي = تفاصيل الحساب الورقي (\u0645ش فلوس حقيقية).\n"
    "عند NO TRADE هيظهر أسماء المرشحين وسبب الرفض.\n"
    "التداول الحقيقي مقفول."
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
    for k in ["TREND_MIN_SCORE", "TREND_RR", "RISK_PER_TRADE_PRO", "MAX_OPEN_POSITIONS"]:
        lines.append(f"{k} = {getattr(config, k, '—')}")
    lines.append("ورقي: شغال | مخاطرة عالية على الورق")
    lines.append("التداول الحقيقي: مقفول")
    return "\n".join(lines)

def _fnum(d, *names):
    for name in names:
        val = getattr(d, name, None)
        if val is None and isinstance(d, dict):
            val = d.get(name)
        try:
            if val not in (None, ""):
                return float(val)
        except (TypeError, ValueError):
            continue
    return 0.0

def _reject_reasons(d, min_score: float, min_rr: float, market_bullish) -> list:
    reasons = []
    conf = _fnum(d, "confidence", "score")
    if conf < min_score:
        reasons.append(f"درجة {conf:.0f}<{min_score:.0f}")
    if market_bullish is False:
        reasons.append("السوق هابط")
    if getattr(d, "_ema200_ok", True) is False:
        reasons.append("تحت EMA200")
    if getattr(d, "_rsi_ok", True) is False:
        reasons.append("RSI مرتفع")
    if getattr(d, "_confluence_ok", True) is False:
        reasons.append("تأكيدات ناقصة")
    entry = _fnum(d, "entry")
    stop = _fnum(d, "stop_loss", "stop")
    tp = _fnum(d, "take_profit", "target", "tp")
    price = _fnum(d, "price")
    if entry > 0 and stop > 0 and tp > 0:
        risk = abs(entry - stop)
        if risk > 0:
            rr = abs(tp - entry) / risk
            if rr < min_rr:
                reasons.append(f"هدف 1:{rr:.1f}<1:{min_rr:g}")
    if entry > 0 and price > 0 and price > entry * 1.04:
        reasons.append("مطاردة (السعر بعيد عن الدخول)")
    if not reasons:
        reasons.append("مش ضمن أفضل الترتيب / تنويع")
    return reasons

def _format_rejects(cands, picks=None, market_bullish=None, limit=8) -> str:
    pick_syms = {getattr(p, "symbol", None) for p in (picks or [])}
    min_score = float(getattr(config, "TREND_MIN_SCORE", 85) or 85)
    min_rr = float(getattr(config, "TREND_RR", 2.0) or 2.0)
    rows = []
    ordered = sorted(
        cands or [],
        key=lambda x: _fnum(x, "confidence", "score"),
        reverse=True,
    )
    for d in ordered:
        sym = getattr(d, "symbol", None)
        if not sym or sym in pick_syms:
            continue
        why = "، ".join(_reject_reasons(d, min_score, min_rr, market_bullish))
        conf = _fnum(d, "confidence", "score")
        tf = getattr(d, "timeframe", "") or ""
        rows.append(f"  • {sym} {tf} درجة {conf:.0f} — {why}")
        if len(rows) >= limit:
            break
    if not rows:
        return "مفيش مرشحين قريبين اتسجلوا في هذا الفحص."
    header = f"أقرب مرشحين (عرض {len(rows)} من {len(ordered)}) وليه اترفضوا:"
    return header + "\n" + "\n".join(rows)

def _paper_report() -> str:
    apply_overrides(config)
    path = os.path.join("journal", "paper_account.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return (
            "📄 الحساب الورقي لسه فاضي أو الملف مش موجود.\n"
            "البوت الورقي هيشتغل على الجدول. التداول الحقيقي مقفول."
        )
    equity = float(data.get("equity") or 0)
    start = float(data.get("starting_equity") or equity or 1)
    ret = (equity / start - 1.0) * 100.0 if start else 0.0
    positions = data.get("positions") or []
    closed = data.get("closed") or []
    wins = sum(1 for c in closed if float(c.get("pnl") or 0) > 0)
    losses = sum(1 for c in closed if float(c.get("pnl") or 0) < 0)
    n = len(closed)
    wr = (wins / n * 100.0) if n else 0.0
    gross_w = sum(float(c.get("pnl") or 0) for c in closed if float(c.get("pnl") or 0) > 0)
    gross_l = -sum(float(c.get("pnl") or 0) for c in closed if float(c.get("pnl") or 0) < 0)
    pf = (gross_w / gross_l) if gross_l > 0 else (float("inf") if gross_w > 0 else 0.0)
    risk = float(getattr(config, "RISK_PER_TRADE_PRO", 0.02) or 0.02)
    max_open = getattr(config, "MAX_OPEN_POSITIONS", 10)
    lines = [
        "📄 الحساب الورقي (مش فلوس حقيقية)",
        f"الرصيد: ${equity:.2f} | البداية: ${start:.2f} | العائد: {ret:+.2f}%",
        f"مفتوحة: {len(positions)} | مغلقة: {n} | فوز: {wins} | خسارة: {losses}",
        f"نسبة النجاح: {wr:.1f}% | عامل ربح: {pf if pf != float('inf') else '∞'}",
        f"مخاطرة الصفقة: {risk*100:.1f}% | أقصى مفتوح: {max_open}",
        "التداول الحقيقي: مقفول",
        "",
    ]
    if positions:
        lines.append("📌 صفقات مفتوحة:")
        for p in positions[:10]:
            lines.append(
                f"  {p.get('symbol')} {p.get('direction')} "
                f"دخول {p.get('entry')} وقف {p.get('stop')} هدف {p.get('target')} "
                f"كم {p.get('qty')}"
            )
    else:
        lines.append("📌 مفيش صفقات مفتوحة دلوقتي.")
    if closed:
        lines.append("")
        lines.append("🧼 آخر 5 صفقات مغلقة:")
        for c in closed[-5:][::-1]:
            pnl = float(c.get("pnl") or 0)
            mark = "+" if pnl >= 0 else ""
            lines.append(
                f"  {c.get('symbol')} {c.get('direction')} "
                f"{c.get('reason')} PnL {mark}{pnl:.2f} R={c.get('result_r')}"
            )
    lines.append("")
    lines.append("⚠️ ورقي فقط. المخاطرة عالية عمدًا على الورق.")
    return "\n".join(lines)

def _quick_scan():
    apply_overrides(config)
    try:
        from deals_bot.strategy import top_picks_multi
        from deals_bot.formatter import format_picks
        config.CRYPTO_UNIVERSE = "all"
        tfs = list(getattr(config, "TREND_TIMEFRAMES", None) or ["6h", "1d"])
        picks, cands, bull = top_picks_multi(["crypto"], timeframes=tfs, top=3, rr=2.0)
        rejects = _format_rejects(cands, picks, market_bullish=bull, limit=8)
        if picks:
            return "🔍 فحص دقة\n\n" + format_picks(picks) + "\n\n" + rejects
        state = "صاعد" if bull else ("هابط" if bull is False else "غير محدد")
        return (
            f"NO TRADE — مفيش صفقة عدت البوابة.\n"
            f"السوق: {state} | إجمالي مرشحين: {len(cands or [])}\n\n"
            + rejects
        )
    except Exception as exc:
        return f"⚠️ {exc}"

def _fast_scan():
    apply_overrides(config)
    try:
        from deals_bot.strategy import scan_universe
        from deals_bot.formatter import format_digest
        config.CRYPTO_UNIVERSE = "all"
        _, accums, earlies = scan_universe(["crypto"], timeframe="1h", top=8)
        all_c = list(earlies or []) + list(accums or [])
        picks = all_c[:2]
        if picks:
            return "⚡ صفقات سريعة\n\n" + format_digest(picks, title="سريع")
        if all_c:
            return "NO TRADE — مفيش صفقة سريعة قوية.\n\n" + _format_rejects(all_c, picks=[], limit=8)
        return "NO TRADE — مفيش مرشحين سريعين اتسجلوا."
    except Exception as exc:
        return f"⚠️ {exc}"

def _pump_scan():
    apply_overrides(config)
    try:
        from deals_bot.strategy import scan_universe
        from deals_bot.formatter import format_digest
        config.CRYPTO_UNIVERSE = "all"
        _, accums, earlies = scan_universe(["crypto"], timeframe="6h", top=8)
        all_c = list(accums or []) + list(earlies or [])
        picks = all_c[:2]
        if picks:
            return "🚀 بداية اندفاع\n\n" + format_digest(picks, title="اندفاع")
        if all_c:
            return "NO TRADE — مفيش بداية اندفاع قوية.\n\n" + _format_rejects(all_c, picks=[], limit=8)
        return "NO TRADE — مفيش مرشحين اندفاع اتسجلوا."
    except Exception as exc:
        return f"⚠️ {exc}"

def _moon_scan():
    return _pump_scan()

def _clean_query(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"^(?:تحليل|العملة|عملة|coin|analyze|check)\s*[:\-]?\s*", "", t, flags=re.I)
    t = t.strip().upper()
    t = re.sub(r"[^A-Z0-9\- ]", "", t)
    return t.strip()[:40]

def _coin_report(query: str) -> str:
    apply_overrides(config)
    q = _clean_query(query)
    try:
        req = urllib.request.Request(
            f"https://api.coingecko.com/api/v3/search?query={urllib.parse.quote(q)}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        coins = data.get("coins") or []
        if not coins:
            return f"معرفتش العملة: {query}"
        pick = next((c for c in coins if str(c.get("symbol", "")).upper() == q), coins[0])
        cid = pick.get("id")
        req2 = urllib.request.Request(
            f"https://api.coingecko.com/api/v3/coins/{cid}?localization=false&tickers=false&community_data=true&developer_data=true",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req2, timeout=25) as resp2:
            full = json.loads(resp2.read().decode("utf-8"))
        md = full.get("market_data") or {}
        price = float((md.get("current_price") or {}).get("usd") or 0)
        ath = float((md.get("ath") or {}).get("usd") or 0)
        rank = full.get("market_cap_rank")
        name = full.get("name")
        sym = str(full.get("symbol") or "").upper()
        need = (ath / price) if price and ath else None
        lines = [
            f"🔍 {name} ({sym})",
            f"السعر: ${price}",
            f"ATH: ${ath} | الترتيب: #{rank or '—'}",
        ]
        if need and need > 1:
            lines.append(f"للقمة محتاج ~×{need:.1f}")
        desc = ((full.get("description") or {}).get("en") or "")[:200]
        if desc:
            lines.append(f"وصف: {desc}...")
        lines.append("زي البيتكوين؟ لا (إلا BTC).")
        lines.append("⚠️ مش نصيحة مالية. التداول الحقيقي مقفول.")
        return "\n".join(lines)
    except Exception as e:
        return f"فشل التحليل: {e}"

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
        "ورقي": "/paper", "paper": "/paper", "حساب ورقي": "/paper",
        "start": "/start", "help": "/help",
    }
    if t in aliases:
        return aliases[t]
    if t.startswith("/"):
        return t.split()[0]
    return t

def _handle(text):
    raw = (text or "").strip()
    cmd = _norm(raw)
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
    if cmd == "/paper":
        return _paper_report()
    if cmd == "/strict":
        save({"ALERT_REQUIRE_CONFIRM": True, "TREND_REQUIRE_MOMENTUM": True, "TREND_ANTI_REVERSAL": True, "ALERT_ONLY": True})
        apply_overrides(config)
        return "✅ متشدد.\n" + _status()
    if cmd == "/normal":
        save({"ALERT_REQUIRE_CONFIRM": True, "TREND_REQUIRE_MOMENTUM": True, "TREND_ANTI_REVERSAL": True, "ALERT_ONLY": True})
        apply_overrides(config)
        return "✅ عادي.\n" + _status()
    cleaned = _clean_query(raw)
    if cleaned and len(cleaned) >= 2 and not cleaned.startswith("/") and re.fullmatch(r"[A-Z0-9][A-Z0-9\- ]{1,20}", cleaned):
        return _coin_report(cleaned)
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

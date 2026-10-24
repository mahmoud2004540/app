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
        ["ورقي", "خطة ادخار"],
        ["📐 نماذج احترافية"],
        ["الحالة", "تشديد", "عادي"],
    ],
    "resize_keyboard": True,
    "persistent": True,
}, ensure_ascii=False)
HELP = (
    "ابعت اسم العملة لتحليل عميق.\n"
    "خطة ادخار = SOL + FIL + TAO + ذهب ("
    "جاهز فورًا).\n"
    "ورقي = الحساب الورقي. التداول الحقيقي مقفول.\n"
    "📐 نماذج احترافية = وتد هابط / قاع مزدوج / علم صاعد (مُختبرة، في السوق الصاعد بس)."
)

def _api(token, method, params=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode("utf-8") if params else None
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))

def send_text(token, chat_id, text):
    if len(text) > 4000:
        text = text[:3990] + "\n…"
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

def _status():
    apply_overrides(config)
    lines = ["📊 حالة البوت"]
    for k in ["TREND_MIN_SCORE", "TREND_RR", "RISK_PER_TRADE_PRO", "MAX_OPEN_POSITIONS"]:
        lines.append(f"{k} = {getattr(config, k, '—')}")
    lines.append("خطة ادخار: SOL+FIL+TAO+ذهب")
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

def _reject_reasons(d, min_score, min_rr, market_bullish):
    reasons = []
    conf = _fnum(d, "confidence", "score")
    if conf < min_score:
        reasons.append(f"درجة {conf:.0f}<{min_score:.0f}")
    if market_bullish is False:
        reasons.append("السوق هابط")
    entry, stop, tp, price = _fnum(d, "entry"), _fnum(d, "stop_loss", "stop"), _fnum(d, "take_profit", "target", "tp"), _fnum(d, "price")
    if entry > 0 and stop > 0 and tp > 0:
        risk = abs(entry - stop)
        if risk > 0 and abs(tp - entry) / risk < min_rr:
            reasons.append("هدف ضعيف")
    if entry > 0 and price > entry * 1.04:
        reasons.append("مطاردة")
    if not reasons:
        reasons.append("مش ضمن أفضل الترتيب")
    return reasons

def _format_rejects(cands, picks=None, market_bullish=None, limit=8):
    pick_syms = {getattr(p, "symbol", None) for p in (picks or [])}
    min_score = float(getattr(config, "TREND_MIN_SCORE", 85) or 85)
    min_rr = float(getattr(config, "TREND_RR", 2.0) or 2.0)
    rows = []
    ordered = sorted(cands or [], key=lambda x: _fnum(x, "confidence", "score"), reverse=True)
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
        return "مفيش مرشحين قريبين."
    return f"أقرب مرشحين ({len(rows)}/{len(ordered)}):\n" + "\n".join(rows)

def _paper_report():
    apply_overrides(config)
    path = os.path.join("journal", "paper_account.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return "📄 الحساب الورقي لسه فاضي."
    equity = float(data.get("equity") or 0)
    start = float(data.get("starting_equity") or equity or 1)
    ret = (equity / start - 1.0) * 100.0 if start else 0.0
    positions = data.get("positions") or []
    closed = data.get("closed") or []
    n = len(closed)
    wins = sum(1 for c in closed if float(c.get("pnl") or 0) > 0)
    wr = (wins / n * 100.0) if n else 0.0
    lines = ["📄 ورقي", f"رصيد ${equity:.2f} | {ret:+.2f}%", f"مفتوح {len(positions)} | مغلق {n} | نجاح {wr:.1f}%"]
    for p in positions[:6]:
        lines.append(f"  {p.get('symbol')} {p.get('direction')} {p.get('entry')}")
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
            return "🔍 فحص\n\n" + format_picks(picks) + "\n\n" + rejects
        state = "صاعد" if bull else ("هابط" if bull is False else "?")
        return f"NO TRADE\nالسوق: {state} | مرشحين: {len(cands or [])}\n\n" + rejects
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
            return "⚡ سريع\n\n" + format_digest(picks, title="سريع")
        return "NO TRADE — مفيش صفقة سريعة." + ("\n\n" + _format_rejects(all_c, [], 8) if all_c else "")
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
            return "🚀 اندفاع\n\n" + format_digest(picks, title="اندفاع")
        return "NO TRADE — مفيش اندفاع." + ("\n\n" + _format_rejects(all_c, [], 8) if all_c else "")
    except Exception as exc:
        return f"⚠️ {exc}"

def _moon_scan():
    return _pump_scan()

# عملات مستقرة ونسخ مغلّفة — مفيش نماذج نتداولها عليها
_STABLES = {"USDT", "USDC", "DAI", "USD1", "FDUSD", "PYUSD", "TUSD", "USDE", "USDS", "USDG",
            "RLUSD", "EURC", "WBTC", "WETH", "STETH"}

def _patterns_scan():
    """النماذج الاحترافية المُختبرة: وتد هابط + قاع مزدوج (يومي)، علم صاعد (4 ساعات)."""
    import time
    from concurrent.futures import ThreadPoolExecutor
    from deals_bot import pro_patterns as pp
    from deals_bot.providers import fetch_okx, list_okx_usd_products
    now = time.time()
    try:
        bull = {tf: pp.market_bullish([x for x in fetch_okx("BTC-USD", tf, 300).candles
                                       if x.ts + pp.TF_SECONDS[tf] <= now]) for tf in ("1d", "4h")}
        syms = [s for s in list_okx_usd_products() if s.split("-")[0] not in _STABLES]
    except Exception as exc:
        return f"⚠️ {exc}"
    tfs = [tf for tf in ("1d", "4h") if bull.get(tf)]
    head = ("📐 نماذج احترافية (وتد هابط + قاع مزدوج يومي، علم صاعد 4 ساعات)\n"
            f"السوق (BTC فوق EMA200): يومي {'🟢' if bull.get('1d') else '🔴'} | "
            f"4 ساعات {'🟢' if bull.get('4h') else '🔴'}\n\n")
    if not tfs:
        return head + ("NO TRADE — السوق مش صاعد على الفريمين. النماذج دي بتكسب في السوق "
                       "الصاعد بس (مقاس) — بنستنى.")
    def scan(sym):
        found = []
        for tf in tfs:
            try:
                for d in pp.recent_setups(fetch_okx(sym, tf, 300).candles, tf, now):
                    d["symbol"] = sym
                    found.append(d)
            except Exception:
                pass
        return found
    with ThreadPoolExecutor(max_workers=8) as pool:
        setups = [d for group in pool.map(scan, syms) for d in group]
    if not setups:
        return head + f"NO TRADE — فحصت {len(syms)} عملة: مفيش نموذج اتكسر حديثًا ولسه مناسب للدخول."
    setups.sort(key=lambda d: (-pp.MEASURED[d["pattern"]][2], d["bars_ago"]))
    body = "\n\n".join(pp.format_setup(d) for d in setups[:5])
    return (head + body + "\n\n⚠️ مفيش صفقة مضمونة — النجاح التاريخي ~55% والربح من إن المكسب "
            "أكبر من الخسارة. التزم بالوقف.")

def _clean_query(text):
    t = (text or "").strip()
    t = re.sub(r"^(?:تحليل|العملة|عملة|coin|analyze|check)\s*[:\-]?\s*", "", t, flags=re.I)
    t = re.sub(r"[^A-Z0-9\- ]", "", t.strip().upper())
    return t.strip()[:40]

def _coin_report(query):
    apply_overrides(config)
    q = _clean_query(query)
    try:
        req = urllib.request.Request(f"https://api.coingecko.com/api/v3/search?query={urllib.parse.quote(q)}", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        coins = data.get("coins") or []
        if not coins:
            return f"معرفتش: {query}"
        pick = next((c for c in coins if str(c.get("symbol", "")).upper() == q), coins[0])
        cid = pick.get("id")
        req2 = urllib.request.Request(f"https://api.coingecko.com/api/v3/coins/{cid}?localization=false&tickers=false&community_data=true&developer_data=true", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req2, timeout=25) as resp2:
            full = json.loads(resp2.read().decode("utf-8"))
    except Exception as e:
        return f"فشل: {e}"
    md = full.get("market_data") or {}
    dd = full.get("developer_data") or {}
    def usd(key):
        v = md.get(key) or {}
        return float(v.get("usd") or 0) if isinstance(v, dict) else float(v or 0)
    name, sym = full.get("name") or cid, str(full.get("symbol") or "").upper()
    price, ath = usd("current_price"), usd("ath")
    rank = full.get("market_cap_rank") or 9999
    need = (ath / price) if price and ath and price > 0 else None
    commits = dd.get("commit_count_4_weeks")
    lines = [f"🔍 {name} ({sym})", f"${price} | ATH ${ath} | #{rank if rank < 9999 else '—'}"]
    if need and need > 1.05:
        lines.append(f"للقمة ~×{need:.1f}")
    lines.append(f"تطوير: commits 4أ = {commits if commits is not None else '—'}")
    lines.append("زي BTC؟ " + ("نعم" if sym == "BTC" else "لا"))
    lines.append("⚠️ مش نصيحة مالية.")
    return "\n".join(lines)

def _savings_help():
    return "💰 اضغط خطة ادخار — SOL + FIL + TAO + ذهب."

def _parse_savings(text):
    t = (text or "").strip()
    if not re.match(r"^(?:ادخار|/save|/plan)", t, flags=re.I):
        return None
    t = re.sub(r"^(?:ادخار|/save|/plan)\s*", "", t, flags=re.I)
    data = {"amount": None, "currency": "EUR", "emergency_months": None, "debt": None,
            "drawdown": 50.0, "experience": "متوسط", "country": "غير_محدد"}
    pairs = re.findall(
        r"(مبلغ|amount|عملة|currency|طوارئ|emergency|ديون|debt|نزول|drawdown|خبرة|experience|بلد|country)\s*[=:]\s*([^\s=]+)",
        t, flags=re.I)
    key_map = {"مبلغ": "amount", "amount": "amount", "عملة": "currency", "currency": "currency",
               "طوارئ": "emergency_months", "emergency": "emergency_months", "ديون": "debt", "debt": "debt",
               "نزول": "drawdown", "drawdown": "drawdown", "خبرة": "experience", "experience": "experience",
               "بلد": "country", "country": "country"}
    for k, v in pairs:
        kk = k.lower() if k.isascii() else k
        field = key_map.get(kk) or key_map.get(k)
        if not field: continue
        if field == "amount":
            try: data["amount"] = float(v.replace(",", "."))
            except ValueError: pass
        elif field == "currency": data["currency"] = v.upper()[:8]
        elif field == "emergency_months":
            try: data["emergency_months"] = float(v.replace(",", "."))
            except ValueError: pass
        elif field == "debt":
            data["debt"] = v.strip().lower() in ("نعم", "yes", "y", "true", "1")
        elif field == "drawdown":
            try: data["drawdown"] = float(v.replace("%", "").replace(",", "."))
            except ValueError: pass
        elif field == "experience": data["experience"] = v
        elif field == "country": data["country"] = v.replace("_", " ")
    if data["amount"] is None or data["emergency_months"] is None or data["debt"] is None:
        return {"_incomplete": True, "raw": data}
    return data

def _tax_note(country):
    c = (country or "").lower().replace(" ", "")
    notes = {"المانيا": "ألمانيا: Finanzamt", "germany": "ألمانيا: Finanzamt",
             "فرنسا": "فرنسا: PFU", "france": "فرنسا: PFU", "مصر": "مصر: مصلحة الضرائب", "egypt": "مصر: مصلحة الضرائب"}
    for k, v in notes.items():
        if k in c: return v
    return "راجع مصلحة الضرائب في بلدك"

_USER_BASKET = [
    ("SOL", "Solana", 35, "شبكة كبيرة · أعلى سيولة في السلة"),
    ("TAO", "Bittensor", 20, "سردية AI · تقلب أعلى"),
    ("FIL", "Filecoin", 15, "تخزين · أبعد عن ATH · أعلى مخاطرة في السلة"),
    ("GOLD", "ذهب", 30, "تنويع خارج الكريبتو · PAXG/XAUT أو ذهب فعلي"),
]

def _savings_plan(data):
    if data.get("_incomplete"):
        return "ناقص بيانات.\n" + _savings_help()
    amount = float(data["amount"]); cur = data["currency"]; em = float(data["emergency_months"])
    debt = bool(data["debt"]); dd = float(data["drawdown"]); exp = str(data["experience"])
    country = str(data["country"])
    lines = [
        "💰 خطة ادخار (سلتك)",
        f"{amount:g} {cur}/شهر | طوارئ {em:g} | ديون {'نعم' if debt else 'لا'}",
        f"نزول {dd:g}% | {exp} | {country}", "", "① الفحص",
    ]
    if debt:
        return "\n".join(lines + ["⛔ أصلح الديون الغالية أولًا.", "⚠️ مش نصيحة مالية."])
    if em < 3:
        return "\n".join(lines + [f"⛔ طوارئ {em:g} < 3 شهور.", "⚠️ مش نصيحة مالية."])
    lines.append(f"✅ طوارئ {em:g} شهر — تقدر تبدأ بحذر.")
    lines += ["", "② التوزيع الشهري (إطار تعليمي — مش توصية شراء)", "السلّة: SOL + FIL + TAO + ذهب"]
    for sym, name, pct, note in _USER_BASKET:
        amt = amount * pct / 100.0
        lines.append(f"• {sym} ({name}) {pct}% → {amt:g} {cur}")
        lines.append(f"  {note}")
    lines.append("• ميم / عشوائي: 0%")
    total = amount * 60
    lines += [
        "", "ملاحظات:",
        "• الذهب يقلل الارتباط بالكريبتو — PAXG/XAUT أو ذهب فعلي.",
        "• FIL أضعف حلقة (بعيدة عن ATH) — نسبتها الأقل.",
        "• SOL أكبر حصة كريبتو للسيولة.",
        "", "③ تنفيذ: يوم ثابت • شراء متكرر • 2FA",
        "", "④ محاكاة 5س (افتراض)", f"دفع: {total:g} {cur}",
        f"هبوط ~{total*0.45:g}–{total*0.75:g} | ثبات ~{total*0.9:g}–{total*1.2:g} | صعود ممكن {total*1.5:g}+",
        "", "⑤ قواعد: مراجعة 1–2/سنة • وقف عند فقدان الدخل",
        f"ضرايب: {_tax_note(country)}",
        "", "⑥ نصب: أرباح مضمونة • ضغط شراء • طلب كلمات سرية",
        "", "⚠️ مش نصيحة مالية. مش هنفترض صعود الأسعار.",
    ]
    return "\n".join(lines)

def _norm(text):
    t = (text or "").strip().lower().split("@", 1)[0]
    aliases = {
        "حالة": "/status", "status": "/status", "تشديد": "/strict", "strict": "/strict",
        "عادي": "/normal", "normal": "/normal", "فحص الآن": "/scan", "فحص": "/scan", "scan": "/scan",
        "صفقات سريعة": "/fast", "سريع": "/fast", "fast": "/fast",
        "بداية اندفاع": "/pump", "بمب": "/pump", "pump": "/pump",
        "مرشح بعيد": "/moon", "100x": "/moon", "moon": "/moon",
        "ورقي": "/paper", "paper": "/paper",
        "📐 نماذج احترافية": "/patterns", "نماذج احترافية": "/patterns", "نماذج": "/patterns",
        "patterns": "/patterns",
        "خطة ادخار": "/savings", "ادخار": "/savings", "savings": "/savings", "خطة": "/savings",
        "start": "/start", "help": "/help",
    }
    if t in aliases: return aliases[t]
    if t.startswith("/"): return t.split()[0]
    return t

def _handle(text):
    raw = (text or "").strip()
    parsed = _parse_savings(raw)
    if parsed is not None:
        return _savings_plan(parsed)
    cmd = _norm(raw)
    if cmd in ("/start", "/help"): return HELP + "\n\n" + _status()
    if cmd == "/status": return _status()
    if cmd == "/scan": return _quick_scan()
    if cmd == "/fast": return _fast_scan()
    if cmd == "/pump": return _pump_scan()
    if cmd == "/moon": return _moon_scan()
    if cmd == "/patterns": return _patterns_scan()
    if cmd == "/paper": return _paper_report()
    if cmd == "/savings":
        return _savings_plan({
            "amount": 400, "currency": "EUR", "emergency_months": 12, "debt": False,
            "drawdown": 90, "experience": "متوسط", "country": "غير محدد",
        })
    if cmd == "/strict":
        save({"ALERT_REQUIRE_CONFIRM": True, "TREND_REQUIRE_MOMENTUM": True, "TREND_ANTI_REVERSAL": True, "ALERT_ONLY": True})
        apply_overrides(config); return "✅ متشدد.\n" + _status()
    if cmd == "/normal":
        save({"ALERT_REQUIRE_CONFIRM": True, "TREND_REQUIRE_MOMENTUM": True, "TREND_ANTI_REVERSAL": True, "ALERT_ONLY": True})
        apply_overrides(config); return "✅ عادي.\n" + _status()
    cleaned = _clean_query(raw)
    if cleaned and len(cleaned) >= 2 and not cleaned.startswith("/") and re.fullmatch(r"[A-Z0-9][A-Z0-9\- ]{1,20}", cleaned):
        return _coin_report(cleaned)
    if cmd.startswith("/"): return "أمر مش معروف.\n" + HELP
    return None

def process_inbox():
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = str(os.environ.get("TELEGRAM_CHAT_ID") or "")
    if not token or not chat_id: return 0
    apply_overrides(config)
    off = _offset()
    upd = _api(token, "getUpdates", {"timeout": "0", "limit": "50", "offset": str(off)})
    if not upd.get("ok"): return 1
    max_id = off; n = 0
    for item in upd.get("result") or []:
        uid = int(item.get("update_id") or 0); max_id = max(max_id, uid + 1)
        msg = item.get("message") or {}
        chat = str((msg.get("chat") or {}).get("id") or "")
        text = msg.get("text") or ""
        if chat != chat_id: continue
        reply = _handle(text)
        if not reply: continue
        send_text(token, chat_id, reply); n += 1
    if max_id != off: _save_offset(max_id)
    print("done", n); return 0

if __name__ == "__main__":
    sys.exit(process_inbox())

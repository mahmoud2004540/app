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
    "ابعت اسم العملة (BTC / NMR) لتحليل عميق: قمة + مشروع + مستقبل.\n"
    "ورقي = تفاصيل الحساب الورقي.\n"
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
    lines.append("ورقي: شغال")
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
    if getattr(d, "_ema200_ok", True) is False:
        reasons.append("تحت EMA200")
    if getattr(d, "_rsi_ok", True) is False:
        reasons.append("RSI مرتفع")
    if getattr(d, "_confluence_ok", True) is False:
        reasons.append("تأكيدات ناقصة")
    entry, stop, tp, price = _fnum(d, "entry"), _fnum(d, "stop_loss", "stop"), _fnum(d, "take_profit", "target", "tp"), _fnum(d, "price")
    if entry > 0 and stop > 0 and tp > 0:
        risk = abs(entry - stop)
        if risk > 0:
            rr = abs(tp - entry) / risk
            if rr < min_rr:
                reasons.append(f"هدف 1:{rr:.1f}<1:{min_rr:g}")
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
        return "مفيش مرشحين قريبين اتسجلوا."
    return f"أقرب مرشحين ({len(rows)}/{len(ordered)}) وليه اترفضوا:\n" + "\n".join(rows)

def _paper_report():
    apply_overrides(config)
    path = os.path.join("journal", "paper_account.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return "📄 الحساب الورقي لسه فاضي. التداول الحقيقي مقفول."
    equity = float(data.get("equity") or 0)
    start = float(data.get("starting_equity") or equity or 1)
    ret = (equity / start - 1.0) * 100.0 if start else 0.0
    positions = data.get("positions") or []
    closed = data.get("closed") or []
    wins = sum(1 for c in closed if float(c.get("pnl") or 0) > 0)
    n = len(closed)
    wr = (wins / n * 100.0) if n else 0.0
    lines = [
        "📄 الحساب الورقي (مش فلوس حقيقية)",
        f"الرصيد: ${equity:.2f} | العائد: {ret:+.2f}%",
        f"مفتوحة: {len(positions)} | مغلقة: {n} | نجاح: {wr:.1f}%",
        "التداول الحقيقي: مقفول",
    ]
    if positions:
        lines.append("📌 مفتوحة:")
        for p in positions[:8]:
            lines.append(f"  {p.get('symbol')} {p.get('direction')} دخول {p.get('entry')}")
    if closed:
        lines.append("🧼 آخر مغلقة:")
        for c in closed[-5:][::-1]:
            pnl = float(c.get("pnl") or 0)
            lines.append(f"  {c.get('symbol')} PnL {pnl:+.2f} ({c.get('reason')})")
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
        return f"NO TRADE — مفيش صفقة عدت البوابة.\nالسوق: {state} | مرشحين: {len(cands or [])}\n\n" + rejects
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
            return "NO TRADE — مفيش صفقة سريعة.\n\n" + _format_rejects(all_c, [], limit=8)
        return "NO TRADE — مفيش مرشحين سريعين."
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
            return "NO TRADE — مفيش اندفاع.\n\n" + _format_rejects(all_c, [], limit=8)
        return "NO TRADE — مفيش مرشحين اندفاع."
    except Exception as exc:
        return f"⚠️ {exc}"

def _moon_scan():
    return _pump_scan()

def _clean_query(text):
    t = (text or "").strip()
    t = re.sub(r"^(?:تحليل|العملة|عملة|coin|analyze|check)\s*[:\-]?\s*", "", t, flags=re.I)
    t = re.sub(r"[^A-Z0-9\- ]", "", t.strip().upper())
    return t.strip()[:40]

def _coin_report(query):
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
    except Exception as e:
        return f"فشل جلب البيانات: {e}"

    md = full.get("market_data") or {}
    cd = full.get("community_data") or {}
    dd = full.get("developer_data") or {}
    links = full.get("links") or {}

    def usd(key):
        v = md.get(key) or {}
        return float(v.get("usd") or 0) if isinstance(v, dict) else float(v or 0)

    def pct(key):
        v = md.get(key)
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    name = full.get("name") or cid
    sym = str(full.get("symbol") or "").upper()
    price, ath, atl = usd("current_price"), usd("ath"), usd("atl")
    rank = full.get("market_cap_rank") or 9999
    mcap = usd("market_cap")
    chg_24, chg_7, chg_30, chg_1y = pct("price_change_percentage_24h"), pct("price_change_percentage_7d"), pct("price_change_percentage_30d"), pct("price_change_percentage_1y")
    ath_chg = pct("ath_change_percentage")
    need = (ath / price) if price and ath and price > 0 else None
    desc = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", ((full.get("description") or {}).get("en") or "").strip())).strip()
    if len(desc) > 300:
        desc = desc[:297].rsplit(" ", 1)[0] + "..."
    cats = [c for c in (full.get("categories") or []) if c][:5]
    homepage = next((h for h in (links.get("homepage") or []) if h), "")
    twitter = links.get("twitter_screen_name") or ""
    github = next((g for g in ((links.get("repos_url") or {}).get("github") or []) if g), "")
    stars, commits, forks = dd.get("stars"), dd.get("commit_count_4_weeks"), dd.get("forks")
    sentiment = full.get("sentiment_votes_up_percentage")
    tw_f, reddit, watch = cd.get("twitter_followers"), cd.get("reddit_subscribers"), full.get("watchlist_portfolio_users")

    lines = [
        f"🔍 تحليل عميق: {name} ({sym})",
        f"السعر: ${price}",
        f"ATH: ${ath} | من القمة: {ath_chg if ath_chg is not None else '—'}%",
        f"ATL: ${atl} | الترتيب: #{rank if rank < 9999 else '—'} | السوق: ${mcap:,.0f}" if mcap else f"ATL: ${atl} | الترتيب: #{rank if rank < 9999 else '—'}",
        f"24س {chg_24}% | 7أ {chg_7}% | 30أ {chg_30}% | سنة {chg_1y}%",
        "",
        "📈 الرجوع للقمة التاريخية؟",
    ]
    if need and need <= 1.05:
        lines.append("   قريبة من/عند القمة — مش منطقة رجوع من قاع.")
    elif need:
        lines.append(f"   محتاج صعود ~×{need:.1f} من السعر الحالي.")

    yes, no = [], []
    if rank <= 30:
        yes.append("ضمن الكبار: سيولة أعلى")
    if isinstance(commits, (int, float)) and commits and commits >= 10:
        yes.append(f"تطوير نشط ({int(commits)} commits / 4 أسابيع)")
    if homepage:
        yes.append("موقع رسمي")
    if github:
        yes.append("مستودع كود معلن")
    if chg_1y is not None and chg_1y > 0:
        yes.append(f"أداء سنة موجب ({chg_1y:+.0f}%)")
    if sentiment is not None and float(sentiment) >= 60:
        yes.append(f"تصويت إيجابي {float(sentiment):.0f}%")
    if need and need < 3:
        yes.append("البعد عن القمة محدود (<×3)")
    if need and need >= 10:
        no.append(f"بعيدة جدًا (×{need:.0f}) — نادر معظم العملات")
    if rank > 100:
        no.append("ترتيب متأخر: منافسة عالية")
    if rank > 200:
        no.append("صغيرة جدًا: سيولة ضعيفة")
    if isinstance(commits, (int, float)) and commits == 0 and github:
        no.append("تطوير راكد (0 commits)")
    if not github and not homepage:
        no.append("مفيش حضور واضح (موقع/كود)")
    if chg_1y is not None and chg_1y < -50:
        no.append(f"أداء سنة ضعيف ({chg_1y:+.0f}%)")
    if not yes:
        yes.append("مفيش إشارات قوية من البيانات")
    if not no:
        no.append("مفيش عائق حاسم — برضه مش ضمان")
    lines.append("   ليه ممكن:")
    for x in yes[:5]:
        lines.append(f"     ✓ {x}")
    lines.append("   ليه صعب / لأ:")
    for x in no[:5]:
        lines.append(f"     ✗ {x}")
    score = 0
    if rank <= 20: score += 2
    elif rank <= 50: score += 1
    if isinstance(commits, (int, float)) and commits and commits >= 5: score += 1
    if need and need < 5: score += 1
    if need and need >= 20: score -= 2
    if rank > 200: score -= 2
    if isinstance(commits, (int, float)) and commits == 0 and github: score -= 1
    if score >= 3:
        lines.append("   الحكم: احتمال متوسط للرجوع الجزئي/الكامل — مش مضمون.")
    elif score >= 1:
        lines.append("   الحكم: احتمال ضعيف-متوسط — محتاج وقت وسوق قوي.")
    else:
        lines.append("   الحكم: احتمال ضعيف تاريخيًا لنفس القمة.")

    lines += ["", "🏗 دراسة المشروع:"]
    if desc:
        lines.append(f"   وصف: {desc}")
    if cats:
        lines.append("   تصنيف: " + " | ".join(cats))
    if homepage:
        lines.append(f"   موقع: {homepage}")
    if twitter:
        lines.append(f"   تويتر: @{twitter}")
    if github:
        lines.append(f"   GitHub: {github}")
    bits = []
    if tw_f: bits.append(f"تويتر {int(tw_f):,}")
    if reddit: bits.append(f"ريديت {int(reddit):,}")
    if watch: bits.append(f"متابعة {int(watch):,}")
    if bits:
        lines.append("   مجتمع: " + " | ".join(bits))
    if stars is not None or commits is not None:
        lines.append(f"   تطوير: نجوم {stars if stars is not None else '—'} | forks {forks if forks is not None else '—'} | commits 4أ {commits if commits is not None else '—'}")
    if sentiment is not None:
        lines.append(f"   مزاج المجتمع: {float(sentiment):.0f}% إيجابي")
    if rank <= 20 and (isinstance(commits, (int, float)) and commits and commits > 0 or not github):
        lines.append("   مستقبل المشروع: كبير/نشط نسبيًا — مخاطرة سوق عالية.")
    elif rank <= 100 and isinstance(commits, (int, float)) and commits and commits > 0 and homepage:
        lines.append("   مستقبل المشروع: إشارات حياة — مش ضمان بقاء.")
    elif (isinstance(commits, (int, float)) and commits == 0 and github) or (rank > 200 and not homepage):
        lines.append("   مستقبل المشروع: ضعيف ظاهر (ركود/صغر).")
    else:
        lines.append("   مستقبل المشروع: غير واضح — مفيش ضمان استمرار.")
    lines.append("   أخبار: راجع الموقع/تويتر بنفسك قبل الدخول.")

    lines += ["", "💎 زي البيتكوين دلوقتي؟"]
    if sym == "BTC":
        lines.append("   دي البيتكوين نفسها.")
    else:
        lines.append("   لا. البيتكوين له شبكة وأمان وسيولة واعتماد مؤسسي مختلف.")
        lines.append("   معظم العملات ما بتكررش نفس المسار حتى لو المشروع كويس.")
        if need and need >= 10:
            lines.append(f"   الرجوع للقمة فقط محتاج ~×{need:.0f} — مش «يبقى زي BTC».")
        lines.append("   أقصى ما نقدر: مشروع حي أو ضعيف نسبيًا — مش نسخة بيتكوين.")
    lines += ["", "⚠️ مش نصيحة مالية ولا ضمان قمة أو مستقبل. التداول الحقيقي مقفول."]
    return "\n".join(lines)

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

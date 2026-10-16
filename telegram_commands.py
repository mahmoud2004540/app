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
        ["الحالة", "تشديد", "عادي"],
    ],
    "resize_keyboard": True,
    "persistent": True,
}, ensure_ascii=False)
HELP = (
    "ابعت اسم العملة (BTC / NMR) لتحليل عميق.\n"
    "خطة ادخار = ادخار شهري محافظ 5 سنين+.\n"
    "ورقي = الحساب الورقي. التداول الحقيقي مقفول.\n"
    "للخطة ابعت بهذا الشكل:\n"
    "ادخار مبلغ=400 عملة=EUR طوارئ=12 ديون=لا نزول=50 خبرة=متوسط بلد=مصر"
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
    lines.append("خطة ادخار: متاحة من الزر")
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
    chg_24 = pct("price_change_percentage_24h")
    chg_7 = pct("price_change_percentage_7d")
    chg_30 = pct("price_change_percentage_30d")
    chg_1y = pct("price_change_percentage_1y")
    ath_chg = pct("ath_change_percentage")
    need = (ath / price) if price and ath and price > 0 else None
    desc = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", ((full.get("description") or {}).get("en") or "").strip())).strip()
    if len(desc) > 280:
        desc = desc[:277].rsplit(" ", 1)[0] + "..."
    cats = [c for c in (full.get("categories") or []) if c][:5]
    homepage = next((h for h in (links.get("homepage") or []) if h), "")
    twitter = links.get("twitter_screen_name") or ""
    github = next((g for g in ((links.get("repos_url") or {}).get("github") or []) if g), "")
    stars, commits, forks = dd.get("stars"), dd.get("commit_count_4_weeks"), dd.get("forks")
    sentiment = full.get("sentiment_votes_up_percentage")

    lines = [
        f"🔍 تحليل عميق: {name} ({sym})",
        f"السعر: ${price}",
        f"ATH: ${ath} | من القمة: {ath_chg if ath_chg is not None else '—'}%",
        f"الترتيب: #{rank if rank < 9999 else '—'} | السوق: ${mcap:,.0f}" if mcap else f"الترتيب: #{rank if rank < 9999 else '—'}",
        f"24س {chg_24}% | 7أ {chg_7}% | سنة {chg_1y}%",
        "",
        "📈 الرجوع للقمة؟",
    ]
    if need and need <= 1.05:
        lines.append("   قريبة من القمة.")
    elif need:
        lines.append(f"   محتاج ~×{need:.1f}")
    yes, no = [], []
    if rank <= 30:
        yes.append("ضمن الكبار")
    if isinstance(commits, (int, float)) and commits and commits >= 10:
        yes.append(f"تطوير نشط ({int(commits)} commits)")
    if homepage:
        yes.append("موقع رسمي")
    if need and need >= 10:
        no.append(f"بعيدة ×{need:.0f}")
    if rank > 200:
        no.append("صغيرة / سيولة ضعيفة")
    if not yes:
        yes.append("بيانات محدودة")
    if not no:
        no.append("مفيش عائق حاسم — مش ضمان")
    lines.append("   ليه ممكن: " + " | ".join(yes[:4]))
    lines.append("   ليه صعب: " + " | ".join(no[:4]))
    lines += ["", "🏗 المشروع:"]
    if desc:
        lines.append(f"   {desc}")
    if cats:
        lines.append("   " + " | ".join(cats))
    if github:
        lines.append(f"   GitHub: {github}")
    lines += ["", "💎 زي BTC؟ " + ("نعم." if sym == "BTC" else "لا — معظم العملات ما بتكررش نفس المسار.")]
    lines.append("⚠️ مش نصيحة مالية. التداول الحقيقي مقفول.")
    return "\n".join(lines)

def _savings_help():
    return (
        "💰 خطة ادخار كريبتو (محافظ · 5 سنين+)\n\n"
        "ابعت سطر واحد:\n"
        "ادخار مبلغ=400 عملة=EUR طوارئ=12 ديون=لا نزول=50 خبرة=متوسط بلد=المانيا\n\n"
        "• مبلغ = الادخار الشهري\n"
        "• طوارئ = كام شهر مصاريف مغطاة نقدًا\n"
        "• ديون = نعم أو لا\n"
        "• نزول = أقصى هبوط % تتحمله\n\n"
        "مثال جاهز:\n"
        "ادخار مبلغ=400 عملة=EUR طوارئ=12 ديون=لا نزول=90 خبرة=متوسط بلد=غير_محدد\n\n"
        "⚠️ مش توصية شراء/بيع. مش هنفترض إن الأسعار هتزيد."
    )

def _parse_savings(text):
    t = (text or "").strip()
    if not re.match(r"^(?:ادخار|/save|/plan)", t, flags=re.I):
        return None
    t = re.sub(r"^(?:ادخار|/save|/plan)\s*", "", t, flags=re.I)
    data = {
        "amount": None,
        "currency": "EUR",
        "emergency_months": None,
        "debt": None,
        "drawdown": 50.0,
        "experience": "متوسط",
        "country": "غير_محدد",
    }
    pairs = re.findall(
        r"(مبلغ|amount|عملة|currency|طوارئ|emergency|ديون|debt|نزول|drawdown|خبرة|experience|بلد|country)\s*[=:]\s*([^\s=]+)",
        t,
        flags=re.I,
    )
    key_map = {
        "مبلغ": "amount", "amount": "amount",
        "عملة": "currency", "currency": "currency",
        "طوارئ": "emergency_months", "emergency": "emergency_months",
        "ديون": "debt", "debt": "debt",
        "نزول": "drawdown", "drawdown": "drawdown",
        "خبرة": "experience", "experience": "experience",
        "بلد": "country", "country": "country",
    }
    for k, v in pairs:
        kk = k.lower() if k.isascii() else k
        field = key_map.get(kk) or key_map.get(k)
        if not field:
            continue
        if field == "amount":
            try:
                data["amount"] = float(v.replace(",", "."))
            except ValueError:
                pass
        elif field == "currency":
            data["currency"] = v.upper()[:8]
        elif field == "emergency_months":
            try:
                data["emergency_months"] = float(v.replace(",", "."))
            except ValueError:
                pass
        elif field == "debt":
            data["debt"] = v.strip().lower() in ("نعم", "yes", "y", "true", "1")
        elif field == "drawdown":
            try:
                data["drawdown"] = float(v.replace("%", "").replace(",", "."))
            except ValueError:
                pass
        elif field == "experience":
            data["experience"] = v
        elif field == "country":
            data["country"] = v.replace("_", " ")
    if data["amount"] is None or data["emergency_months"] is None or data["debt"] is None:
        return {"_incomplete": True, "raw": data}
    return data

def _tax_note(country):
    c = (country or "").lower().replace(" ", "")
    notes = {
        "المانيا": "ألمانيا: غالبًا إعفاء بعد حيازة سنة — راجع Finanzamt.",
        "germany": "ألمانيا: غالبًا إعفاء بعد حيازة سنة — راجع Finanzamt.",
        "deutschland": "ألمانيا: غالبًا إعفاء بعد سنة — راجع Finanzamt.",
        "فرنسا": "فرنسا: ضريبة PFU تقريبًا على المكاسب — راجع الضرائب.",
        "france": "فرنسا: ضريبة PFU — راجع الضرائب.",
        "اسبانيا": "إسبانيا: شرائح على مكاسب الادخار — راجع Agencia Tributaria.",
        "spain": "إسبانيا: شرائح — راجع Agencia Tributaria.",
        "هولندا": "هولندا: Box 3 — راجع Belastingdienst.",
        "netherlands": "هولندا: Box 3 — راجع Belastingdienst.",
        "مصر": "مصر: راجع مصلحة الضرائب / محاسب.",
        "egypt": "مصر: راجع مصلحة الضرائب / محاسب.",
    }
    for k, v in notes.items():
        if k in c:
            return v
    return "الضرايب تعتمد على بلدك — راجع مصلحة الضرائب أو محاسب."

def _savings_plan(data):
    if data.get("_incomplete"):
        return (
            "ناقص بيانات. ابعت كامل:\n"
            "ادخار مبلغ=400 عملة=EUR طوارئ=12 ديون=لا نزول=50 خبرة=متوسط بلد=المانيا\n\n"
            + _savings_help()
        )
    amount = float(data["amount"])
    cur = data["currency"]
    em = float(data["emergency_months"])
    debt = bool(data["debt"])
    dd = float(data["drawdown"])
    exp = str(data["experience"])
    country = str(data["country"])
    lines = [
        "💰 خطة ادخار كريبتو (محافظ)",
        f"مبلغ: {amount:g} {cur}/شهر | طوارئ: {em:g} شهر | ديون: {'نعم' if debt else 'لا'}",
        f"نزول مقبول: {dd:g}% | خبرة: {exp} | بلد: {country}",
        "",
        "① الفحص الأول",
    ]
    if debt:
        lines += [
            "⛔ ديون غالية → أصلحها أولًا. متكملش ادخار كريبتو دلوقتي.",
            "",
            "⚠️ مش نصيحة مالية. التداول الحقيقي مقفول.",
        ]
        return "\n".join(lines)
    if em < 3:
        lines += [
            f"⛔ طوارئ {em:g} شهر فقط (المطلوب 3–6).",
            f"حط الـ {amount:g} {cur} في نقد/حساب سهل السحب لحد 3 شهور.",
            "بعدها ابعت نفس الأمر تاني.",
            "",
            "⚠️ مش نصيحة مالية.",
        ]
        return "\n".join(lines)
    lines.append(f"✅ طوارئ {em:g} شهر وبدون ديون غالية → تقدر تبدأ بحذر.")
    if dd <= 30:
        btc_pct, eth_pct, sol_pct = 70, 30, 0
        risk_note = "تحمل منخفض → BTC+ETH فقط."
    elif dd <= 50:
        btc_pct, eth_pct, sol_pct = 60, 30, 10
        risk_note = "تحمل متوسط → BTC+ETH + SOL محدود."
    else:
        btc_pct, eth_pct, sol_pct = 55, 30, 15
        risk_note = "تحمل عالي برضه صفر عملات صغيرة (ادخار محافظ)."
    btc_amt = amount * btc_pct / 100
    eth_amt = amount * eth_pct / 100
    sol_amt = amount * sol_pct / 100
    total_5y = amount * 60
    lines += [
        "",
        "② التوزيع (إطار تعليمي — مش توصية شراء)",
        risk_note,
        f"• BTC  {btc_pct}% → {btc_amt:g} {cur}",
        f"• ETH  {eth_pct}% → {eth_amt:g} {cur}",
    ]
    if sol_pct > 0:
        lines.append(f"• SOL  {sol_pct}% → {sol_amt:g} {cur}")
    lines.append("• مخاطرة عالية: 0%")
    lines += [
        "",
        "③ التنفيذ",
        "• يوم ثابت كل شهر",
        "• شراء سوقي أو متكرر",
        "• بورصة مرخّصة في بلدك — قارن الرسوم",
        "• عند كبر المبلغ: جزء في محفظة شخصية",
        "• 2FA + متدخلش على روابط مشبوهة",
        "",
        "④ محاكاة 5 سنين (افتراضات مش توقعات)",
        f"إجمالي الدفع: {total_5y:g} {cur}",
        f"• هبوط: ~{total_5y*0.4:g}–{total_5y*0.7:g} {cur}",
        f"• ثبات: ~{total_5y*0.85:g}–{total_5y*1.15:g} {cur}",
        f"• صعود: ممكن {total_5y*1.4:g}+ {cur} (مش مضمون)",
        "",
        "⑤ القواعد",
        "• مراجعة: 1–2 مرة/سنة",
        "• وقف: فقدان الدخل أو احتياج الطوارئ أو ديون غالية",
        "• نزول 50%: متبيعش من الذعر إن الأفق طويل",
        f"• ضرايب: {_tax_note(country)}",
        "",
        "⑥ علامات خطر",
        "• أرباح مضمونة / نسبة شهرية ثابتة",
        "• ضغط «اشترِ دلوقتي»",
        "• طلب الكلمات السرية أو تحويل غريب",
        "",
        "⚠️ مش نصيحة مالية. مش هنفترض إن الأسعار هتزيد.",
        "التداول الحقيقي في البوت مقفول.",
    ]
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
        "ورقي": "/paper", "paper": "/paper",
        "خطة ادخار": "/savings", "ادخار": "/savings", "savings": "/savings", "خطة": "/savings",
        "start": "/start", "help": "/help",
    }
    if t in aliases:
        return aliases[t]
    if t.startswith("/"):
        return t.split()[0]
    return t

def _handle(text):
    raw = (text or "").strip()
    parsed = _parse_savings(raw)
    if parsed is not None:
        return _savings_plan(parsed)
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
    if cmd == "/savings":
        return _savings_help()
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

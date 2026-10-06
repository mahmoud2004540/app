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
        ["الحالة", "تشديد", "عادي"],
    ],
    "resize_keyboard": True,
    "persistent": True,
}, ensure_ascii=False)
HELP = (
    "ابعت اسم العملة (مثال: BTC أو NMR) لتحليل السعر + المشروع + الأخبار المتاحة.\n"
    "فحص الآن = دقة | صفقات سريعة = فريم قصير\n"
    "الصفقة مش بتتبعت غير لو درجة 80+ وهدف 1:2.\n"
    "مفيش عملة هتبقى زي البيتكوين بضمان."
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
    lines.append("بوابة: 80+ / 1:2 / من غير مطاردة")
    lines.append("ابعت اسم عملة: سعر + مشروع + مستقبل")
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
    tp = _num(deal, "take_profit", "target", "tp2", "tp")
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
        f"NO TRADE — مفيش صفقة.\n{title}\n"
        f"الشرط: 80+ و 1:2 والسعر عند الدخول.\n"
        f"السوق {state} | مرفوضين: {len(cands or [])}"
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
            return "NO TRADE — مفيش بداية اندفاع عد البوابة."
        return "🚀 بداية اندفاع\nقياس ~27%.\n\n" + format_digest(picks, title="عد البوابة")
    except Exception as exc:
        return f"⚠️ {exc}"

def _moon_scan():
    apply_overrides(config)
    config.CRYPTO_UNIVERSE = "all"
    try:
        from deals_bot.formatter import format_digest
        picks = _early_picks(["1d", "6h"], 2)
        if not picks:
            return "NO TRADE — مفيش مرشح بعيد. مش 100x."
        return "🚀 مرشح بعيد\nمش 100x.\n\n" + format_digest(picks, title="عند الدخول")
    except Exception as exc:
        return f"⚠️ {exc}"

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
            return "NO TRADE — مفيش صفقة سريعة عد البوابة."
        return "⚡ صفقات سريعة\n\n" + format_digest(picks, title="أول الحركة")
    except Exception as exc:
        return f"⚠️ {exc}"

def _http_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _clean_query(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"^(?:تحليل|العملة|عملة|coin|analyze|check)\s*[:\-]?\s*", "", t, flags=re.I)
    t = t.strip().upper()
    t = re.sub(r"[^A-Z0-9\- ]", "", t)
    return t.strip()[:40]

def _resolve_coin(query: str):
    q = _clean_query(query)
    if not q or len(q) < 2:
        return None
    try:
        data = _http_json(f"https://api.coingecko.com/api/v3/search?query={urllib.parse.quote(q)}")
    except Exception:
        return None
    coins = data.get("coins") or []
    if not coins:
        return None
    q_up = q.upper().replace(" ", "")
    exact = [c for c in coins if str(c.get("symbol", "")).upper() == q_up]
    pick = exact[0] if exact else coins[0]
    return {"id": pick.get("id"), "symbol": str(pick.get("symbol", "")).upper(), "name": pick.get("name") or ""}

def _market_snapshot(coin_id: str):
    data = _http_json(
        f"https://api.coingecko.com/api/v3/coins/{coin_id}"
        f"?localization=false&tickers=false&community_data=true&developer_data=true"
    )
    md = data.get("market_data") or {}
    cd = data.get("community_data") or {}
    dd = data.get("developer_data") or {}
    links = data.get("links") or {}
    def usd(key):
        v = md.get(key) or {}
        return float(v.get("usd") or 0) if isinstance(v, dict) else float(v or 0)
    def pct(key):
        v = md.get(key)
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None
    desc = ((data.get("description") or {}).get("en") or "").strip()
    desc = re.sub(r"<[^>]+>", " ", desc)
    desc = re.sub(r"\s+", " ", desc).strip()
    if len(desc) > 280:
        desc = desc[:277].rsplit(" ", 1)[0] + "..."
    cats = [c for c in (data.get("categories") or []) if c][:5]
    homepage = next((h for h in (links.get("homepage") or []) if h), "")
    twitter = links.get("twitter_screen_name") or ""
    repos = (links.get("repos_url") or {}).get("github") or []
    github = next((g for g in repos if g), "")
    return {
        "name": data.get("name") or coin_id,
        "symbol": str(data.get("symbol") or "").upper(),
        "price": usd("current_price"),
        "ath": usd("ath"),
        "ath_chg": pct("ath_change_percentage"),
        "atl": usd("atl"),
        "rank": data.get("market_cap_rank"),
        "mcap": usd("market_cap"),
        "chg_24h": pct("price_change_percentage_24h"),
        "chg_7d": pct("price_change_percentage_7d"),
        "chg_30d": pct("price_change_percentage_30d"),
        "chg_1y": pct("price_change_percentage_1y"),
        "desc": desc,
        "cats": cats,
        "homepage": homepage,
        "twitter": twitter,
        "github": github,
        "sentiment_up": data.get("sentiment_votes_up_percentage"),
        "watchlist": data.get("watchlist_portfolio_users"),
        "twitter_followers": cd.get("twitter_followers"),
        "reddit_subs": cd.get("reddit_subscribers"),
        "telegram_users": cd.get("telegram_channel_user_count"),
        "gh_stars": dd.get("stars"),
        "gh_forks": dd.get("forks"),
        "gh_commits_4w": dd.get("commit_count_4_weeks"),
    }

def _project_future_note(snap: dict) -> list:
    lines = []
    rank = snap.get("rank") or 9999
    commits = snap.get("gh_commits_4w")
    stars = snap.get("gh_stars")
    sentiment = snap.get("sentiment_up")
    cats = snap.get("cats") or []
    has_site = bool(snap.get("homepage"))
    has_gh = bool(snap.get("github"))
    active_dev = isinstance(commits, (int, float)) and commits and commits > 0
    dead_dev = isinstance(commits, (int, float)) and commits == 0 and has_gh
    if snap.get("desc"):
        lines.append(f"   وصف: {snap['desc']}")
    if cats:
        lines.append("   تصنيف: " + " | ".join(cats[:4]))
    if has_site:
        lines.append(f"   موقع: {snap['homepage']}")
    if snap.get("twitter"):
        lines.append(f"   تويتر: @{snap['twitter']}")
    if has_gh:
        lines.append(f"   GitHub: {snap['github']}")
    bits = []
    if snap.get("twitter_followers"):
        bits.append(f"تويتر {int(snap['twitter_followers']):,}")
    if snap.get("reddit_subs"):
        bits.append(f"ريديت {int(snap['reddit_subs']):,}")
    if snap.get("telegram_users"):
        bits.append(f"تليجرام {int(snap['telegram_users']):,}")
    if snap.get("watchlist"):
        bits.append(f"متابعة {int(snap['watchlist']):,}")
    if bits:
        lines.append("   مجتمع: " + " | ".join(bits))
    if stars is not None or commits is not None:
        lines.append(
            f"   تطوير: نجوم {stars if stars is not None else '—'} | "
            f"commits 4 أسابيع {commits if commits is not None else '—'}"
        )
    if sentiment is not None:
        lines.append(f"   تصويت إيجابي (CoinGecko): {float(sentiment):.0f}%")
    if rank <= 20 and (active_dev or not has_gh):
        lines.append("   مستقبل: مشروع كبير/نشط نسبيًا — لسه فيه مخاطرة سوق.")
    elif rank <= 100 and active_dev and has_site:
        lines.append("   مستقبل: فيه إشارات حياة (تطوير/موقع) — مش ضمان نجاح.")
    elif dead_dev or (rank > 200 and not active_dev and not has_site):
        lines.append("   مستقبل ضعيف: تطوير راكد أو مشروع صغير بلا حضور واضح.")
    else:
        lines.append("   مستقبل غير واضح من البيانات — مفيش ضمان استمرار.")
    lines.append("   أخبار: مفيش مصدر أخبار حي مجاني موثوق دلوقتي. راجع الموقع/تويتر قبل الدخول.")
    return lines

def _pair_symbol(sym: str) -> str:
    s = (sym or "").upper().replace("USDT", "").replace("USD", "").replace("-", "")
    return f"{s}-USD"

def _tf_check(pair: str, timeframe: str, mode: str):
    try:
        from deals_bot.providers import fetch_best
        from deals_bot.analyzer import detect_trend_pullback, detect_early_pump, detect_accumulation
        series = fetch_best(pair, "crypto", timeframe, limit=220)
        if not series or len(series) < 40:
            return None
        if mode == "fast":
            ep = detect_early_pump(series)
            if ep and float(ep.get("score") or 0) >= 70:
                return {"ok": True, "kind": "أول كسر", "score": float(ep.get("score") or 0), "entry": ep.get("price"), "stop": ep.get("stop"), "tp": ep.get("target")}
            acc = detect_accumulation(series)
            if acc and float(acc.get("score") or 0) >= 70:
                return {"ok": True, "kind": "تجميع", "score": float(acc.get("score") or 0), "entry": acc.get("price"), "stop": acc.get("stop"), "tp": acc.get("target")}
            return {"ok": False, "kind": "لا", "score": 0}
        tp = detect_trend_pullback(series, rr=2.0, direction="long")
        if tp and float(tp.get("score") or tp.get("confidence") or 0) >= 80:
            return {"ok": True, "kind": "اتجاه", "score": float(tp.get("score") or tp.get("confidence") or 0), "entry": tp.get("entry") or tp.get("price"), "stop": tp.get("stop_loss") or tp.get("stop"), "tp": tp.get("take_profit") or tp.get("target")}
        return {"ok": False, "kind": "لا", "score": float((tp or {}).get("score") or (tp or {}).get("confidence") or 0)}
    except Exception as exc:
        return {"ok": False, "kind": "خطأ", "score": 0, "err": str(exc)[:80]}

def _fmt_money(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "—"
    if x >= 1000:
        return f"${x:,.2f}"
    if x >= 1:
        return f"${x:.4f}"
    return f"${x:.8f}".rstrip("0").rstrip(".")

def _fmt_pct(x):
    if x is None:
        return "—"
    try:
        return f"{float(x):+.1f}%"
    except (TypeError, ValueError):
        return "—"

def _coin_report(query: str) -> str:
    apply_overrides(config)
    _enable_30m()
    resolved = _resolve_coin(query)
    if not resolved or not resolved.get("id"):
        return f"معرفتش العملة: {query}\nابعت الرمز (BTC / ETH / NMR)."
    try:
        snap = _market_snapshot(resolved["id"])
    except Exception as e:
        return f"فشلت جيب البيانات لـ {resolved.get('symbol')}: {e}"
    pair = _pair_symbol(snap["symbol"] or resolved["symbol"])
    price = snap["price"]
    ath = snap["ath"]
    drop = (price / ath - 1.0) * 100.0 if price and ath and ath > 0 else None
    need_x = (ath / price) if price and ath and price > 0 else None
    fast = _tf_check(pair, "1h", "fast") or _tf_check(pair, "15m", "fast")
    swing = _tf_check(pair, "6h", "swing") or _tf_check(pair, "1d", "swing")
    lines = [
        f"🔍 {snap['name']} ({snap['symbol']})",
        f"السعر: {_fmt_money(price)}",
        f"ATH: {_fmt_money(ath)} ({_fmt_pct(drop if drop is not None else snap.get('ath_chg'))})",
        f"ATL: {_fmt_money(snap.get('atl'))}",
        f"الترتيب: #{snap.get('rank') or '—'} | السوق: {_fmt_money(snap.get('mcap'))}",
        f"24س {_fmt_pct(snap.get('chg_24h'))} | 7أ {_fmt_pct(snap.get('chg_7d'))} | 30أ {_fmt_pct(snap.get('chg_30d'))} | سنة {_fmt_pct(snap.get('chg_1y'))}",
        "",
    ]
    if fast and fast.get("ok"):
        lines.append(f"⚡ سريع: ممكن ({fast.get('kind')}) {fast.get('score', 0):.0f}")
        if fast.get("entry"):
            lines.append(f"   دخول {_fmt_money(fast['entry'])} | وقف {_fmt_money(fast.get('stop'))} | هدف {_fmt_money(fast.get('tp'))}")
    else:
        lines.append("⚡ سريع: NO TRADE")
    if swing and swing.get("ok"):
        lines.append(f"📈 متوسط: ممكن ({swing.get('kind')}) {swing.get('score', 0):.0f}")
        if swing.get("entry"):
            lines.append(f"   دخول {_fmt_money(swing['entry'])} | وقف {_fmt_money(swing.get('stop'))} | هدف {_fmt_money(swing.get('tp'))}")
    else:
        lines.append(f"📈 متوسط: NO TRADE (درجة {(swing or {}).get('score') or 0:.0f})")
    lines.append("")
    lines.append("🏗 المشروع والمستقبل:")
    lines.extend(_project_future_note(snap))
    lines.append("")
    lines.append("🌍 استثمار طويل:")
    rank = snap.get("rank") or 9999
    if need_x and need_x > 1:
        lines.append(f"   للقمة التاريخية محتاج ~×{need_x:.1f}")
    elif need_x and need_x <= 1.05:
        lines.append("   قريبة من القمة — مش شراء رخيص.")
    if rank <= 10:
        lines.append("   كبيرة: سيولة أقوى، الصعود مش مضمون.")
    elif rank <= 50:
        lines.append("   متوسطة: حجم صغير فقط + مخاطرة عالية.")
    elif rank <= 200:
        lines.append("   صغيرة: معظم العملات ما بترجع للقمة.")
    else:
        lines.append("   صغيرة جدًا: مخاطرة انهيار/ركود مرتفعة.")
    lines.append("")
    lines.append("💎 زي البيتكوين؟")
    if snap["symbol"] == "BTC":
        lines.append("   دي البيتكوين.")
    else:
        lines.append("   لا. سيولة/شبكة مختلفة. معظم العملات ما بتوصلش لنفس المسار.")
        if need_x and need_x >= 10:
            lines.append(f"   القمة تحتاج ~×{need_x:.0f} — احتمال ضعيف.")
    lines.append("")
    lines.append("⚠️ مش نصيحة مالية. التداول الحقيقي مقفول.")
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
    if cmd == "/strict":
        save({"ALERT_REQUIRE_CONFIRM": True, "TREND_REQUIRE_MOMENTUM": True, "TREND_ANTI_REVERSAL": True, "ALERT_ONLY": True, "TREND_RR": 2.0, "TREND_MIN_SCORE": 85})
        apply_overrides(config)
        return "✅ البوابة متشددة.\n" + _status()
    if cmd == "/normal":
        save({"ALERT_REQUIRE_CONFIRM": True, "TREND_REQUIRE_MOMENTUM": True, "TREND_ANTI_REVERSAL": True, "ALERT_ONLY": True})
        apply_overrides(config)
        return "✅ التأكيد شغال.\n" + _status()
    cleaned = _clean_query(raw)
    if cleaned and len(cleaned) >= 2 and not cleaned.startswith("/"):
        if re.fullmatch(r"[A-Z0-9][A-Z0-9\- ]{1,20}", cleaned):
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

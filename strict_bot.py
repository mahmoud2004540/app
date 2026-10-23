#!/usr/bin/env python3
"""
المحلّل المتحفّظ: يفحص الأزواج المحدّدة ويرسل على تيليجرام صفقات عالية الاحتمالية فقط.

Conservative analyst runner. Each run:
  1) يقيّم الصفقات المفتوحة في السجل (ربح/خسارة/تعادل) من الشموع الحقيقية.
  2) مرة كل أسبوع: تقرير نسبة النجاح الحقيقية + رفع العتبة لـ85 لو النسبة < 60%.
  3) يفحص كل زوج على آخر شمعة مقفولة بالشروط الثمانية الإلزامية.
  4) يرسل الصفقات اللي درجتها ≥ العتبة، أو «لا توجد فرصة مطابقة للشروط حالياً»
     مرة واحدة لكل شمعة جديدة على الفريم الأساسي (مش كل 15 دقيقة).

التشغيل:
  python strict_bot.py            # يحتاج TELEGRAM_TOKEN و TELEGRAM_CHAT_ID
  python strict_bot.py --dry-run  # يطبع بدون إرسال وبدون تعديل السجل
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import config
from deals_bot import strict, strict_journal
from deals_bot.providers import fetch, fetch_okx


def _symbols():
    env = os.environ.get("STRICT_SYMBOLS")
    if env:
        return [s.strip() for s in env.split(",") if s.strip()]
    return list(config.STRICT_SYMBOLS)


def fetch_frame(symbol: str, market: str, timeframe: str, limit: int = 300):
    """كريبتو من OKX (فريمات أصلية 1H/4H/1D)؛ غيره من Yahoo."""
    if market == "crypto":
        return fetch_okx(symbol, timeframe=timeframe, limit=limit)
    return fetch(symbol, market, "yfinance", timeframe, limit=limit)


NEWS_CACHE = os.path.join(".cache", "news_cache.json")


def load_news(now_ts: float, max_age: float = 3600.0):
    """
    أجندة الأخبار مع كاش ساعة (المصدر يحدّ الطلبات المتكرّرة بـ 429).
    لو الجلب فشل نستخدم الكاش لو عمره أقل من 6 ساعات، وإلا None (= الشرط 7 يرفض).
    """
    cached = None
    try:
        with open(NEWS_CACHE, encoding="utf-8") as f:
            cached = json.load(f)
    except (OSError, json.JSONDecodeError):
        pass
    if cached and now_ts - cached.get("ts", 0) < max_age:
        return cached["events"]
    try:
        events = strict.fetch_news()
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ أجندة الأخبار غير متاحة: {exc}")
        if cached and now_ts - cached.get("ts", 0) < 6 * 3600:
            return cached["events"]
        return None
    os.makedirs(os.path.dirname(NEWS_CACHE), exist_ok=True)
    with open(NEWS_CACHE, "w", encoding="utf-8") as f:
        json.dump({"ts": now_ts, "events": events}, f)
    return events


def _cfg(market: str) -> strict.StrictConfig:
    return strict.StrictConfig(
        min_rr=config.STRICT_MIN_RR,
        max_rr=config.STRICT_MAX_RR,
        adx_min=config.STRICT_ADX_MIN,
        # Yahoo لا يعطي فوليوم/سيولة دولارية موثوقة للفوركس
        min_dollar_vol=0.0 if market == "forex" else config.STRICT_MIN_DOLLAR_VOL,
        block_weekend_crypto=config.STRICT_BLOCK_WEEKEND_CRYPTO,
        news_window_min=config.STRICT_NEWS_WINDOW_MIN,
    )


def scan(market: str, symbols, now: datetime, min_score: int):
    """يرجّع (صفقات مقبولة، سطور سجل الفحص)."""
    tf = config.STRICT_PRIMARY_TF
    news = load_news(now.timestamp())
    picks, log = [], []
    now_ts = now.timestamp()
    for sym in symbols:
        try:
            primary = fetch_frame(sym, market, tf, 300)
            trend = {t: fetch_frame(sym, market, t, 300) for t in config.STRICT_TREND_TFS}
        except Exception as exc:  # noqa: BLE001
            log.append(f"{sym}: تعذّر الجلب ({exc})")
            continue
        setup, why = strict.best_setup(primary, trend, tf, now_ts, news, _cfg(market),
                                       allow_short=config.STRICT_ALLOW_SHORT)
        if not setup:
            log.append(f"{sym}: ❌ " + " | ".join(why))
        elif setup.score < min_score:
            log.append(f"{sym}: ❌ الدرجة {setup.score} < {min_score}")
        elif strict_journal.has_open(sym):
            log.append(f"{sym}: ⏸ فيه صفقة مفتوحة على نفس الزوج")
        else:
            log.append(f"{sym}: ✅ {setup.direction} درجة {setup.score}")
            picks.append(setup)
    return picks, log


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not args.dry_run and (not token or not chat):
        print("❌ يجب ضبط TELEGRAM_TOKEN و TELEGRAM_CHAT_ID.", file=sys.stderr)
        return 2
    from send_digest import send_telegram

    def send(text):
        print("----- رسالة -----\n" + text + "\n-----------------")
        if not args.dry_run:
            send_telegram(token, chat, text)

    market = os.environ.get("STRICT_MARKET", config.STRICT_MARKET)
    now = datetime.now(timezone.utc)
    base = int(config.STRICT_MIN_SCORE)

    if not args.dry_run:
        n = strict_journal.evaluate_open(lambda s, m, t: fetch_frame(s, m, t, 300))
        if n:
            print(f"📒 اتقفلت {n} صفقة في السجل.")
        report = strict_journal.weekly_review(
            now, base=base, raised=int(config.STRICT_RAISED_SCORE),
            min_wr=float(config.STRICT_WEEKLY_MIN_WINRATE))
        if report:
            send(report)

    min_score = strict_journal.current_min_score(base)
    picks, log = scan(market, _symbols(), now, min_score)
    print(f"🔎 فحص {market} {config.STRICT_PRIMARY_TF} (حد الثقة {min_score}):")
    print("\n".join("  " + x for x in log))

    risk = float(config.STRICT_RISK_PER_TRADE)
    equity = float(getattr(config, "ACCOUNT_BALANCE", 1000.0))
    if picks:
        for s in picks:
            if args.dry_run or strict_journal.record(s, opened_ts=s.candle_ts
                                                    + strict.TF_SECONDS[s.timeframe]):
                send(strict.format_setup(s, equity, risk))
        return 0

    # لا صفقة: نبلّغ مرة واحدة لكل شمعة مقفولة جديدة (أو مرة يوميًا / أبدًا)
    mode = getattr(config, "STRICT_NO_TRADE_NOTICE", "bar")
    if mode == "off":
        return 0
    step = strict.TF_SECONDS.get(config.STRICT_PRIMARY_TF, 3600) if mode == "bar" else 86400
    bar = int(now.timestamp() // step)
    state = strict_journal.load_state()
    if args.dry_run:
        print(strict.NO_TRADE)
    elif state.get("last_no_trade_bar") != bar:
        state["last_no_trade_bar"] = bar
        strict_journal.save_state(state)
        send(strict.NO_TRADE)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
بوت تيليجرام: نفس محرّك التحليل لكن يوصلك على تليفونك.

Telegram interface for the deals engine. Uses python-telegram-bot (v20+).

كيف تشغّله / How to run:
  1) أنشئ بوتًا عبر @BotFather في تيليجرام واحصل على التوكن.
  2) صدّر التوكن:  export TELEGRAM_TOKEN="123456:ABC..."
  3) ثبّت المتطلبات:  pip install -r requirements.txt
  4) شغّل:  python telegram_bot.py

الأوامر داخل البوت / Commands:
  /start                نبذة وتعليمات
  /best [market] [tf]   أفضل الصفقات (market: crypto|stocks|forex|all)
  /crypto  /stocks  /forex   اختصارات لكل سوق
  /buy [market]         أفضل صفقات الشراء فقط
"""

from __future__ import annotations

import os

import config
from deals_bot import rank_deals
from deals_bot.formatter import format_deals
from deals_bot.providers import fetch_many

try:
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
    )
except ImportError:  # pragma: no cover - environment dependent
    raise SystemExit(
        "مكتبة python-telegram-bot غير مثبّتة.\n"
        "ثبّتها بـ:  pip install -r requirements.txt"
    )


def _symbols_for(market: str, source: str) -> list[str]:
    if market == "crypto" and source == "binance":
        return config.BINANCE_WATCHLIST
    return config.WATCHLISTS[market]


def _compute(market: str, timeframe: str, direction: str, top: int) -> str:
    source = config.DEFAULT_SOURCE
    markets = ["crypto", "stocks", "forex"] if market == "all" else [market]
    all_deals = []
    for mkt in markets:
        src = source if mkt == "crypto" else "yfinance"
        symbols = _symbols_for(mkt, src)
        series = fetch_many(symbols, mkt, src, timeframe)
        if series:
            all_deals.extend(rank_deals(series, top=top, direction=direction))

    if direction == "buy":
        all_deals.sort(key=lambda d: d.score, reverse=True)
    elif direction == "sell":
        all_deals.sort(key=lambda d: d.score)
    else:
        all_deals.sort(key=lambda d: d.confidence, reverse=True)
    all_deals = all_deals[:top]

    return format_deals(all_deals, title=f"أفضل الصفقات — {market} ({timeframe})")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 أهلًا بك في بوت الصفقات!\n\n"
        "أعطيك أفضل فرص التداول بناءً على تحليل فني آلي.\n\n"
        "الأوامر:\n"
        "• /best crypto 1h — أفضل صفقات الكريبتو على فريم ساعة\n"
        "• /crypto  /stocks  /forex — اختصارات لكل سوق\n"
        "• /best all — أفضل الصفقات عبر كل الأسواق\n"
        "• /buy crypto — صفقات الشراء فقط\n\n"
        "⚠️ ليست نصيحة مالية — للأغراض التعليمية فقط."
    )


def _parse_args(args: list[str]) -> tuple[str, str]:
    market = "crypto"
    timeframe = config.DEFAULT_TIMEFRAME
    valid_markets = {"crypto", "stocks", "forex", "all"}
    valid_tf = {"1m", "5m", "15m", "1h", "1d"}
    for a in args:
        low = a.lower()
        if low in valid_markets:
            market = low
        elif low in valid_tf:
            timeframe = low
    return market, timeframe


async def best(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    market, timeframe = _parse_args(context.args or [])
    await update.message.reply_text(f"⏳ جاري تحليل «{market}» على فريم {timeframe}...")
    text = _compute(market, timeframe, direction="any", top=config.DEFAULT_TOP)
    await update.message.reply_text(text)


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    market, timeframe = _parse_args(context.args or [])
    await update.message.reply_text(f"⏳ جاري البحث عن صفقات شراء في «{market}»...")
    text = _compute(market, timeframe, direction="buy", top=config.DEFAULT_TOP)
    await update.message.reply_text(text)


def _market_handler(market: str):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _, timeframe = _parse_args(context.args or [])
        await update.message.reply_text(f"⏳ جاري تحليل «{market}»...")
        text = _compute(market, timeframe, direction="any", top=config.DEFAULT_TOP)
        await update.message.reply_text(text)

    return handler


def main() -> None:
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise SystemExit(
            "لم يتم ضبط متغيّر البيئة TELEGRAM_TOKEN.\n"
            'صدّره أولًا:  export TELEGRAM_TOKEN="ضع_التوكن_هنا"'
        )

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("best", best))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("crypto", _market_handler("crypto")))
    app.add_handler(CommandHandler("stocks", _market_handler("stocks")))
    app.add_handler(CommandHandler("forex", _market_handler("forex")))

    print("✅ البوت يعمل الآن. اضغط Ctrl+C للإيقاف.")
    app.run_polling()


if __name__ == "__main__":
    main()

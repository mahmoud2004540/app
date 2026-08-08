#!/usr/bin/env python3
"""
يرسل أفضل الصفقات إلى تيليجرام تلقائيًا (يُستخدم مع GitHub Actions المجدولة).

Sends the best trading deals to a Telegram chat. Designed to run as a scheduled
GitHub Actions job — no server, no interactivity. Reads configuration from
environment variables (set them as GitHub repository Secrets):

  TELEGRAM_TOKEN     (مطلوب) توكن البوت من BotFather
  TELEGRAM_CHAT_ID   (مطلوب) معرّف محادثتك (رقم) أو @channelusername
  MARKETS            (اختياري) قائمة مفصولة بفواصل: crypto,stocks,forex  (افتراضي)
  TIMEFRAME          (اختياري) 1m|5m|15m|1h|1d   (افتراضي 1h)
  TOP                (اختياري) عدد الصفقات لكل سوق  (افتراضي 5)
  DIRECTION          (اختياري) any|buy|sell  (افتراضي any)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request

import config
from deals_bot import rank_deals
from deals_bot.formatter import format_digest
from deals_bot.providers import fetch_many

TELEGRAM_MAX = 4000  # حد أمان أقل من 4096 لتفادي رفض الرسالة


def _symbols_for(market: str) -> list[str]:
    return config.WATCHLISTS.get(market, [])


def build_message() -> str:
    markets = [
        m.strip()
        for m in os.environ.get("MARKETS", "crypto,stocks,forex").split(",")
        if m.strip() in ("crypto", "stocks", "forex")
    ] or ["crypto"]
    timeframe = os.environ.get("TIMEFRAME", config.DEFAULT_TIMEFRAME)
    top = int(os.environ.get("TOP", config.DEFAULT_TOP))
    direction = os.environ.get("DIRECTION", "any")

    all_deals = []
    for mkt in markets:
        symbols = _symbols_for(mkt)
        series = fetch_many(symbols, mkt, "yfinance", timeframe)
        if series:
            all_deals.extend(rank_deals(series, top=top, direction=direction))

    if direction == "buy":
        all_deals.sort(key=lambda d: d.score, reverse=True)
    elif direction == "sell":
        all_deals.sort(key=lambda d: d.score)
    else:
        all_deals.sort(key=lambda d: d.confidence, reverse=True)

    title = f"أفضل الصفقات — {', '.join(markets)} ({timeframe})"
    return format_digest(all_deals[: max(top, 5)], title=title)


def send_telegram(token: str, chat_id: str, text: str) -> None:
    """أرسل الرسالة (مع تقسيمها إن تجاوزت حد تيليجرام)."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chunk in _chunks(text, TELEGRAM_MAX):
        data = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": chunk, "disable_web_page_preview": "true"}
        ).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if not body.get("ok"):
                raise RuntimeError(f"Telegram API error: {body}")


def _chunks(text: str, size: int) -> list[str]:
    """قسّم النص على حدود الأسطر لتجنّب قطع صفقة في المنتصف."""
    if len(text) <= size:
        return [text]
    out, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > size:
            out.append(cur)
            cur = ""
        cur += line + "\n"
    if cur.strip():
        out.append(cur)
    return out


def main() -> int:
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(
            "❌ يجب ضبط TELEGRAM_TOKEN و TELEGRAM_CHAT_ID.\n"
            "أضِفهما كـ Secrets في إعدادات المستودع (Settings → Secrets → Actions).",
            file=sys.stderr,
        )
        return 2

    message = build_message()
    send_telegram(token, chat_id, message)
    print("✅ تم إرسال الملخّص إلى تيليجرام بنجاح.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

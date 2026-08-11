#!/usr/bin/env python3
"""
أرسل تقرير الأداء (نفس محتوى اللوحة) إلى تيليجرام — PHASE 4.

Loads the paper account + journal, computes performance, formats the dashboard
as a Telegram message, and sends it. Designed for a scheduled run (daily) or
on demand. No real money — reporting only.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request

import config
from deals_bot import journal
from deals_bot import paper_trading as pt
from deals_bot.performance import compute
from deals_bot.report import build_report

PAPER_STATE = os.path.join("journal", "paper_account.json")
TELEGRAM_MAX = 4000


def send_telegram(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chunk in _chunks(text, TELEGRAM_MAX):
        data = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": chunk, "disable_web_page_preview": "true"}
        ).encode("utf-8")
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if not body.get("ok"):
                raise RuntimeError(f"Telegram API error: {body}")


def _chunks(text: str, size: int):
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

    account = pt.load_account(getattr(config, "ACCOUNT_BALANCE", 1000.0), PAPER_STATE)
    m = compute(account)
    recent = list(reversed(journal.load()))
    risk = {
        "risk_pct": getattr(config, "RISK_PER_TRADE_PRO", 0.005) * 100,
        "daily": getattr(config, "MAX_DAILY_LOSS_PCT", 0.015) * 100,
        "consec": getattr(config, "MAX_CONSECUTIVE_LOSSES", 3),
        "rr": getattr(config, "MIN_RISK_REWARD", 2.0),
        "max_open": getattr(config, "MAX_OPEN_POSITIONS", 5),
    }
    report = build_report(account, m, recent, risk)
    print(report)

    if not token or not chat_id:
        print("\n⚠️ TELEGRAM_TOKEN/CHAT_ID غير مضبوطين — طُبع التقرير فقط.", file=sys.stderr)
        return 0
    send_telegram(token, chat_id, report)
    print("\n✅ أُرسل تقرير الأداء إلى تيليجرام.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

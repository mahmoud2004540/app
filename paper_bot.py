#!/usr/bin/env python3
"""
حلقة البوت الورقية (Paper Trading) — PHASE 2.

Runs ONE cycle of the paper-trading loop: monitor open paper positions, then open
new APPROVED setups through the decision pipeline. Persists the paper account +
journal to the repo and sends Telegram alerts on opens/closes. No real money.

Designed to run on a schedule (GitHub Actions), not as an infinite loop.

Env:
  TELEGRAM_TOKEN / TELEGRAM_CHAT_ID   (اختياري — للإشعارات)
  MARKETS      (افتراضي crypto)
  TIMEFRAME    (افتراضي 1h)
  PAPER_EQUITY (افتراضي ACCOUNT_BALANCE)
"""

from __future__ import annotations

import os
import sys
import time

import config
from deals_bot import paper_trading as pt
from deals_bot.bot_loop import run_cycle
from deals_bot.pipeline import _risk_engine
from deals_bot.providers import fetch
from deals_bot.strategy import resolve_symbols

PAPER_STATE = os.path.join("journal", "paper_account.json")


def _fetch(sym, market, tf, limit):
    src = "auto" if market == "crypto" else "yfinance"
    return fetch(sym, market, src, tf, limit=limit)


def _send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    import json
    import urllib.parse
    import urllib.request

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
    ).encode("utf-8")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as resp:
            json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ تعذّر إرسال تيليجرام: {exc}")


def main() -> int:
    if getattr(config, "LIVE_TRADING_ENABLED", False):
        print("🛑 LIVE_TRADING_ENABLED=True غير مدعوم هنا — هذا البوت ورقي فقط.")
        return 2

    market = os.environ.get("MARKETS", "crypto").split(",")[0].strip() or "crypto"
    timeframe = os.environ.get("TIMEFRAME", "1h")
    confirm_tf = getattr(config, "CONFIRM_TIMEFRAME", "15m")
    equity0 = float(os.environ.get("PAPER_EQUITY", getattr(config, "ACCOUNT_BALANCE", 1000.0)))

    account = pt.load_account(equity0, PAPER_STATE)
    engine = _risk_engine()
    symbols = resolve_symbols(market, "auto")
    now_ts = time.time()

    print(f"📄 Paper Bot: {len(symbols)} رمزًا | رصيد {account.equity:.2f} | "
          f"مفتوحة {len(account.positions)}")

    events = run_cycle(
        account, symbols, _fetch, now_ts, engine,
        fetch_confirm=_fetch, market=market, base_tf=timeframe, confirm_tf=confirm_tf,
        fee_rate=getattr(config, "FEE_RATE", 0.001),
        slippage_rate=getattr(config, "SLIPPAGE_RATE", 0.0005),
    )
    pt.save_account(account, PAPER_STATE)

    stats = pt.account_stats(account)
    for e in events:
        icon = "🟢 فتح" if e.kind == "open" else "🔴 إغلاق"
        line = f"{icon} {e.symbol}: {e.detail}"
        print(line)
        _send_telegram(f"📄 Paper Trade\n{line}")

    summary = (
        f"📄 حساب Paper: رصيد {stats['equity']} ({stats['return_pct']:+.2f}%) | "
        f"مفتوحة {stats['open']} | مغلقة {stats['closed']} | "
        f"نجاح {stats['win_rate']}% | عامل ربح {stats['profit_factor']}"
    )
    print(summary)
    if events:                       # أرسل ملخّصًا فقط حين يحدث شيء
        _send_telegram(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())

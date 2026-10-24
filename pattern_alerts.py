#!/usr/bin/env python3
"""
تنبيهات تلقائية بالنماذج الاحترافية (وتد هابط / قاع مزدوج يومي، علم صاعد 4 ساعات).

كل تشغيل:
  1) يقيّم الصفقات المفتوحة في journal/pattern_trades.jsonl (ربح/خسارة من الشموع الحقيقية).
  2) مرة لكل شمعة 4 ساعات جديدة: يفحص الكون كله ويبعت الكسرات الجديدة بس (من غير تكرار).
  لو مفيش جديد → ما يبعتش حاجة (مفيش إزعاج).

التشغيل:  python pattern_alerts.py            (يحتاج TELEGRAM_TOKEN و TELEGRAM_CHAT_ID)
          python pattern_alerts.py --dry-run  (يطبع بس)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import config
import deals_bot  # noqa: F401 - يطبّق إعدادات لوحة التحكم (رأس المال ونسبة المخاطرة)
from deals_bot import pattern_scan as ps
from deals_bot import pro_patterns as pp

STATE = os.path.join("journal", "pattern_alerts_state.json")


def _fetch(symbol, timeframe):
    from deals_bot.providers import fetch_gate, fetch_okx
    try:
        return fetch_okx(symbol, timeframe, 300).candles
    except Exception:  # noqa: BLE001 - عملة Gate
        return fetch_gate(symbol, timeframe, 300).candles


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not args.dry_run and (not token or not chat):
        print("❌ يجب ضبط TELEGRAM_TOKEN و TELEGRAM_CHAT_ID.", file=sys.stderr)
        return 2
    now = time.time()
    if not args.dry_run:
        n = ps.evaluate_open(_fetch, now)
        if n:
            print(f"📒 اتقفلت {n} صفقة نماذج في السجل.")
    # القرار بيتغيّر بس مع قفل شمعة 4 ساعات جديدة (أصغر فريم مستخدم)
    bar = int(now // pp.TF_SECONDS["4h"])
    try:
        with open(STATE, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        state = {}
    if state.get("last_bar") == bar and not args.dry_run:
        print("⏭ الشمعة الحالية اتفحصت — مستني قفل شمعة 4 ساعات جديدة.")
        return 0
    res = ps.scan(now)
    print(f"🔎 فحص {res['okx'] + res['gate']} عملة — السوق {res['bull']} — {len(res['setups'])} كسر")
    equity = float(getattr(config, "ACCOUNT_BALANCE", 1000.0))
    risk = float(getattr(config, "RISK_PER_TRADE_PRO", 0.02))
    new = res["setups"] if args.dry_run else ps.record_new(res["setups"], now)
    if not args.dry_run:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump({"last_bar": bar}, f)
    if not new:
        print("🔕 مفيش كسر جديد — ما بعتناش حاجة.")
        return 0
    text = ("🚨 نموذج احترافي جديد\n\n" + "\n\n".join(ps.format_setup(d, equity, risk) for d in new[:5])
            + "\n\n" + ps.stats_line() + "\n⚠️ مفيش صفقة مضمونة — التزم بالوقف.")
    print(text)
    if not args.dry_run:
        from send_digest import send_telegram
        send_telegram(token, chat, text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

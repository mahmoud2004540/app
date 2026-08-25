#!/usr/bin/env python3
"""
ماسح ICT / Smart Money Concepts — يمسح كل الكون ويرسل أفضل صفقة ≥80 لتيليجرام.

Institutional-style ICT scanner as a scheduled job. Runs the full ICT model
(HTF bias → liquidity → price delivery → multi-confirmation entry → /100 score)
on every symbol, and sends ONLY the single best tradeable setup (score ≥
ICT_MIN_SCORE) to Telegram. If nothing qualifies it says NO TRADE and stays
quiet (no noise). Quality over quantity — spot-only, long setups.

Env:
  TELEGRAM_TOKEN / TELEGRAM_CHAT_ID   (اختياري — للإشعارات)
  MARKETS      (افتراضي crypto)
  ICT_LIMIT    (اختياري: حدّ عدد الرموز للفحص السريع؛ 0 = الكل)
  ICT_SEND_NOTRADE (اختياري: 1 = ابعت رسالة NO TRADE أيضًا؛ الافتراضي صامت)
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request

import config
from deals_bot import ict
from deals_bot.providers import fetch
from deals_bot.strategy import resolve_symbols

SENT_STATE = os.path.join("journal", "ict_sent.json")


def _fetch(sym, market, tf, limit):
    src = "auto" if market == "crypto" else "yfinance"
    return fetch(sym, market, src, tf, limit=limit)


def _send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("ℹ️ لا توكن تيليجرام — طباعة فقط.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chunk in _chunks(text, 4000):
        data = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": chunk, "disable_web_page_preview": "true"}
        ).encode("utf-8")
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                if not body.get("ok"):
                    print(f"⚠️ Telegram: {body}")
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ تعذّر إرسال تيليجرام: {exc}")


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


def _dedup_key(s: ict.ICTSetup) -> str:
    return f"ICT:{s.symbol}:{round(s.entry, 8)}"


def _recently_sent(key: str, hours: float) -> bool:
    try:
        with open(SENT_STATE, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:  # noqa: BLE001
        return False
    ts = data.get(key)
    return ts is not None and (time.time() - float(ts)) <= hours * 3600


def _mark_sent(key: str) -> None:
    try:
        data = {}
        try:
            with open(SENT_STATE, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:  # noqa: BLE001
            data = {}
        now = time.time()
        data[key] = now
        # نظافة: احذف ما مضى عليه أكثر من 48 ساعة
        data = {k: v for k, v in data.items() if now - float(v) <= 48 * 3600}
        os.makedirs("journal", exist_ok=True)
        with open(SENT_STATE, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ تعذّر حفظ حالة ICT: {exc}")


def main() -> int:
    markets = [m.strip() for m in os.environ.get("MARKETS", "crypto").split(",")
               if m.strip() in ("crypto", "stocks", "forex")] or ["crypto"]
    limit = int(os.environ.get("ICT_LIMIT", "0") or "0")
    resend_h = float(getattr(config, "ICT_RESEND_HOURS", 24))

    print(f"📊 ماسح ICT: الأسواق {markets} | حدّ الرموز {limit or 'الكل'} | "
          f"العتبة ≥{ict.ICT_MIN_SCORE:.0f}")

    best, all_setups = ict.scan_ict(markets, _fetch, resolve_symbols, limit_symbols=limit)

    # لوج تشخيصي: أعلى 5 مرشّحين (حتى لو تحت العتبة) — شفافية
    top = all_setups[:5]
    print(f"🔎 فُحص {len(all_setups)} رمزًا. أعلى المرشّحين:")
    for s in top:
        tag = "✅" if s.is_tradeable else "  "
        print(f"  {tag} {s.symbol}: {s.score:.0f}/100 (bias={s.htf_bias}, RR={s.rr:.1f})")

    if best is None:
        msg = ("📊 ICT / Smart Money\n\n🚫 NO TRADE — لا يوجد إعداد ICT مكتمل "
               f"(≥{ict.ICT_MIN_SCORE:.0f}/100) الآن.\n"
               "الجودة قبل الكمية — البوت ينتظر التوافق الكامل "
               "(HTF Bias + سيولة + كنس + اندفاع + FVG/OB + تأكيد).")
        print(msg)
        if os.environ.get("ICT_SEND_NOTRADE", "").lower() in ("1", "true", "yes"):
            _send_telegram(msg)
        return 0

    key = _dedup_key(best)
    if _recently_sent(key, resend_h):
        print(f"🔕 {best.symbol}: أفضل صفقة ICT أُرسلت خلال {resend_h:g}h — لا تكرار.")
        return 0

    out = ict.format_ict(best, when="1D→4H→1H")
    print("----- أفضل صفقة ICT -----")
    print(out)
    print("-------------------------")
    _send_telegram(out)
    _mark_sent(key)
    print("✅ أُرسلت أفضل صفقة ICT إلى تيليجرام.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

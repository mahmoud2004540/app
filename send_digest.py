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
from deals_bot.formatter import DISCLAIMER, format_picks, format_watch
from deals_bot.strategy import market_is_bullish, top_picks


def _alert_only() -> bool:
    return os.environ.get("ALERT_ONLY", "").lower() in ("1", "true", "yes")

TELEGRAM_MAX = 4000  # حد أمان أقل من 4096 لتفادي رفض الرسالة


def build_message():
    """يبني نص الرسالة، أو None في وضع التنبيه (ALERT_ONLY) حين لا توجد صفقة."""
    markets = [
        m.strip()
        for m in os.environ.get("MARKETS", "crypto,stocks,forex").split(",")
        if m.strip() in ("crypto", "stocks", "forex")
    ] or ["crypto"]
    timeframe = os.environ.get("TIMEFRAME", config.DEFAULT_TIMEFRAME)
    alert_only = _alert_only()

    # وضع التنبيه: فحص رخيص أولًا — لو السوق العام هابط لا نفحص كل العملات أصلًا.
    if alert_only and getattr(config, "TREND_MARKET_REGIME", True) and "crypto" in markets:
        if market_is_bullish(timeframe) is False:
            print("🔕 وضع التنبيه: السوق هابط — لا فحص ولا إرسال (توفير موارد).")
            return None

    # المنتج الأساسي: أفضل 1-2 صفقة من فحص كل العملات — الإعداد الرابح المُثبت
    # بالباك-تِست (ارتداد داخل اتجاه صاعد، درجة ≥85، + فلتر حالة السوق + EMA200).
    picks, candidates, market_bullish = top_picks(markets, timeframe=timeframe)
    min_score = int(getattr(config, "TREND_MIN_SCORE", 85))

    if alert_only and not picks:
        print("🔕 وضع التنبيه: لا صفقة مؤكّدة الآن — لم تُرسل رسالة.")
        return None

    header = (
        "🏆 أفضل الصفقات — مُنتقاة من فحص كل العملات\n"
        "(إعداد «ارتداد داخل اتجاه صاعد» — أفضلية مقاسة +0.38R لكل صفقة "
        "بالباك-تِست على بيانات حقيقية)\n\n"
    )
    if picks:
        # في صفقة/صفقتين مؤكّدة → نناديها باسمها: «هي دي»
        prefix = "🚨 صفقة جديدة مؤكّدة!\n\n" if alert_only else ""
        be_r = getattr(config, "TREND_BREAKEVEN_R", 0.0)
        tip = (
            f"🔒 إدارة: انقل وقف الخسارة إلى سعر الدخول بمجرّد تحقيق +{be_r:g}R "
            "(يحوّلها لصفقة بلا خسارة).\n\n"
            if be_r and be_r > 0 else ""
        )
        return prefix + header + tip + format_picks(picks)

    # لا صفقة مؤكّدة: نوضّح السبب ونعرض أقرب مرشّح باسمه (مراقبة) إن وُجد
    if market_bullish is False:
        why = (
            "🛑 السوق العام (BTC) تحت متوسّطه الآن — الشراء ضد التيار خاسر "
            "(مُثبت بالباك-تِست). الأفضل انتظار عودة السوق فوق متوسّطه.\n\n"
        )
        missing = "السوق العام هابط"
    else:
        why = (
            f"📭 لا يوجد إعداد اكتمل شرطه (درجة ≥{min_score}) الآن. الإعداد الرابح "
            "نادر — أفضل من صفقة ضعيفة: لا صفقة.\n\n"
        )
        missing = f"الدرجة أقل من {min_score}"

    if candidates:
        best = candidates[0]
        return header + why + format_watch(best, missing)
    return header + why + DISCLAIMER


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

    # فحص تشخيصي: أي مصادر السعر الفوري متاحة من هذا الخادم؟
    from deals_bot.providers import fetch_spot_binance, fetch_spot_coinbase

    for _name, _fn in (("Binance", fetch_spot_binance), ("Coinbase", fetch_spot_coinbase)):
        try:
            print(f"🔎 فحص السعر الفوري BTC-USD ({_name}): {_fn('BTC-USD')}")
        except Exception as exc:  # noqa: BLE001
            print(f"🔎 ⚠️ {_name} غير متاح: {exc}")

    message = build_message()
    if message is None:
        # وضع التنبيه: لا صفقة مؤكّدة — لا نرسل شيئًا (نتفادى الإزعاج).
        print("ℹ️ لا رسالة لإرسالها (وضع التنبيه بلا صفقة).")
        return 0
    print("----- محتوى الرسالة -----")
    print(message)
    print("-------------------------")
    send_telegram(token, chat_id, message)
    print("✅ تم إرسال الملخّص إلى تيليجرام بنجاح.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
import time
import urllib.parse
import urllib.request

import config
from deals_bot import journal
from deals_bot.formatter import DISCLAIMER, format_digest, format_picks, format_watch
from deals_bot.providers import fetch
from deals_bot.strategy import market_is_bullish, scan_universe, top_picks


def _alert_only() -> bool:
    # متغيّر البيئة له الأولوية؛ وإلا نأخذ الافتراضي من config (الدخول فقط افتراضيًا).
    env = os.environ.get("ALERT_ONLY")
    if env is not None and env.strip() != "":
        return env.lower() in ("1", "true", "yes")
    return bool(getattr(config, "ALERT_ONLY", False))


HEARTBEAT_STATE = os.path.join("journal", "last_heartbeat.json")


def _heartbeat_due(state_path: str = HEARTBEAT_STATE) -> bool:
    """هل نبضة اليوم لم تُرسَل بعد؟ (نبضة واحدة يوميًا كحدّ أقصى)."""
    if not bool(getattr(config, "HEARTBEAT_DAILY", True)):
        return False
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        with open(state_path, encoding="utf-8") as fh:
            if json.load(fh).get("date") == today:
                return False
    except Exception:  # noqa: BLE001 - ملف مفقود/تالف → النبضة مستحقّة
        pass
    return True


def _mark_heartbeat(state_path: str = HEARTBEAT_STATE) -> None:
    """سجّل أن نبضة اليوم أُرسلت (لمنع التكرار كل ساعتين)."""
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as fh:
            json.dump({"date": today}, fh)
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ تعذّر حفظ حالة النبضة: {exc}")


def _heartbeat_message(status: str) -> str:
    """نص النبضة اليومية القصيرة — تطمئنك أن البوت حيّ ولماذا ينتظر."""
    return (
        "🔔 البوت شغّال ✅ (وضع الدخول فقط)\n"
        f"{status}\n"
        "مستني صفقة مؤكّدة تخشها على طول — هبعتها لك فور ظهورها. "
        "لا رسائل مراقبة، فقط دخول حقيقي."
    )


_LAST_DIGEST = os.path.join("journal", "last_digest.json")


def _mark_new(deals) -> int:
    """
    علّم الصفقات الجديدة (لم تظهر في آخر تحديث) بـ _is_new، واحفظ القائمة الحالية.

    Returns how many are new since the previous digest — so we can say when
    nothing changed instead of repeating the same list as if it were fresh.
    """
    last = set()
    try:
        with open(_LAST_DIGEST, encoding="utf-8") as f:
            last = set(json.load(f))
    except Exception:  # noqa: BLE001
        last = set()
    new_n = 0
    for d in deals:
        d._is_new = d.symbol not in last
        if d._is_new:
            new_n += 1
    try:
        os.makedirs("journal", exist_ok=True)
        with open(_LAST_DIGEST, "w", encoding="utf-8") as f:
            json.dump([d.symbol for d in deals], f, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ تعذّر حفظ قائمة آخر تحديث: {exc}")
    return new_n


def _apply_new_strategy(picks, timeframe: str) -> None:
    """
    مرّر كل صفقة على الاستراتيجية الجديدة: تأكيد 15M + حجم مخاطرة محرّك المخاطر (0.5%).

    يضبط على كل صفقة: confirmed (تأكيد إطار 15 دقيقة) وحجم المركز وفق محرّك المخاطر.
    """
    from deals_bot.confirmation import confirm
    from deals_bot.providers import fetch
    from deals_bot.risk_engine import RiskConfig, RiskEngine

    eng = RiskEngine(RiskConfig(
        risk_per_trade=getattr(config, "RISK_PER_TRADE_PRO", 0.005),
        fee_rate=getattr(config, "FEE_RATE", 0.001),
        slippage_rate=getattr(config, "SLIPPAGE_RATE", 0.0005),
        min_rr=getattr(config, "MIN_RISK_REWARD", 2.0),
    ))
    ctf = getattr(config, "CONFIRM_TIMEFRAME", "15m")
    vmult = getattr(config, "CONFIRM_VOLUME_MULT", 1.3)
    equity = getattr(config, "ACCOUNT_BALANCE", 1000.0)
    for d in picks:
        src = "auto" if d.market == "crypto" else "yfinance"
        try:
            cs = fetch(d.symbol, d.market, src, ctf, limit=60)
            d.confirmed = confirm(cs, "BUY", vmult).confirmed
        except Exception:  # noqa: BLE001 - التأكيد أفضلية، لا يُفشل الإشارة
            d.confirmed = None
        qty, risk_amount = eng.position_size(equity, d.entry, d.stop_loss, d.direction)
        if qty > 0:
            d.qty, d.risk_amount = qty, risk_amount
        # إثراء بالمشاعر (CryptoPanic) — معلومة مساعدة، ليست فلترًا مُثبتًا
        try:
            from deals_bot.providers import fetch_sentiment
            s = fetch_sentiment(d.symbol)
            if s and s.get("posts"):
                d._sentiment = f"{s['label']} ({s['positive']}↑/{s['negative']}↓)"
        except Exception:  # noqa: BLE001
            pass


def _journal_maintenance(picks, timeframe: str) -> str:
    """سجّل الصفقات الجديدة، قيّم المفتوحة من الشموع الحقيقية، وأرجع ملاحظة التعلّم."""
    try:
        now = time.time()
        added = journal.record_signals(picks, timeframe, now)
        if added:
            print(f"📓 سُجّلت {added} صفقة جديدة في سجل التداول.")

        def _fetch(sym, mkt, tf, lim):
            src = "auto" if mkt == "crypto" else "yfinance"
            return fetch(sym, mkt, src, tf, limit=lim)

        closed = journal.evaluate_open(_fetch)
        if closed:
            print(f"📓 أُغلقت {closed} صفقة بعد تقييم نتيجتها.")
        be = getattr(config, "TREND_MIN_SCORE", 85)  # noqa: F841 - reserved for future tuning
        return journal.learning_note(backtest_expectancy=0.38)
    except Exception as exc:  # noqa: BLE001 - السجل إضافة، لا يجب أن يُفشل الإرسال
        print(f"⚠️ سجل التداول: {exc}")
        return ""

TELEGRAM_MAX = 4000  # حد أمان أقل من 4096 لتفادي رفض الرسالة


def build_prepump_message(markets, timeframe: str) -> str:
    """
    رسالة «ما قبل الاندفاع» — عملة أو اثنتان لكل قسم، بأعلى جودة (درجة ≥85).

    قسمان: (1) تجميع/انضغاط قبل الاندفاع، (2) بداية الاندفاع (أول كسر بحجم).
    مع بوّابة حالة السوق لرفع نسبة النجاح، وملاحظة أمينة عن طبيعة الدخول المبكّر.
    """
    _signals, accums, earlies = scan_universe(markets, timeframe=timeframe)

    banner = ""
    if getattr(config, "PREPUMP_MARKET_REGIME", True) and "crypto" in markets:
        if market_is_bullish(timeframe) is False:
            banner = ("⚠️ السوق العام (BTC) تحت متوسّطه — إشارات الكسر أضعف الآن؛ "
                      "تعامل بحذر أو انتظر عودة السوق.\n\n")

    head = (
        "🎯 صفقات ما قبل الاندفاع فقط (قبل/بداية الـ pump — لا مطاردة)\n"
        f"أقوى {getattr(config, 'PREPUMP_TOP', 2)} فقط لكل قسم (درجة ≥"
        f"{int(getattr(config, 'PREPUMP_MIN_SCORE', 85))})\n\n"
    )
    msg = head + banner
    msg += format_digest(accums, title=f"1) قبل الاندفاع — تجميع/انضغاط (الأبكر) ({timeframe})")
    msg += "\n\n" + format_digest(
        earlies, title=f"2) بداية الاندفاع — أول كسر بحجم ({timeframe})")
    if not accums and not earlies:
        msg += ("\n\n📭 لا يوجد إعداد قوي (درجة ≥"
                f"{int(getattr(config, 'PREPUMP_MIN_SCORE', 85))}) الآن. "
                "الإعداد النادر أفضل من صفقة ضعيفة — البوت ينتظر.")
    msg += (
        "\n\nℹ️ صدق تام: «ما قبل الاندفاع» دخول مبكّر — أعلى مكافأة لكن نسبة نجاحه "
        "أقل بطبيعته من استراتيجية الاتجاه المؤكّدة (+0.38R). رفعنا العتبة وفلتر "
        "السوق لأعلى جودة ممكنة، لكن استخدم وقف الخسارة دائمًا."
    )
    return msg


def build_message():
    """يبني نص الرسالة، أو None في وضع التنبيه (ALERT_ONLY) حين لا توجد صفقة."""
    markets = [
        m.strip()
        for m in os.environ.get("MARKETS", "crypto,stocks,forex").split(",")
        if m.strip() in ("crypto", "stocks", "forex")
    ] or ["crypto"]
    timeframe = os.environ.get("TIMEFRAME", config.DEFAULT_TIMEFRAME)
    alert_only = _alert_only()

    # وضع «ما قبل الاندفاع» (تجميع/انضغاط + بداية اندفاع) — عملة أو اثنتان لكل قسم
    if os.environ.get("DIGEST_MODE", "trend").lower() == "prepump" and not alert_only:
        return build_prepump_message(markets, timeframe)

    # وضع التنبيه: فحص رخيص أولًا — لو السوق العام هابط لا نفحص كل العملات أصلًا.
    if alert_only and getattr(config, "TREND_MARKET_REGIME", True) and "crypto" in markets:
        if market_is_bullish(timeframe) is False:
            if _heartbeat_due():
                _mark_heartbeat()
                print("🔔 وضع الدخول فقط: السوق هابط — إرسال نبضة اليوم.")
                return _heartbeat_message("السوق العام (BTC): هابط 🔴 — لا نشتري ضد التيار.")
            print("🔕 وضع الدخول فقط: السوق هابط — لا فحص ولا إرسال (نبضة اليوم أُرسلت).")
            return None

    # المنتج الأساسي: أفضل 1-2 صفقة من فحص كل العملات — الإعداد الرابح المُثبت
    # بالباك-تِست (ارتداد داخل اتجاه صاعد، درجة ≥85، + فلتر حالة السوق + EMA200).
    picks, candidates, market_bullish = top_picks(markets, timeframe=timeframe)
    min_score = int(getattr(config, "TREND_MIN_SCORE", 85))

    # الاستراتيجية الجديدة: تأكيد الدخول + حجم مخاطرة محرّك المخاطر (0.5%) لكل صفقة
    if picks:
        _apply_new_strategy(picks, timeframe)
        # وضع الدخول فقط: لا نرسل إلا الصفقات اللي حصل فيها التأكيد فعلًا (تخشها على
        # طول) — نحذف أي «بانتظار التأكيد».
        if alert_only and getattr(config, "ALERT_REQUIRE_CONFIRM", True):
            confirmed = [d for d in picks if d.confirmed is True]
            if len(confirmed) != len(picks):
                print(f"🔎 وضع الدخول فقط: {len(picks) - len(confirmed)} صفقة "
                      "لسه بانتظار التأكيد — لن تُرسَل حتى يكتمل التأكيد.")
            picks = confirmed

    if alert_only and not picks:
        if _heartbeat_due():
            _mark_heartbeat()
            state = ("السوق صاعد 🟢 لكن لا صفقة اكتمل تأكيدها بعد"
                     if market_bullish else "السوق العام: هابط 🔴")
            print("🔔 وضع الدخول فقط: لا صفقة مؤكّدة — إرسال نبضة اليوم.")
            return _heartbeat_message(state)
        print("🔕 وضع الدخول فقط: لا صفقة مؤكّدة الآن — لم تُرسل رسالة (نبضة اليوم أُرسلت).")
        return None

    header = (
        "🏆 أفضل الصفقات — على الاستراتيجية الجديدة\n"
        "(اتجاه صاعد + ارتداد + تأكيد الدخول + محرّك مخاطر 0.5% — "
        "أفضلية مقاسة +0.38R داخل العيّنة، +0.19R خارجها)\n\n"
    )
    # المرحلتان 12+13: سجّل الصفقات الجديدة، قيّم المفتوحة، واحصل على ملاحظة التعلّم
    # (في الوضع العادي فقط — نُبقي وضع التنبيه السريع رخيصًا).
    note = "" if alert_only else _journal_maintenance(picks, timeframe)
    tail = ("\n\n" + note) if note else ""

    if picks:
        # في صفقة/صفقتين → نناديها باسمها: «هي دي»
        new_n = _mark_new(picks)
        all_confirmed = all(getattr(d, "confirmed", None) is True for d in picks)
        if alert_only:
            prefix = ("🚨 صفقة جديدة مؤكّدة!\n\n" if all_confirmed
                      else "🎯 أفضل صفقة الآن — بانتظار تأكيد 30 دقيقة، راقبها قبل الدخول\n\n")
        else:
            prefix = ""
        freshness = (f"🆕 {new_n} جديدة | 🔁 {len(picks) - new_n} مكرّرة\n\n"
                     if not alert_only else "")
        be_r = getattr(config, "TREND_BREAKEVEN_R", 0.0)
        tip = (
            f"🔒 إدارة: انقل وقف الخسارة إلى سعر الدخول بمجرّد تحقيق +{be_r:g}R "
            "(يحوّلها لصفقة بلا خسارة).\n\n"
            if be_r and be_r > 0 else ""
        )
        return prefix + header + freshness + tip + format_picks(picks) + tail

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

    # زي الأول: نعرض أفضل عدة عملات (5) بالتفاصيل بدل واحدة — كلها مراقبة الآن.
    if candidates:
        show_n = int(getattr(config, "DIGEST_WATCH_TOP", 5))
        top = candidates[:show_n]
        _apply_new_strategy(top, timeframe)
        for d in top:
            d.confirmed = None          # لا نضع «مؤكّدة» — الظرف العام مراقبة
        new_n = _mark_new(top)
        change = (f"🆕 {new_n} جديدة منذ آخر تحديث"
                  if new_n else "🔁 لا جديد — نفس مرشّحي آخر مرة")
        watch_head = (
            f"👀 أقرب {len(top)} مرشّحين الآن (مراقبة — {missing})\n{change}:\n\n"
        )
        return header + why + watch_head + format_picks(top) + tail
    return header + why + DISCLAIMER + tail


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

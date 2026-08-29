#!/usr/bin/env python3
"""
تشخيص تيليجرام: يكشف *أين* تذهب الرسائل فعلًا ويبعت رسالة اختبار حيّة.

المشكلة: اللوج يقول «تم الإرسال بنجاح» (تيليجرام يرد ok:true) لكن المستخدم لا
يستلم. السبب شبه المؤكّد: TELEGRAM_CHAT_ID يشير إلى شات غير الذي يفتحه المستخدم،
أو التوكن لبوت آخر. لا نقدر رؤية السرّ من الكود، لكن هذا السكربت (يملك السرّ في
بيئة التشغيل) يطبع هوية البوت والشات (بلا كشف التوكن) ويبعت رسالة اختبار موسومة
بالوقت — فيؤكّد المستخدم فورًا: هل وصلت؟ وإلى أي بوت/شات.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request


def _api(token: str, method: str, params: dict | None = None) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode("utf-8") if params else None
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("❌ TELEGRAM_TOKEN / TELEGRAM_CHAT_ID غير مضبوطين.", file=sys.stderr)
        return 2

    # هوية غير حسّاسة تساعد التشخيص (بلا كشف التوكن كاملًا)
    print(f"🔑 التوكن ينتهي بـ: ...{token[-6:]}   |   chat_id المضبوط: {chat_id}")

    # (1) مَن البوت؟ — اسم المستخدم الذي يجب أن يفتحه المستخدم
    try:
        me = _api(token, "getMe")
        if me.get("ok"):
            u = me["result"]
            print(f"🤖 البوت: @{u.get('username')}  (الاسم: {u.get('first_name')}, id: {u.get('id')})")
        else:
            print(f"🤖 getMe فشل: {me}")
    except Exception as exc:  # noqa: BLE001
        print(f"🤖 getMe خطأ: {exc}")

    # (2) إلى أي شات تذهب الرسائل فعلًا؟ — نوعه واسمه
    try:
        ch = _api(token, "getChat", {"chat_id": chat_id})
        if ch.get("ok"):
            c = ch["result"]
            ident = c.get("username") or c.get("title") or c.get("first_name") or "—"
            print(f"💬 الشات الهدف: نوع={c.get('type')}  الاسم/المعرّف={ident}  id={c.get('id')}")
        else:
            print(f"💬 getChat فشل: {ch}  ← chat_id غالبًا خطأ أو البوت ليس عضوًا فيه.")
    except Exception as exc:  # noqa: BLE001
        print(f"💬 getChat خطأ: {exc}")

    # (3) رسالة اختبار حيّة موسومة بالوقت — يؤكّد المستخدم استلامها فورًا
    stamp = time.strftime("%H:%M:%S UTC")
    text = (
        f"🔧 اختبار مباشر من البوت — {stamp}\n"
        f"لو وصلتك الرسالة دي، يبقى الإرسال شغّال وواصل للشات الصح.\n"
        f"ردّ بكلمة «وصلت» لو شفتها. ✅"
    )
    try:
        r = _api(token, "sendMessage", {"chat_id": chat_id, "text": text})
        if r.get("ok"):
            mid = r["result"].get("message_id")
            print(f"✅ رسالة الاختبار أُرسلت (message_id={mid}). تيليجرام أكّد الاستلام (ok:true).")
        else:
            print(f"❌ sendMessage رد ok:false: {r}")
            return 1
    except Exception as exc:  # noqa: BLE001
        print(f"❌ sendMessage خطأ: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

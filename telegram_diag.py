#!/usr/bin/env python3
"""تشخيص تيليجرام: هوية البوت/الشات + رسالة اختبار + آخر من كاتب البوت."""
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

    print(f"🔑 التوكن ينتهي بـ: ...{token[-6:]}")
    print(f"📍 CHAT_ID المضبوط طوله={len(str(chat_id))} ويبدأ بـ {str(chat_id)[:2]}...")

    try:
        me = _api(token, "getMe")
        if me.get("ok"):
            u = me["result"]
            print(f"🤖 البوت: @{u.get('username')}  (الاسم: {u.get('first_name')}, id: {u.get('id')})")
        else:
            print(f"🤖 getMe فشل: {me}")
            return 1
    except Exception as exc:
        print(f"🤖 getMe خطأ: {exc}")
        return 1

    try:
        ch = _api(token, "getChat", {"chat_id": chat_id})
        if ch.get("ok"):
            c = ch["result"]
            ident = c.get("username") or c.get("title") or c.get("first_name") or "—"
            uname = f"@{c['username']}" if c.get("username") else "(مفيش username)"
            print(f"💬 الشات المضبوط: نوع={c.get('type')}  الاسم={ident}  username={uname}  id={c.get('id')}")
        else:
            print(f"💬 getChat فشل: {ch}")
    except Exception as exc:
        print(f"💬 getChat خطأ: {exc}")

    try:
        upd = _api(token, "getUpdates", {"timeout": "0", "limit": "20"})
        if upd.get("ok"):
            seen = []
            for item in upd.get("result") or []:
                msg = item.get("message") or item.get("edited_message") or {}
                fr = msg.get("from") or {}
                chat = msg.get("chat") or {}
                key = (chat.get("id"), fr.get("id"))
                if key in seen:
                    continue
                seen.append(key)
                print(
                    "📨 حدّ كاتب البوت: "
                    f"from={fr.get('first_name')} @{fr.get('username')} "
                    f"chat_id={chat.get('id')} type={chat.get('type')} "
                    f"text={(msg.get('text') or '')[:40]}"
                )
            if not seen:
                print("📨 مفيش getUpdates حديث — البوت محدثش محد كاتبه قريب. افتح @Bighotwelcome_bot وابعت /start.")
        else:
            print(f"📨 getUpdates فشل: {upd}")
    except Exception as exc:
        print(f"📨 getUpdates خطأ: {exc}")

    stamp = time.strftime("%Y-%m-%d %H:%M:%S UTC")
    text = (
        f"🚨 رسالة تأكيد من البوت — {stamp}\n"
        f"البوت: @Bighotwelcome_bot\n"
        f"لو قريت الرسالة دي ابعت /start هنا واكتب: وصلت"
    )
    try:
        r = _api(token, "sendMessage", {"chat_id": chat_id, "text": text})
        if r.get("ok"):
            mid = r["result"].get("message_id")
            dest = r["result"].get("chat") or {}
            print(
                f"✅ اتبعت message_id={mid} إلى type={dest.get('type')} "
                f"name={dest.get('first_name') or dest.get('title')} "
                f"username=@{dest.get('username')}"
            )
        else:
            print(f"❌ sendMessage ok:false: {r}")
            return 1
    except Exception as exc:
        print(f"❌ sendMessage خطأ: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

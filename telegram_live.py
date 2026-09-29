#!/usr/bin/env python3
"""رد شبه فوري: long-poll على تيليجرام لمدة ساعات على GitHub Actions."""
from __future__ import annotations
import os, sys, time
import telegram_commands as tc

WINDOW = int(os.environ.get("LIVE_WINDOW_SEC", str(5 * 3600 + 1800)))

def main() -> int:
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = str(os.environ.get("TELEGRAM_CHAT_ID") or "")
    if not token or not chat_id:
        print("مفيش توكن/شات")
        return 2
    try:
        tc._api(token, "sendMessage", {
            "chat_id": chat_id,
            "text": "الرد بقى شبه فوري. اكتب /status دلوقتي كرسالة جديدة.",
        })
    except Exception as exc:
        print("announce", exc)
    off = tc._offset()
    end = time.time() + WINDOW
    print("live until", end)
    while time.time() < end:
        try:
            upd = tc._api(token, "getUpdates", {
                "timeout": "25",
                "limit": "50",
                "offset": str(off),
            })
        except Exception as exc:
            print("poll", exc)
            time.sleep(2)
            continue
        if not upd.get("ok"):
            print(upd)
            time.sleep(2)
            continue
        for item in upd.get("result") or []:
            uid = int(item.get("update_id") or 0)
            off = max(off, uid + 1)
            msg = item.get("message") or {}
            chat = str((msg.get("chat") or {}).get("id") or "")
            text = msg.get("text") or ""
            if chat != chat_id:
                continue
            reply = tc._handle(text)
            if not reply:
                continue
            try:
                tc._api(token, "sendMessage", {"chat_id": chat_id, "text": reply})
                print("cmd", text[:40])
            except Exception as exc:
                print("send", exc)
        tc._save_offset(off)
    return 0

if __name__ == "__main__":
    sys.exit(main())

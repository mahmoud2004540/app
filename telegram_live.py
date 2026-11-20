#!/usr/bin/env python3
from __future__ import annotations
import os, sys, time, re
import telegram_commands as tc
WINDOW = int(os.environ.get("LIVE_WINDOW_SEC", str(5 * 3600 + 1800)))

def main() -> int:
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = str(os.environ.get("TELEGRAM_CHAT_ID") or "")
    if not token or not chat_id:
        return 2
    try:
        tc.send_text(
            token,
            chat_id,
            "ورقي شغال بمخاطرة عالية (ورق فقط). اضغط زر ورقي للتفاصيل. التداول الحقيقي مقفول.",
        )
    except Exception as exc:
        print("announce", exc)
    off = tc._offset()
    end = time.time() + WINDOW
    from deals_bot import price_alerts
    last_check = 0.0
    while time.time() < end:
        # تنبيهات السعر: فحص كل دقيقة (طلب أسعار واحد لكل العملات)
        if time.time() - last_check >= 60:
            last_check = time.time()
            try:
                for msg in price_alerts.check():
                    tc.send_text(token, chat_id, msg)
                    print("alert", msg.splitlines()[0])
            except Exception as exc:
                print("alerts", exc)
        try:
            upd = tc._api(token, "getUpdates", {"timeout": "25", "limit": "50", "offset": str(off)})
        except Exception as exc:
            print("poll", exc)
            time.sleep(2)
            continue
        if not upd.get("ok"):
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
            cmd = tc._norm(text)
            cleaned = tc._clean_query(text)
            is_coin = bool(cleaned and re.fullmatch(r"[A-Z0-9][A-Z0-9\- ]{1,20}", cleaned) and not cmd.startswith("/"))
            if cmd in ("/scan", "/fast", "/pump", "/moon", "/paper", "/patterns") or is_coin:
                try:
                    tc.send_text(token, chat_id, "⏳ بحلل... لحظة.")
                except Exception:
                    pass
            reply = tc._handle(text)
            if not reply:
                continue
            try:
                tc.send_text(token, chat_id, reply)
                print("cmd", text[:40])
            except Exception as exc:
                print("send", exc)
        tc._save_offset(off)
    return 0

if __name__ == "__main__":
    sys.exit(main())

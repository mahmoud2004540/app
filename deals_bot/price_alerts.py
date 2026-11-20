"""
تنبيهات السعر: المستخدم يحدّد عملة وسعر، والبوت يبعتله أول ما السعر يوصل.

أوامر تيليجرام (عربي أو إنجليزي):
  تنبيه BTC 100000        → يبلّغك لما BTC يوصل 100,000 (فوق أو تحت السعر الحالي — بيتحدّد لوحده)
  تنبيه SOL +5%           → لما SOL يطلع 5% من سعره دلوقتي (أو -5% لما ينزل)
  تنبيه ETH 3.5k          → k = ألف، m = مليون
  تنبيهاتي                → قائمة التنبيهات الشغالة
  الغي 3  /  الغي الكل     → مسح تنبيه برقمه أو كلهم

الأسعار: OKX (طلب واحد لكل العملات) ثم Gate.io للعملات اللي مش على OKX.
الحالة في journal/price_alerts.json وبتترفع على المستودع عشان تفضل بعد إعادة التشغيل.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from typing import Callable, Dict, List, Optional

PATH = os.path.join("journal", "price_alerts.json")
MAX_ALERTS = 50
# أسماء شائعة بالعربي → الرمز
NAMES = {"بيتكوين": "BTC", "بتكوين": "BTC", "ايثريوم": "ETH", "إيثريوم": "ETH", "ايثيريوم": "ETH",
         "سولانا": "SOL", "ريبل": "XRP", "دوج": "DOGE", "دوجكوين": "DOGE", "بينانس": "BNB", "كاردانو": "ADA"}

_ADD = re.compile(r"^(?:/alert|alert|تنبيه|نبهني|نبّهني|نبهنى)\s+(\S+)\s+([+\-]?[\d.,]+)\s*([km%]?)\s*$", re.I)
_LIST = re.compile(r"^(?:/alerts|alerts|تنبيهاتي|تنبيهاتى|🔔 تنبيهاتي)$", re.I)
_DEL = re.compile(r"^(?:/del|del|الغي|الغى|إلغي|الغاء|إلغاء|امسح)\s+(?:تنبيه\s+)?(\d+|الكل|all)$", re.I)


# --------------------------------------------------------------------------- #
# التخزين
# --------------------------------------------------------------------------- #
def load(path: str = PATH) -> Dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("alerts"), list):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"next_id": 1, "alerts": []}


def save(data: Dict, path: str = PATH) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    persist(path)


def persist(path: str = PATH) -> None:
    """على GitHub Actions: ارفع الملف على الفرع عشان التنبيهات تفضل بعد إعادة التشغيل."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    try:
        subprocess.run(["git", "config", "user.name", "trading-bot"], check=False)
        subprocess.run(["git", "config", "user.email", "bot@users.noreply.github.com"], check=False)
        subprocess.run(["git", "add", path], check=False)
        if subprocess.run(["git", "diff", "--cached", "--quiet", path]).returncode == 0:
            return
        subprocess.run(["git", "commit", "-m", "chore(alerts): update price alerts [skip ci]"], check=False)
        branch = os.environ.get("GITHUB_REF_NAME") or "main"
        for _ in range(3):
            subprocess.run(["git", "pull", "--rebase", "origin", branch], check=False)
            if subprocess.run(["git", "push", "origin", f"HEAD:{branch}"]).returncode == 0:
                return
            time.sleep(2)
    except Exception as exc:  # noqa: BLE001 - التنبيه لسه شغال في الذاكرة حتى لو الرفع فشل
        print("alerts persist failed", exc)


# --------------------------------------------------------------------------- #
# الأسعار
# --------------------------------------------------------------------------- #
def normalize(sym: str) -> str:
    s = NAMES.get(sym.strip(), sym).strip().upper()
    for suffix in ("/USDT", "-USDT", "_USDT", "USDT", "/USD", "-USD", "USD"):
        if s.endswith(suffix) and len(s) > len(suffix):
            s = s[: -len(suffix)]
            break
    return s


def prices(bases: List[str]) -> Dict[str, float]:
    """آخر سعر لكل عملة: OKX (طلب واحد للكل) ثم Gate.io للباقي."""
    from .providers import _http_json

    want = {b.upper() for b in bases}
    out: Dict[str, float] = {}
    try:
        for r in _http_json("https://www.okx.com/api/v5/market/tickers?instType=SPOT", timeout=20, retries=2)["data"]:
            inst = r.get("instId", "")
            if inst.endswith("-USDT") and inst[:-5] in want and r.get("last"):
                out[inst[:-5]] = float(r["last"])
    except Exception:  # noqa: BLE001
        pass
    missing = want - set(out)
    if missing:
        try:
            for t in _http_json("https://api.gateio.ws/api/v4/spot/tickers", timeout=20, retries=2):
                pair = t.get("currency_pair", "")
                if pair.endswith("_USDT") and pair[:-5] in missing and t.get("last"):
                    out[pair[:-5]] = float(t["last"])
        except Exception:  # noqa: BLE001
            pass
    return out


def _px(x: float) -> str:
    if x >= 1000:
        return f"{x:,.2f}"
    if x >= 1:
        return f"{x:.4f}"
    if x >= 0.0001:
        return f"{x:.6g}"
    return f"{x:.12f}".rstrip("0")          # عملات صغيرة جدًا زي PEPE: 0.0000035319


# --------------------------------------------------------------------------- #
# الأوامر
# --------------------------------------------------------------------------- #
def handle_text(text: str, price_fn: Callable = prices, path: str = PATH,
                now: Optional[float] = None) -> Optional[str]:
    """لو الرسالة أمر تنبيهات يرجّع الرد، وإلا None (عشان باقي الأوامر تشتغل عادي)."""
    t = (text or "").strip()
    if _LIST.match(t):
        return list_text(path)
    m = _DEL.match(t)
    if m:
        return delete(m.group(1), path)
    m = _ADD.match(t)
    if m:
        return add(m.group(1), m.group(2), m.group(3).lower(), price_fn, path, now)
    return None


def add(sym: str, number: str, unit: str, price_fn: Callable = prices, path: str = PATH,
        now: Optional[float] = None) -> str:
    base = normalize(sym)
    try:
        val = float(number.replace(",", ""))
    except ValueError:
        return "⚠️ الرقم مش واضح. مثال: تنبيه BTC 100000"
    cur = price_fn([base]).get(base)
    if not cur:
        return f"⚠️ مش لاقي سعر {base} على OKX ولا Gate.io. اتأكد من اسم العملة (مثال: BTC، SOL، PEPE)."
    if unit == "%":
        target = cur * (1 + val / 100)
    else:
        target = val * {"k": 1_000, "m": 1_000_000}.get(unit, 1)
    if target <= 0:
        return "⚠️ السعر لازم يكون أكبر من صفر."
    if abs(target - cur) / cur < 0.0005:
        return f"ℹ️ {base} أصلًا عند {_px(cur)} دلوقتي — اختار سعر مختلف."
    data = load(path)
    if len(data["alerts"]) >= MAX_ALERTS:
        return f"⚠️ عندك {MAX_ALERTS} تنبيه شغال — امسح شوية الأول (الغي <رقم>)."
    direction = "above" if target > cur else "below"
    alert = {"id": data["next_id"], "symbol": base, "target": target, "direction": direction,
             "created_price": cur, "created_ts": now or time.time()}
    data["alerts"].append(alert)
    data["next_id"] += 1
    save(data, path)
    arrow = "⬆️ يطلع لـ" if direction == "above" else "⬇️ ينزل لـ"
    return (f"🔔 تمام — تنبيه #{alert['id']}: هبلّغك لما {base} {arrow} {_px(target)}\n"
            f"السعر دلوقتي: {_px(cur)} ({(target / cur - 1) * 100:+.1f}%)")


def list_text(path: str = PATH) -> str:
    data = load(path)
    if not data["alerts"]:
        return ("🔔 مفيش تنبيهات شغالة.\n"
                "ضيف واحد كده: تنبيه BTC 100000  أو  تنبيه SOL +5%")
    cur = prices([a["symbol"] for a in data["alerts"]])
    lines = ["🔔 تنبيهاتك الشغالة:"]
    for a in data["alerts"]:
        arrow = "⬆️" if a["direction"] == "above" else "⬇️"
        now_px = cur.get(a["symbol"])
        dist = f" — دلوقتي {_px(now_px)} ({(a['target'] / now_px - 1) * 100:+.1f}%)" if now_px else ""
        lines.append(f"#{a['id']} {a['symbol']} {arrow} {_px(a['target'])}{dist}")
    lines.append("\nللمسح: الغي <رقم>  أو  الغي الكل")
    return "\n".join(lines)


def delete(which: str, path: str = PATH) -> str:
    data = load(path)
    if which in ("الكل", "all"):
        n = len(data["alerts"])
        data["alerts"] = []
        save(data, path)
        return f"🗑 اتمسح {n} تنبيه."
    aid = int(which)
    before = len(data["alerts"])
    data["alerts"] = [a for a in data["alerts"] if a["id"] != aid]
    if len(data["alerts"]) == before:
        return f"⚠️ مفيش تنبيه رقم {aid}. ابعت «تنبيهاتي» تشوف الأرقام."
    save(data, path)
    return f"🗑 اتمسح تنبيه #{aid}."


# --------------------------------------------------------------------------- #
# الفحص الدوري
# --------------------------------------------------------------------------- #
def check(price_fn: Callable = prices, path: str = PATH) -> List[str]:
    """افحص كل التنبيهات: اللي وصل سعره يتبعت ويتمسح. يرجّع رسائل التنبيه."""
    data = load(path)
    if not data["alerts"]:
        return []
    cur = price_fn([a["symbol"] for a in data["alerts"]])
    fired, keep = [], []
    for a in data["alerts"]:
        p = cur.get(a["symbol"])
        hit = p is not None and (p >= a["target"] if a["direction"] == "above" else p <= a["target"])
        if not hit:
            keep.append(a)
            continue
        arrow = "⬆️ طلع لـ" if a["direction"] == "above" else "⬇️ نزل لـ"
        fired.append(f"🚨 تنبيه سعر #{a['id']}: {a['symbol']} {arrow} {_px(a['target'])}\n"
                     f"السعر دلوقتي: {_px(p)} (كان {_px(a['created_price'])} لما حطيت التنبيه)")
    if fired:
        data["alerts"] = keep
        save(data, path)
    return fired

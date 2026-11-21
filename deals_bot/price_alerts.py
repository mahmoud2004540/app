"""
تنبيهات السعر: المستخدم يحدّد عملة وسعر، والبوت يبعتله أول ما السعر يوصل.

أوامر تيليجرام (عربي أو إنجليزي):
  تنبيه BTC 100000        → يبلّغك لما BTC يوصل 100,000 (فوق أو تحت السعر الحالي — بيتحدّد لوحده)
  تنبيه SOL +5%           → لما SOL يطلع 5% من سعره دلوقتي (أو -5% لما ينزل)
  تنبيه ETH 3.5k          → k = ألف، m = مليون
  تنبيهاتي                → قائمة التنبيهات الشغالة
  الغي 3  /  الغي الكل     → مسح تنبيه برقمه أو كلهم
  راقب BTC 500            → كل ما BTC يتحرك 500 دولار (طلوع أو نزول) يبعتلك، ويبدأ يعدّ من السعر الجديد
  راقب PYTH 0.01          → نفس الفكرة لأي عملة، بالمبلغ اللي تختاره (مش نسبة)
  وقف BTC                 → يوقف مراقبة BTC

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
_WATCH = re.compile(r"^(?:/watch|watch|راقب|راقبلي|تابع|تابعلي)\s+(\S+)\s+([\d.,]+)\s*([k]?)\s*$", re.I)
_UNWATCH = re.compile(r"^(?:/unwatch|unwatch|وقف|اوقف|أوقف|الغي مراقبة|الغي)\s+([^\d\s]\S*)$", re.I)
_DEL = re.compile(r"^(?:/del|del|الغي|الغى|إلغي|الغاء|إلغاء|امسح)\s+(?:تنبيه\s+)?(\d+|الكل|all)$", re.I)


# --------------------------------------------------------------------------- #
# التخزين
# --------------------------------------------------------------------------- #
def load(path: str = PATH) -> Dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("alerts"), list):
            data.setdefault("watches", [])
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"next_id": 1, "alerts": [], "watches": []}


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


def _amt(x: float) -> str:
    """مبلغ حركة: 500 → «$500»، 0.5 → «$0.5»، 0.0001 → «$0.0001»."""
    return "$" + (f"{x:,.0f}" if x == int(x) and x >= 1 else f"{x:.10f}".rstrip("0").rstrip("."))


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
        return list_text(path, price_fn)
    m = _DEL.match(t)
    if m:
        return delete(m.group(1), path)
    m = _WATCH.match(t)
    if m:
        return watch(m.group(1), m.group(2), m.group(3).lower(), price_fn, path, now)
    m = _UNWATCH.match(t)
    if m and m.group(1) not in ("الكل", "all"):
        return unwatch(m.group(1), path)
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


def watch(sym: str, number: str, unit: str, price_fn: Callable = prices, path: str = PATH,
          now: Optional[float] = None) -> str:
    """مراقبة متكررة: كل ما السعر يتحرك «step» دولار من آخر سعر اتبلّغ بيه → رسالة."""
    base = normalize(sym)
    try:
        step = float(number.replace(",", "")) * (1_000 if unit == "k" else 1)
    except ValueError:
        return "⚠️ الرقم مش واضح. مثال: راقب BTC 500"
    if step <= 0:
        return "⚠️ المبلغ لازم يكون أكبر من صفر."
    cur = price_fn([base]).get(base)
    if not cur:
        return f"⚠️ مش لاقي سعر {base} على OKX ولا Gate.io. اتأكد من اسم العملة (مثال: BTC، SOL، PYTH)."
    if step < cur * 0.001:
        return (f"⚠️ {_amt(step)} صغير أوي على {base} (سعره {_px(cur)}) — هيبعتلك رسايل كل شوية. "
                f"جرّب مبلغ أكبر من {_px(cur * 0.001)}.")
    data = load(path)
    data["watches"] = [w for w in data["watches"] if w["symbol"] != base]
    data["watches"].append({"symbol": base, "step": step, "ref": cur, "created_ts": now or time.time()})
    save(data, path)
    return (f"👀 تمام — هراقب {base}: كل ما يتحرك {_amt(step)} طلوع أو نزول هبعتلك.\n"
            f"السعر دلوقتي: {_px(cur)} → أول إشارة عند {_px(cur + step)} أو {_px(cur - step)}\n"
            f"للإيقاف: وقف {base}")


def unwatch(sym: str, path: str = PATH) -> str:
    base = normalize(sym)
    data = load(path)
    before = len(data["watches"])
    data["watches"] = [w for w in data["watches"] if w["symbol"] != base]
    if len(data["watches"]) == before:
        return f"⚠️ مش براقب {base}. ابعت «تنبيهاتي» تشوف اللي شغال."
    save(data, path)
    return f"🛑 وقفت مراقبة {base}."


def list_text(path: str = PATH, price_fn: Callable = prices) -> str:
    data = load(path)
    if not data["alerts"] and not data["watches"]:
        return ("🔔 مفيش تنبيهات شغالة.\n"
                "• تنبيه عند سعر: تنبيه BTC 100000\n"
                "• كل ما يتحرك مبلغ: راقب BTC 500")
    cur = price_fn([a["symbol"] for a in data["alerts"]] + [w["symbol"] for w in data["watches"]])
    lines = []
    if data["watches"]:
        lines.append("👀 مراقبة الحركة:")
        for w in data["watches"]:
            now_px = cur.get(w["symbol"])
            extra = (f" — دلوقتي {_px(now_px)} ({'+' if now_px >= w['ref'] else '−'}{_amt(round(abs(now_px - w['ref']), 2 if abs(now_px - w['ref']) >= 1 else 10))} "
                     f"من آخر إشارة)") if now_px else ""
            lines.append(f"• {w['symbol']} كل ±{_amt(w['step'])}{extra}")
        lines.append("")
    if data["alerts"]:
        lines.append("🔔 تنبيهات عند سعر:")
    for a in data["alerts"]:
        arrow = "⬆️" if a["direction"] == "above" else "⬇️"
        now_px = cur.get(a["symbol"])
        dist = f" — دلوقتي {_px(now_px)} ({(a['target'] / now_px - 1) * 100:+.1f}%)" if now_px else ""
        lines.append(f"#{a['id']} {a['symbol']} {arrow} {_px(a['target'])}{dist}")
    lines.append("\nللمسح: الغي <رقم> • الغي الكل • وقف <عملة>")
    return "\n".join(lines)


def delete(which: str, path: str = PATH) -> str:
    data = load(path)
    if which in ("الكل", "all"):
        n = len(data["alerts"]) + len(data["watches"])
        data["alerts"], data["watches"] = [], []
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
    if not data["alerts"] and not data["watches"]:
        return []
    cur = price_fn([a["symbol"] for a in data["alerts"]] + [w["symbol"] for w in data["watches"]])
    fired, keep = [], []
    for w in data["watches"]:
        p = cur.get(w["symbol"])
        if p is None or abs(p - w["ref"]) < w["step"]:
            continue
        diff = p - w["ref"]
        arrow = "🟢⬆️ طلع" if diff > 0 else "🔴⬇️ نزل"
        fired.append(f"{arrow} {w['symbol']} {_amt(round(abs(diff), 2 if abs(diff) >= 1 else 10))}\n"
                     f"من {_px(w['ref'])} لـ {_px(p)} ({diff / w['ref'] * 100:+.2f}%)\n"
                     f"الإشارة الجاية عند {_px(p + w['step'])} أو {_px(p - w['step'])}")
        w["ref"] = p
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

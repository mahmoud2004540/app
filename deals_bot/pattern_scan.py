"""
فحص النماذج الاحترافية على الكون كله + حجم الصفقة + سجل النتائج الحقيقية.

يستخدمه زر «📐 نماذج احترافية» والتنبيهات التلقائية (pattern_alerts.py) — نفس الكود.
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional

from . import pro_patterns as pp

JOURNAL = os.path.join("journal", "pattern_trades.jsonl")
# عملات مستقرة ونسخ مغلّفة — مفيش نماذج نتداولها عليها
STABLES = {"USDT", "USDC", "DAI", "USD1", "FDUSD", "PYUSD", "TUSD", "USDE", "USDS", "USDG",
           "RLUSD", "EURC", "WBTC", "WETH", "STETH"}


def scan(now: Optional[float] = None, min_gate_volume: float = 100_000.0) -> Dict:
    """
    يرجّع {"bull": {tf: bool}, "okx": n, "gate": n, "setups": [...]}.
    OKX + عملات Gate.io السائلة اللي مش على OKX (من غير أسهم مرمّزة).
    """
    from .providers import fetch_gate, fetch_okx, list_gate_usd_products, list_okx_usd_products

    now = now or time.time()
    bull = {tf: pp.market_bullish([x for x in fetch_okx("BTC-USD", tf, 300).candles
                                   if x.ts + pp.TF_SECONDS[tf] <= now]) for tf in ("1d", "4h")}
    okx = {s for s in list_okx_usd_products() if s.split("-")[0] not in STABLES}
    try:
        gate = {s for s in list_gate_usd_products(min_gate_volume) if s.split("-")[0] not in STABLES} - okx
    except Exception:  # noqa: BLE001 - Gate إضافة؛ لو وقع نكمّل بـ OKX
        gate = set()
    tfs = [tf for tf in ("1d", "4h") if bull.get(tf)]
    setups: List[dict] = []
    if tfs:
        def one(sym):
            found = []
            fetch_fn = fetch_okx if sym in okx else fetch_gate
            for tf in tfs:
                try:
                    for d in pp.recent_setups(fetch_fn(sym, tf, 300).candles, tf, now):
                        d["symbol"] = sym
                        found.append(d)
                except Exception:  # noqa: BLE001 - عملة واحدة ما تبوّظش الفحص
                    pass
            return found
        with ThreadPoolExecutor(max_workers=8) as pool:
            setups = [d for group in pool.map(one, sorted(okx) + sorted(gate)) for d in group]
        setups.sort(key=lambda d: (-pp.MEASURED[d["pattern"]][2], d["bars_ago"]))
    return {"bull": bull, "okx": len(okx), "gate": len(gate), "setups": setups}


def position_size(equity: float, risk_pct: float, entry: float, stop: float) -> Dict:
    """
    حجم الصفقة (اللوت) الاحترافي: الخسارة لو ضرب الوقف = risk_pct من رأس المال.
    بدون رافعة: لو قيمة المركز أكبر من رأس المال نقصّه لرأس المال (والمخاطرة تقل).
    """
    per_unit = entry - stop
    if per_unit <= 0 or equity <= 0:
        return {"qty": 0.0, "value": 0.0, "risk": 0.0, "risk_pct": 0.0}
    qty = equity * risk_pct / per_unit
    if qty * entry > equity:
        qty = equity / entry
    return {"qty": qty, "value": qty * entry, "risk": qty * per_unit, "risk_pct": qty * per_unit / equity * 100}


def format_reply(res: Dict, equity: float, risk_pct: float, limit: int = 5) -> str:
    bull = res["bull"]
    head = ("📐 نماذج احترافية (وتد هابط + قاع مزدوج يومي، علم صاعد 4 ساعات)\n"
            f"السوق (BTC فوق EMA200): يومي {'🟢' if bull.get('1d') else '🔴'} | "
            f"4 ساعات {'🟢' if bull.get('4h') else '🔴'}\n\n")
    if not any(bull.values()):
        return head + ("NO TRADE — السوق مش صاعد على الفريمين. النماذج دي بتكسب في السوق "
                       "الصاعد بس (مقاس) — بنستنى.")
    if not res["setups"]:
        return head + (f"NO TRADE — فحصت {res['okx'] + res['gate']} عملة ({res['okx']} OKX + "
                       f"{res['gate']} Gate.io): مفيش نموذج اتكسر حديثًا ولسه مناسب للدخول.")
    body = "\n\n".join(format_setup(d, equity, risk_pct) for d in res["setups"][:limit])
    return (head + body + "\n\n⚠️ مفيش صفقة مضمونة — النجاح التاريخي ~55% والربح من إن المكسب "
            "أكبر من الخسارة. التزم بالوقف.")


def format_setup(d: Dict, equity: float, risk_pct: float) -> str:
    s = position_size(equity, risk_pct, d["entry"], d["stop"])
    return (pp.format_setup(d) +
            f"\n💼 الحجم: {s['qty']:.6g} عملة (≈ ${s['value']:,.2f}) — "
            f"لو ضرب الوقف تخسر ${s['risk']:,.2f} ({s['risk_pct']:.1f}% من ${equity:,.0f})")


# --------------------------------------------------------------------------- #
# سجل الصفقات المُرسَلة ونتيجتها الحقيقية
# --------------------------------------------------------------------------- #
def _trade_id(d: Dict) -> str:
    return f"{d['timeframe']}:{d['symbol']}:{d['pattern']}:{round(d['breakout_ts'])}"


def load(path: str = JOURNAL) -> List[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def save(trades: List[dict], path: str = JOURNAL) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for t in trades:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")


def record_new(setups: List[dict], now: float, path: str = JOURNAL) -> List[dict]:
    """سجّل الجديد بس (نفس الكسر ما يتبعتش مرتين). يرجّع الصفقات الجديدة."""
    trades = load(path)
    seen = {t["id"] for t in trades}
    new = []
    for d in setups:
        tid = _trade_id(d)
        if tid in seen:
            continue
        seen.add(tid)
        trades.append({"id": tid, "symbol": d["symbol"], "timeframe": d["timeframe"], "pattern": d["pattern"],
                       "entry": d["entry"], "stop": d["stop"], "target": d["target"], "opened_ts": now,
                       "status": "open", "result_r": None, "closed_ts": None})
        new.append(d)
    if new:
        save(trades, path)
    return new


def evaluate_open(fetch_fn: Callable, now: Optional[float] = None, max_bars: int = 100,
                  path: str = JOURNAL) -> int:
    """قيّم المفتوحة من الشموع المقفولة بعد الإرسال: الوقف أولًا (متحفّظ)، ثم الهدف، ثم حد المدة."""
    now = now or time.time()
    trades = load(path)
    closed = 0
    for t in trades:
        if t["status"] != "open":
            continue
        try:
            cs = fetch_fn(t["symbol"], t["timeframe"])
        except Exception:  # noqa: BLE001
            continue
        step = pp.TF_SECONDS[t["timeframe"]]
        after = [c for c in cs if c.ts >= t["opened_ts"] and c.ts + step <= now]
        risk = t["entry"] - t["stop"]
        for k, c in enumerate(after):
            if c.low <= t["stop"]:
                t.update(status="loss", result_r=-1.0, closed_ts=c.ts + step)
            elif c.high >= t["target"]:
                t.update(status="win", result_r=round((t["target"] - t["entry"]) / risk, 3), closed_ts=c.ts + step)
            elif k + 1 >= max_bars:
                r = (c.close - t["entry"]) / risk
                t.update(status="win" if r > 0 else "loss", result_r=round(r, 3), closed_ts=c.ts + step)
            if t["status"] != "open":
                closed += 1
                break
    if closed:
        save(trades, path)
    return closed


def stats(path: str = JOURNAL) -> Dict:
    trades = load(path)
    done = [t for t in trades if t["status"] != "open"]
    wins = sum(t["status"] == "win" for t in done)
    return {"open": len(trades) - len(done), "closed": len(done), "wins": wins,
            "win_rate": wins / len(done) if done else None,
            "total_r": round(sum(t["result_r"] or 0 for t in done), 2)}


def stats_line(path: str = JOURNAL) -> str:
    s = stats(path)
    if not s["closed"]:
        return f"📒 سجل النماذج: لسه مفيش صفقات مقفولة (مفتوحة: {s['open']})."
    return (f"📒 سجل النماذج الحقيقي: {s['closed']} مقفولة — ✅ {s['wins']} | ❌ {s['closed'] - s['wins']} "
            f"— نجاح {s['win_rate']:.0%} | {s['total_r']:+.2f}R | مفتوحة: {s['open']}")

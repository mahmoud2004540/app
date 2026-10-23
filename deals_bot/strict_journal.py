"""
سجل صفقات المحلّل المتحفّظ + نسبة النجاح الحقيقية أسبوعيًا + رفع العتبة تلقائيًا.

كل صفقة تُرسَل تُسجَّل، ثم تُقيَّم من الشموع الحقيقية بعد الدخول:
  - لمس الوقف قبل TP1            → خسارة (−1R)
  - لمس TP1 ثم رجع لنقطة الدخول  → تعادل (0R) — الوقف اتنقل للدخول
  - لمس TP2                      → ربح (+RR)
لو شمعة واحدة لمست الوقف والهدف معًا نحسبها ضدّنا (تقدير متحفّظ، بلا تجميل).

نسبة النجاح = الرابحة ÷ كل المقفولة (التعادل محسوب في المقام — تقدير متحفّظ).
لو نسبة أسبوع مقفول < 60% → العتبة 85 للأسبوع التالي، وإلا ترجع 80.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional

JOURNAL = os.path.join("journal", "strict_trades.jsonl")
STATE = os.path.join("journal", "strict_state.json")


@dataclass
class StrictTrade:
    id: str
    symbol: str
    market: str
    timeframe: str
    direction: str
    entry: float
    stop: float
    tp1: float
    tp2: float
    rr: float
    score: int
    opened_ts: float              # زمن قفل شمعة التأكيد (= الدخول)
    status: str = "open"          # open | win | loss | breakeven
    tp1_hit: bool = False
    result_r: Optional[float] = None
    closed_ts: Optional[float] = None


def load(path: str = JOURNAL) -> List[StrictTrade]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(StrictTrade(**json.loads(line)))
            except (json.JSONDecodeError, TypeError):
                continue
    return out


def save(trades: List[StrictTrade], path: str = JOURNAL) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for t in trades:
            f.write(json.dumps(asdict(t), ensure_ascii=False) + "\n")


def has_open(symbol: str, path: str = JOURNAL) -> bool:
    return any(t.symbol == symbol and t.status == "open" for t in load(path))


def record(setup, opened_ts: float, path: str = JOURNAL) -> bool:
    """سجّل صفقة مُرسَلة. يرجّع False لو نفس الإعداد مسجَّل قبل كده."""
    trades = load(path)
    tid = f"{setup.timeframe}:{setup.symbol}:{setup.direction}:{round(setup.candle_ts)}"
    if any(t.id == tid for t in trades):
        return False
    trades.append(StrictTrade(
        id=tid, symbol=setup.symbol, market=setup.market, timeframe=setup.timeframe,
        direction=setup.direction, entry=setup.entry, stop=setup.stop, tp1=setup.tp1,
        tp2=setup.tp2, rr=setup.rr, score=setup.score, opened_ts=opened_ts,
    ))
    save(trades, path)
    return True


def step(t: StrictTrade, high: float, low: float, ts: float) -> None:
    """طبّق شمعة واحدة على صفقة مفتوحة (دالة نقية، تعدّل t في مكانها)."""
    buy = t.direction == "BUY"
    stop = t.entry if t.tp1_hit else t.stop
    hit_stop = low <= stop if buy else high >= stop
    hit_tp1 = high >= t.tp1 if buy else low <= t.tp1
    hit_tp2 = high >= t.tp2 if buy else low <= t.tp2
    if hit_stop:                                  # الوقف أولًا (متحفّظ)
        t.status = "breakeven" if t.tp1_hit else "loss"
        t.result_r = 0.0 if t.tp1_hit else -1.0
        t.closed_ts = ts
        return
    if hit_tp2:
        t.status, t.result_r, t.closed_ts = "win", round(t.rr, 3), ts
        t.tp1_hit = True
        return
    if hit_tp1:
        t.tp1_hit = True


def evaluate_open(fetch_fn: Callable, path: str = JOURNAL) -> int:
    """
    قيّم المفتوحة من الشموع المقفولة بعد الدخول. fetch_fn(symbol, market, tf) -> Series.
    يرجّع عدد الصفقات اللي اتقفلت الآن.
    """
    from .strict import TF_SECONDS

    trades = load(path)
    closed = 0
    now = datetime.now(timezone.utc).timestamp()
    for t in trades:
        if t.status != "open":
            continue
        try:
            series = fetch_fn(t.symbol, t.market, t.timeframe)
        except Exception:  # noqa: BLE001 - نتركها مفتوحة لو الجلب فشل
            continue
        step_s = TF_SECONDS.get(t.timeframe, 3600)
        for c in series.candles:
            if c.ts < t.opened_ts or c.ts + step_s > now:
                continue
            step(t, c.high, c.low, c.ts + step_s)
            if t.status != "open":
                closed += 1
                break
    save(trades, path)
    return closed


def stats(trades: List[StrictTrade], start_ts: float = 0.0, end_ts: float = float("inf")) -> dict:
    done = [t for t in trades if t.status != "open" and t.closed_ts is not None
            and start_ts <= t.closed_ts < end_ts]
    w = sum(t.status == "win" for t in done)
    l = sum(t.status == "loss" for t in done)
    b = sum(t.status == "breakeven" for t in done)
    n = len(done)
    return {"n": n, "wins": w, "losses": l, "breakeven": b,
            "win_rate": (w / n) if n else None,
            "total_r": round(sum(t.result_r or 0.0 for t in done), 2)}


# --------------------------------------------------------------------------- #
# الحالة الأسبوعية والعتبة المتكيّفة
# --------------------------------------------------------------------------- #
def load_state(path: str = STATE) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict, path: str = STATE) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


def _week_start(dt: datetime) -> datetime:
    d = dt.astimezone(timezone.utc)
    return (d - timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def weekly_review(now: datetime, base: int = 80, raised: int = 85, min_wr: float = 0.60,
                  journal_path: str = JOURNAL, state_path: str = STATE) -> Optional[str]:
    """
    مرة واحدة كل أسبوع (أول تشغيل بعد بداية الأسبوع، UTC الإثنين): راجع الأسبوع
    اللي فات، اضبط العتبة، ورجّع نص التقرير. لو الأسبوع اتراجع قبل كده → None.
    """
    state = load_state(state_path)
    this_week = _week_start(now)
    last_week = this_week - timedelta(days=7)
    key = last_week.strftime("%G-W%V")
    if state.get("reviewed_week") == key:
        return None
    trades = load(journal_path)
    wk = stats(trades, last_week.timestamp(), this_week.timestamp())
    allt = stats(trades)
    old = int(state.get("min_score", base))
    if wk["n"] == 0:
        new, note = old, "لا صفقات مقفولة الأسبوع اللي فات — العتبة كما هي."
    elif wk["win_rate"] < min_wr:
        new, note = raised, f"النسبة أقل من {min_wr:.0%} → رفعنا حد الثقة لـ {raised}."
    else:
        new, note = base, f"النسبة {min_wr:.0%} أو أكثر → حد الثقة {base}."
    state.update({"reviewed_week": key, "min_score": new})
    save_state(state, state_path)
    if allt["n"] == 0:
        return None               # لسه مفيش ولا صفقة مقفولة — لا تقرير فاضي

    def line(s):
        if not s["n"]:
            return "لا صفقات مقفولة"
        return (f"{s['n']} صفقة: ✅ {s['wins']} ربح | ❌ {s['losses']} خسارة | "
                f"➖ {s['breakeven']} تعادل — نسبة النجاح {s['win_rate']:.0%} | {s['total_r']:+.2f}R")

    return (
        f"📒 التقرير الأسبوعي للمحلّل المتحفّظ ({key})\n\n"
        f"الأسبوع: {line(wk)}\n"
        f"منذ البداية: {line(allt)}\n\n"
        f"🔒 {note}\n"
        "(نسبة النجاح = الرابحة ÷ كل المقفولة، والتعادل محسوب — أرقام حقيقية من السجل فقط.)"
    )


def current_min_score(base: int = 80, path: str = STATE) -> int:
    return int(load_state(path).get("min_score", base))

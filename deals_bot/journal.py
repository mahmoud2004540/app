"""
سجلّ التداول + حلقة التعلّم (المرحلتان 12 و13 من خط الأنابيب).

Trade Journal & learning loop. Every signal the bot emits is recorded to a
JSONL file; later runs evaluate each open record against real candles (did price
hit the target or the stop first?) and mark it win/loss. From the closed records
we compute the bot's *live* performance — win rate, expectancy in R, profit
factor — and compare it to the backtest so we can see drift and learn.

Persistence: the file lives in the repo and is committed back after each run
(GitHub Actions containers are ephemeral, so the repo is the durable store).

This module is pure/offline-testable: the evaluator takes a `fetch_fn` so tests
can feed synthetic candles with no network.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Callable, List, Optional

DEFAULT_JOURNAL = os.path.join("journal", "trades.jsonl")


@dataclass
class JournalTrade:
    id: str                       # فريد: timeframe:symbol:opened_ts (لمنع التكرار)
    symbol: str
    market: str
    timeframe: str
    entry: float
    stop: float
    target: float
    score: float
    rr: float
    opened_ts: float              # زمن شمعة الإشارة
    recorded_ts: float            # زمن التسجيل
    status: str = "open"          # open | win | loss | expired
    exit: Optional[float] = None
    result_r: Optional[float] = None
    closed_ts: Optional[float] = None
    reason: str = ""


# --------------------------------------------------------------------------- #
# تخزين
# --------------------------------------------------------------------------- #
def load(path: str = DEFAULT_JOURNAL) -> List[JournalTrade]:
    """اقرأ كل الصفقات من الملف (JSONL). ملف غير موجود → قائمة فارغة."""
    if not os.path.exists(path):
        return []
    out: List[JournalTrade] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(JournalTrade(**json.loads(line)))
            except (json.JSONDecodeError, TypeError):
                continue          # تجاهل السطور التالفة بدل الانهيار
    return out


def save(trades: List[JournalTrade], path: str = DEFAULT_JOURNAL) -> None:
    """اكتب كل الصفقات (يعيد كتابة الملف كاملًا)."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for t in trades:
            f.write(json.dumps(asdict(t), ensure_ascii=False) + "\n")


def _trade_id(timeframe: str, symbol: str, opened_ts: float) -> str:
    return f"{timeframe}:{symbol}:{round(opened_ts)}"


# --------------------------------------------------------------------------- #
# المرحلة 12: تسجيل الإشارات
# --------------------------------------------------------------------------- #
def record_signals(deals, timeframe: str, now_ts: float,
                   path: str = DEFAULT_JOURNAL) -> int:
    """
    سجّل كل صفقة مؤكّدة يبعتها البوت (مع منع تكرار نفس الإعداد).

    Returns how many NEW trades were appended (existing ids are skipped so the
    same setup isn't logged again on every run).
    """
    existing = load(path)
    seen = {t.id for t in existing}
    added = 0
    for d in deals:
        opened_ts = float(getattr(d, "opened_ts", now_ts) or now_ts)
        tid = _trade_id(timeframe, d.symbol, opened_ts)
        if tid in seen:
            continue
        existing.append(
            JournalTrade(
                id=tid, symbol=d.symbol, market=d.market, timeframe=timeframe,
                entry=float(d.entry), stop=float(d.stop_loss), target=float(d.take_profit),
                score=float(d.confidence), rr=float(d.risk_reward),
                opened_ts=opened_ts, recorded_ts=float(now_ts),
                reason=(d.reasons[0] if getattr(d, "reasons", None) else ""),
            )
        )
        seen.add(tid)
        added += 1
    if added:
        save(existing, path)
    return added


# --------------------------------------------------------------------------- #
# المرحلة 13 (جزء أ): تقييم النتائج من الشموع الحقيقية
# --------------------------------------------------------------------------- #
def evaluate_open(fetch_fn: Callable, path: str = DEFAULT_JOURNAL,
                  limit: int = 300) -> int:
    """
    قيّم الصفقات المفتوحة: هل لمس السعر الهدف أم الوقف أولًا بعد الدخول؟

    fetch_fn(symbol, market, timeframe, limit) -> Series (يُحقن ليكون قابلًا
    للاختبار offline). يُحدّث الحالة إلى win/loss ويحسب result_r. Returns the
    number of trades newly closed.
    """
    trades = load(path)
    closed = 0
    # نجمع حسب (symbol, market, timeframe) لتقليل عدد الطلبات
    for t in trades:
        if t.status != "open":
            continue
        try:
            series = fetch_fn(t.symbol, t.market, t.timeframe, limit)
        except Exception:  # noqa: BLE001 - لو تعذّر الجلب نتركها مفتوحة
            continue
        candles = getattr(series, "candles", None) or []
        risk = t.entry - t.stop
        if risk <= 0:
            continue
        outcome = None
        for c in candles:
            if c.ts <= t.opened_ts:
                continue                      # فقط الشموع بعد الدخول
            if c.low <= t.stop:               # الأسوأ أولًا (وقف)
                outcome = (t.stop, "loss", c.ts)
                break
            if c.high >= t.target:
                outcome = (t.target, "win", c.ts)
                break
        if outcome:
            exit_price, status, cts = outcome
            t.exit = exit_price
            t.status = status
            t.result_r = round((exit_price - t.entry) / risk, 3)
            t.closed_ts = cts
            closed += 1
    if closed:
        save(trades, path)
    return closed


# --------------------------------------------------------------------------- #
# المرحلة 13 (جزء ب): إحصاءات الأداء الحيّ + التعلّم
# --------------------------------------------------------------------------- #
def summary(path: str = DEFAULT_JOURNAL) -> dict:
    """احسب أداء البوت الفعلي من الصفقات المغلقة."""
    trades = load(path)
    closed = [t for t in trades if t.status in ("win", "loss")]
    open_n = sum(1 for t in trades if t.status == "open")
    n = len(closed)
    wins = sum(1 for t in closed if t.status == "win")
    total_r = sum((t.result_r or 0.0) for t in closed)
    gross_win = sum((t.result_r or 0.0) for t in closed if (t.result_r or 0) > 0)
    gross_loss = -sum((t.result_r or 0.0) for t in closed if (t.result_r or 0) < 0)
    return {
        "total": len(trades),
        "open": open_n,
        "closed": n,
        "wins": wins,
        "losses": n - wins,
        "win_rate": (wins / n * 100.0) if n else 0.0,
        "expectancy_r": (total_r / n) if n else 0.0,
        "total_r": total_r,
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else (
            float("inf") if gross_win > 0 else 0.0
        ),
    }


def learning_note(path: str = DEFAULT_JOURNAL, backtest_expectancy: float = 0.38) -> str:
    """
    حلقة التعلّم: قارن الأداء الحيّ بالباك-تِست واستخلص ملاحظة.

    Not blind auto-tuning (that overfits tiny samples). Instead an honest signal:
    is the live edge tracking the backtested +0.38R, or drifting? Below ~20 closed
    trades we say the sample is still too small to judge.
    """
    s = summary(path)
    if s["closed"] < 20:
        return (
            f"📓 سجل التداول: {s['closed']} صفقة مغلقة، {s['open']} مفتوحة. "
            "العيّنة صغيرة لسه — نحتاج ≥20 صفقة مغلقة للحكم على الأداء الحيّ."
        )
    live = s["expectancy_r"]
    head = (
        f"📓 الأداء الحيّ: {s['closed']} صفقة | نجاح {s['win_rate']:.0f}% | "
        f"توقّع {live:+.2f}R | إجمالي {s['total_r']:+.1f}R"
    )
    if live >= backtest_expectancy * 0.6:
        verdict = "✅ الأداء الحيّ يواكب الباك-تِست — الأفضلية صامدة."
    elif live > 0:
        verdict = "⚠️ الأداء الحيّ موجب لكنه أضعف من الباك-تِست — راقب الانحراف."
    else:
        verdict = (
            "🛑 الأداء الحيّ سالب — الأفضلية لا تتحقق فعليًا. يُنصح برفع عتبة الدرجة "
            "أو تشديد الفلاتر (إعادة تحسين) قبل الاستمرار."
        )
    return head + "\n" + verdict

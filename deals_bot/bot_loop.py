"""
حلقة البوت الورقية (Paper Trading Bot Loop) — PHASE 2.

One cycle of the live loop, wired to the decision pipeline + risk engine + paper
execution. It is deliberately a single pure function taking injected fetchers so
it runs offline in tests and on a schedule in CI (no infinite CPU loop).

Each cycle:
  1) Monitor open paper positions → close any that hit stop/target.
  2) Rebuild daily-safety state from the account (daily loss, consecutive losses).
  3) Evaluate fresh candidates through the pipeline → open APPROVED ones as paper
     trades (respecting max open positions + daily safety).

Live money is never touched — this drives the Paper Trading engine only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from . import paper_trading as pt
from .models import Series
from .pipeline import APPROVED, evaluate
from .risk_engine import DailyState, RiskEngine


@dataclass
class CycleEvent:
    kind: str            # "open" | "close"
    symbol: str
    detail: str


def _daily_state(acc: pt.PaperAccount, engine: RiskEngine) -> DailyState:
    return DailyState(
        starting_equity=acc.day_start_equity or acc.starting_equity,
        current_equity=acc.equity,
        trades_today=len(acc.closed),
        consecutive_losses=pt.trailing_consecutive_losses(acc),
        open_positions=len(acc.positions),
    )


def run_cycle(
    account: pt.PaperAccount,
    symbols: List[str],
    fetch_base: Callable,       # (symbol, market, timeframe, limit) -> Series (1H)
    now_ts: float,
    engine: RiskEngine,
    fetch_confirm: Optional[Callable] = None,   # (symbol, market, timeframe, limit) -> Series (15M)
    market: str = "crypto",
    base_tf: str = "1h",
    confirm_tf: str = "15m",
    fee_rate: float = 0.001,
    slippage_rate: float = 0.0005,
) -> List[CycleEvent]:
    """شغّل دورة واحدة: راقب المفتوحة، ثم افتح المعتمدة الجديدة. يُرجع الأحداث."""
    events: List[CycleEvent] = []
    pt.roll_day(account, now_ts)

    # 1) مراقبة الصفقات المفتوحة → إغلاق ما لمس الوقف/الهدف
    for pos in list(account.positions):
        try:
            series = fetch_base(pos.symbol, pos.market, base_tf, 3)
        except Exception:  # noqa: BLE001
            continue
        if not series.candles:
            continue
        last = series.candles[-1]
        ex = pt.check_exit(pos, last.high, last.low)
        if ex:
            exit_price, reason = ex
            trade = pt.close_position(account, pos, exit_price, reason, last.ts,
                                      fee_rate=fee_rate, slippage_rate=slippage_rate)
            events.append(CycleEvent(
                "close", pos.symbol,
                f"{'🎯 هدف' if reason == 'target' else '🛑 وقف'} | "
                f"{trade.result_r:+.2f}R | رصيد {account.equity:.2f}",
            ))

    # 2) بوّابة الأمان اليومية (بعد الإغلاقات)
    open_symbols = {p.symbol for p in account.positions}
    daily = _daily_state(account, engine)
    if not engine.can_open_new_trade(daily).approved:
        return events            # موقوف اليوم — لا نفتح جديدًا

    # 3) تقييم مرشّحين جدد وفتح المعتمد منهم
    for sym in symbols:
        if len(account.positions) >= engine.cfg.max_open_positions:
            break
        if sym in open_symbols:
            continue
        try:
            base = fetch_base(sym, market, base_tf, 300)
        except Exception:  # noqa: BLE001
            continue
        conf_series = None
        if fetch_confirm is not None:
            try:
                conf_series = fetch_confirm(sym, market, confirm_tf, 60)
            except Exception:  # noqa: BLE001
                conf_series = None

        dec = evaluate(base, account.equity, daily, conf_series, engine)
        if dec.status != APPROVED:
            continue
        opened_ts = base.candles[-1].ts if base.candles else now_ts
        pt.open_position(
            account, sym, market, dec.direction, dec.entry, dec.stop, dec.target,
            dec.qty, opened_ts, fee_rate=fee_rate, slippage_rate=slippage_rate,
            ai_score=dec.ai_score,
        )
        open_symbols.add(sym)
        daily.open_positions = len(account.positions)
        events.append(CycleEvent(
            "open", sym,
            f"دخول {dec.entry:.6g} | وقف {dec.stop:.6g} | هدف {dec.target:.6g} | "
            f"AI {dec.ai_score:.0f} | {dec.qty:g} وحدة",
        ))
    return events

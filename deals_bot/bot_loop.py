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

from . import indicators as ind
from . import paper_trading as pt
from .analyzer import TF_HOURS, estimate_eta_hours
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
    market_bullish: Optional[bool] = None,
) -> List[CycleEvent]:
    """شغّل دورة واحدة: راقب المفتوحة، ثم افتح المعتمدة الجديدة. يُرجع الأحداث."""
    events: List[CycleEvent] = []
    pt.roll_day(account, now_ts)

    # 1) مراقبة الصفقات المفتوحة → إغلاق ما لمس الوقف/الهدف
    open_closes = {}          # نخزّن إغلاقات المفتوحة (لفلتر الارتباط)
    for pos in list(account.positions):
        try:
            series = fetch_base(pos.symbol, pos.market, base_tf, 60)
        except Exception:  # noqa: BLE001
            continue
        if not series.candles:
            continue
        open_closes[pos.symbol] = series.closes()
        last = series.candles[-1]
        # وقف متحرّك: مشّي الوقف خلف القمة بعد +ACTIVATE_R (مُثبت: يضاعف التوقّع).
        import config as _cfg
        pt.apply_trailing(
            pos, last.high, last.low,
            getattr(_cfg, "TREND_TRAIL_ACTIVATE_R", 0.0),
            getattr(_cfg, "TREND_TRAIL_ATR", 0.0),
        )
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

        try:
            dec = evaluate(base, account.equity, daily, conf_series, engine,
                           market_bullish=market_bullish)
        except Exception:  # noqa: BLE001 - عملة واحدة تالفة يجب ألا تُسقط الدورة كلها
            continue
        if dec.status != APPROVED:
            continue

        # حدّ مخاطرة المحفظة: لا نتجاوز إجمالي المخاطرة المسموح عبر كل المفتوح
        heat_after = (len(account.positions) + 1) * engine.cfg.risk_per_trade
        if heat_after > engine.cfg.max_portfolio_heat + 1e-9:
            print(f"  🛡️ {sym}: تجاوز حدّ مخاطرة المحفظة "
                  f"({heat_after*100:.1f}% > {engine.cfg.max_portfolio_heat*100:.0f}%) — تخطٍّ.")
            break

        # فلتر الارتباط: لا نفتح عملة مرتبطة بشدة بصفقة مفتوحة (رهان مكرّر)
        too_correlated = False
        for osym, ocloses in open_closes.items():
            corr = ind.returns_correlation(base.closes(), ocloses, 50)
            if corr is not None and corr >= engine.cfg.max_correlation:
                print(f"  🔗 {sym}: مرتبطة بـ{osym} (ارتباط {corr:.2f}) — تخطٍّ (رهان مكرّر).")
                too_correlated = True
                break
        if too_correlated:
            continue

        opened_ts = base.candles[-1].ts if base.candles else now_ts
        # ATR عند الدخول — يُخزّن للوقف المتحرّك (trailing)
        atr_v = ind.atr(base.highs(), base.lows(), base.closes(), 14)
        pt.open_position(
            account, sym, market, dec.direction, dec.entry, dec.stop, dec.target,
            dec.qty, opened_ts, fee_rate=fee_rate, slippage_rate=slippage_rate,
            ai_score=dec.ai_score, atr0=atr_v or 0.0,
        )
        open_symbols.add(sym)
        open_closes[sym] = base.closes()      # يُحسب ضمن الارتباط للمرشّح التالي
        daily.open_positions = len(account.positions)
        # الزمن المتوقّع للهدف (تقديري من ATR الإطار الأساسي)
        eta = estimate_eta_hours(dec.entry, dec.target, atr_v,
                                 tf_hours=TF_HOURS.get(base_tf, 1.0))
        eta_txt = f" | ⏱️ متوقّع ~{eta:g}h" if eta else ""
        events.append(CycleEvent(
            "open", sym,
            f"دخول {dec.entry:.6g} | وقف {dec.stop:.6g} | هدف {dec.target:.6g} | "
            f"AI {dec.ai_score:.0f} | {dec.qty:g} وحدة{eta_txt}",
        ))
    return events

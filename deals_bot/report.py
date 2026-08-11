"""
تقرير الأداء النصّي لتيليجرام (Telegram Performance Report) — PHASE 4.

Same content as the HTML dashboard, formatted as a compact Telegram message:
account, performance, the proven backtest edge, risk-engine config, open
positions and recent signals. Pure/offline-testable — takes computed metrics.
"""

from __future__ import annotations

from typing import List

PROVEN = {"in_sample_r": 0.38, "in_sample_wr": 46, "oos_r": 0.19, "oos_trades": 108}


def _pf(v) -> str:
    return "∞" if v == float("inf") else f"{v:.2f}"


def build_report(account, m: dict, recent: List, risk: dict) -> str:
    ret = m["return_pct"]
    ret_emoji = "🟢" if ret > 0 else ("🔴" if ret < 0 else "⚪")
    exp = m["expectancy_r"]
    exp_emoji = "🟢" if exp > 0 else ("🔴" if exp < 0 else "⚪")

    lines = [
        "📊 لوحة أداء بوت التداول",
        "🟢 الحالة: يعمل (تداول ورقي)  |  🔒 التداول الحقيقي: مُعطَّل",
        "",
        "💰 الحساب",
        f"   رأس المال: {m['equity']:,.2f}  (بدأ من {m['starting_equity']:,.0f})",
        f"   {ret_emoji} العائد: {ret:+.2f}%",
        f"   صافي الربح/الخسارة: {m['net_pnl']:+,.2f}  ({m['total_r']:+.1f}R)",
        "",
        "📈 الأداء",
        f"   {exp_emoji} التوقّع/صفقة: {exp:+.2f}R",
        f"   نسبة النجاح: {m['win_rate']:.0f}%  ({m['wins']}/{m['closed']})",
        f"   عامل الربح: {_pf(m['profit_factor'])}",
        f"   أقصى تراجع: {m['max_drawdown_pct']:.1f}%",
        f"   صفقات مفتوحة: {m['open_positions']} (حدّ أقصى {risk['max_open']})",
        "",
        "🏆 الأفضلية المُثبتة (باك-تِست حقيقي)",
        f"   داخل العيّنة: +{PROVEN['in_sample_r']:.2f}R (نجاح {PROVEN['in_sample_wr']}%)",
        f"   خارج العيّنة (Walk-Forward): +{PROVEN['oos_r']:.2f}R ({PROVEN['oos_trades']} صفقة)",
        "",
        "🛡️ محرّك المخاطر",
        f"   {risk['risk_pct']:.1f}%/صفقة | {risk['daily']:.1f}% يومي | "
        f"إيقاف بعد {risk['consec']} خسائر | RR 1:{risk['rr']:.0f}",
    ]

    lines.append("")
    lines.append("📌 الصفقات المفتوحة")
    if account.positions:
        for p in account.positions:
            lines.append(
                f"   • {p.symbol}: دخول {p.entry:.6g} | وقف {p.stop:.6g} | "
                f"هدف {p.target:.6g} | AI {p.ai_score:.0f}"
            )
    else:
        lines.append("   — لا صفقات مفتوحة الآن —")

    lines.append("")
    lines.append("🕒 آخر الإشارات المسجّلة")
    if recent:
        label = {"win": "✅ ربح", "loss": "🔴 خسارة", "open": "⏳ مفتوحة",
                 "expired": "⚪ منتهية"}
        for t in recent[:6]:
            r = f"{t.result_r:+.2f}R" if t.result_r is not None else ""
            lines.append(f"   • {t.symbol} (درجة {t.score:.0f}) "
                         f"{label.get(t.status, t.status)} {r}".rstrip())
    else:
        lines.append("   — لا إشارات مسجّلة بعد (البوت ينتظر إعدادًا مؤكّدًا) —")

    lines.append("")
    lines.append("⚠️ تحليل آلي تعليمي — ليس نصيحة مالية. لا صفقة ناجحة 100%.")
    return "\n".join(lines)

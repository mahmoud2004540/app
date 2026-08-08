"""
تنسيق الصفقات لعرضها في سطر الأوامر أو تيليجرام.

Render Deal objects into human-readable text for the CLI and Telegram bot.
"""

from __future__ import annotations

from typing import List

from .models import Deal

_ARROW = {"BUY": "🟢 شراء", "SELL": "🔴 بيع", "NEUTRAL": "⚪ حياد"}

DISCLAIMER = (
    "⚠️ تنبيه: هذا تحليل فني آلي لأغراض تعليمية فقط وليس نصيحة مالية. "
    "التداول ينطوي على مخاطر — تحقّق بنفسك ولا تخاطر بأكثر مما تتحمّل خسارته."
)


def _fmt_price(x: float) -> str:
    if x == 0:
        return "0"
    if abs(x) >= 100:
        return f"{x:,.2f}"
    if abs(x) >= 1:
        return f"{x:,.4f}"
    return f"{x:.6f}"


def format_deal(deal: Deal, index: int | None = None) -> str:
    """صفقة واحدة كنص متعدد الأسطر."""
    head = f"{_ARROW.get(deal.direction, deal.direction)}  {deal.symbol}"
    if index is not None:
        head = f"{index}. {head}"

    lines = [
        head,
        f"   السوق: {deal.market}  |  الثقة: {deal.confidence:.0f}/100  |  الدرجة: {deal.score:+.0f}",
        f"   السعر الحالي: {_fmt_price(deal.price)}",
    ]
    if deal.is_actionable():
        lines.append(
            f"   الدخول: {_fmt_price(deal.entry)}  |  "
            f"وقف الخسارة: {_fmt_price(deal.stop_loss)}  |  "
            f"الهدف: {_fmt_price(deal.take_profit)}"
        )
        lines.append(f"   نسبة المخاطرة/العائد: 1:{deal.risk_reward:.1f}")

    ind = deal.indicators
    if ind:
        lines.append(
            "   المؤشرات: "
            f"RSI={ind.get('rsi')}  "
            f"MACD_hist={ind.get('macd_hist')}  "
            f"زخم={ind.get('momentum_pct')}%  "
            f"حجم=×{ind.get('volume_surge')}"
        )
    if deal.reasons:
        lines.append("   الأسباب:")
        for r in deal.reasons:
            lines.append(f"     • {r}")
    if deal.error:
        lines.append(f"   ⚠️ {deal.error}")
    return "\n".join(lines)


def format_deals(deals: List[Deal], title: str = "أفضل الصفقات") -> str:
    """قائمة صفقات كاملة مع عنوان وتنبيه."""
    if not deals:
        return (
            f"— {title} —\n"
            "لا توجد صفقات واضحة الآن حسب المعايير الحالية. "
            "جرّب إطارًا زمنيًا مختلفًا أو وسّع قائمة المتابعة.\n\n" + DISCLAIMER
        )
    parts = [f"— {title} —", ""]
    for i, d in enumerate(deals, 1):
        parts.append(format_deal(d, index=i))
        parts.append("")
    parts.append(DISCLAIMER)
    return "\n".join(parts)

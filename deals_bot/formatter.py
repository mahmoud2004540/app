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
    whale = "🐋 " if deal.whale else ""
    head = f"{whale}{_ARROW.get(deal.direction, deal.direction)}  {deal.symbol}"
    if index is not None:
        head = f"{index}. {head}"

    lines = [
        head,
        f"   السوق: {deal.market}  |  الثقة: {deal.confidence:.0f}/100  |  الدرجة: {deal.score:+.0f}",
        f"   السعر الحالي: {_fmt_price(deal.price)}",
    ]
    if deal.confirmed is True:
        lines[1] += "  |  ✅ مؤكّد"
    elif deal.confirmed is False:
        lines[1] += "  |  ⚠️ غير مؤكّد"
    if deal.is_actionable():
        lines.append(
            f"   الدخول: {_fmt_price(deal.entry)}  |  "
            f"وقف الخسارة: {_fmt_price(deal.stop_loss)}  |  "
            f"الهدف: {_fmt_price(deal.take_profit)}"
        )
        lines.append(f"   نسبة المخاطرة/العائد: 1:{deal.risk_reward:.1f}")
        if deal.qty is not None:
            lines.append(
                f"   حجم الصفقة المقترح: {deal.qty:g} وحدة "
                f"(مخاطرة {deal.risk_amount:g})"
            )

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


def format_digest(deals: List[Deal], title: str = "أفضل الصفقات") -> str:
    """
    نسخة مختصرة مناسبة لرسائل تيليجرام (سطور قليلة لكل صفقة).

    Compact rendering for scheduled Telegram pushes — keeps each deal short so
    the whole digest fits comfortably in one message.
    """
    if not deals:
        return (
            f"📭 {title}\n"
            "لا توجد صفقات واضحة الآن حسب المعايير الحالية.\n\n" + DISCLAIMER
        )
    parts = [f"📊 {title}", ""]
    for i, d in enumerate(deals, 1):
        badge = " ✅" if d.confirmed is True else ""
        whale = "🐋 " if d.whale else ""
        head = f"{i}. {whale}{_ARROW.get(d.direction, d.direction)} {d.symbol}  ({d.market}){badge}"
        parts.append(head)
        parts.append(
            f"   الثقة {d.confidence:.0f}/100 | السعر {_fmt_price(d.price)}"
        )
        if d.is_actionable():
            parts.append(
                f"   دخول {_fmt_price(d.entry)} | وقف {_fmt_price(d.stop_loss)} | "
                f"هدف {_fmt_price(d.take_profit)} | R:R 1:{d.risk_reward:.1f}"
            )
            if d.qty is not None:
                parts.append(f"   حجم مقترح: {d.qty:g} وحدة (مخاطرة {d.risk_amount:g})")
        if d.reasons:
            parts.append(f"   • {d.reasons[0]}")
        parts.append("")
    parts.append(DISCLAIMER)
    return "\n".join(parts)


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

"""
تنسيق الصفقات لعرضها في سطر الأوامر أو تيليجرام.

Render Deal objects into human-readable text for the CLI and Telegram bot.
"""

from __future__ import annotations

from typing import List

import config

from .models import Deal

_ARROW = {"BUY": "🟢 شراء", "SELL": "🔴 بيع", "NEUTRAL": "⚪ حياد"}

DISCLAIMER = (
    "⚠️ تنبيه: هذا تحليل فني آلي لأغراض تعليمية فقط وليس نصيحة مالية. "
    "«الثقة» = مدى توافق كل المؤشرات + الحيتان (قوة الإشارة)، وليست ضمان ربح — "
    "لا توجد صفقة ناجحة 100%. التداول ينطوي على مخاطر؛ استخدم وقف الخسارة دائمًا "
    "ولا تخاطر بأكثر مما تتحمّل خسارته."
)


def grade(deal: Deal) -> str:
    """
    تقييم يجمع كل المؤشرات + الحيتان + التأكيد في وصف واحد واضح.

    A single label summarising how strongly ALL signals (indicators + money flow
    + whale + higher-timeframe confirmation) agree. Higher = stronger setup —
    strength of confluence, NOT a probability of profit.
    """
    c = deal.confidence
    if deal.whale and deal.confirmed is True and c >= 85:
        return "⭐ توافق كامل — حيتان + كل المؤشرات + تأكيد إطار أعلى"
    if c >= 90:
        return "A+ إشارة قوية جدًا (توافق شبه كامل)"
    if c >= 78:
        return "A إشارة قوية"
    if c >= 68:
        return "B إشارة جيدة"
    return "C إشارة متوسطة"


def _fmt_price(x: float) -> str:
    if x == 0:
        return "0"
    ax = abs(x)
    if ax >= 100:
        return f"{x:,.2f}"
    if ax >= 1:
        return f"{x:,.4f}"
    if ax >= 0.001:
        return f"{x:.6f}"
    # عملات متناهية الصغر (ميم كوينز): أظهر أرقامًا معنوية كافية بدل أصفار
    return f"{x:.10f}".rstrip("0").rstrip(".")


def _fmt_eta(hours: float) -> str:
    """صيغة الزمن المتوقّع: ساعات أو أيام حسب الحجم."""
    if hours < 1:
        return f"{int(round(hours * 60))} دقيقة"
    if hours < 10:
        return f"{hours:.1f} ساعة"
    if hours < 24:
        return f"{hours:.0f} ساعة"
    days = hours / 24.0
    return f"{days:.1f} يوم"


_TF_LABEL = {
    "15m": "⏱️ فريم 15 دقيقة (مضاربة سريعة)",
    "30m": "⏱️ فريم 30 دقيقة (مضاربة سريعة)",
    "1h": "🕐 فريم ساعة (صفقة خلال اليوم)",
    "4h": "🕓 فريم 4 ساعات (صفقة يوم–يومين)",
    "6h": "🕕 فريم 6 ساعات (صفقة عدّة أيام)",
    "1d": "📆 فريم يومي (صفقة أسبوع أو أكثر)",
}


def _tf_label(tf: str) -> str:
    """وصف مفهوم للإطار الزمني الذي وُلِّدت منه الإشارة."""
    return _TF_LABEL.get(tf, f"إطار {tf}")


def _trade_horizon(hours: float) -> str:
    """صنّف مدة الصفقة المتوقّعة (من الزمن المقدّر للهدف) بوصف مفهوم."""
    if hours < 8:
        return "⚡ صفقة سريعة (خلال ساعات)"
    if hours < 48:
        return "📅 استثمار قصير (يوم – يومين)"
    return "🕰️ استثمار أطول (عدّة أيام)"


def expected_moves(deal: Deal):
    """
    الحركة المتوقّعة بالنسبة المئوية حتى الهدف وحتى وقف الخسارة.

    Returns (target_pct, stop_pct) as positive magnitudes: how much price is
    projected to move to reach the take-profit (the "pump" target) and to the
    stop-loss. Derived from ATR-based levels — an estimate from volatility, not
    a promise. Returns (0.0, 0.0) if not actionable.
    """
    if not deal.is_actionable() or deal.entry == 0:
        return 0.0, 0.0
    target_pct = abs(deal.take_profit - deal.entry) / deal.entry * 100.0
    stop_pct = abs(deal.stop_loss - deal.entry) / deal.entry * 100.0
    return target_pct, stop_pct


def format_deal(deal: Deal, index: int | None = None) -> str:
    """صفقة واحدة كنص متعدد الأسطر."""
    tags = ("🚀 " if deal.pump else "") + ("🐋 " if deal.whale else "")
    head = f"{tags}{_ARROW.get(deal.direction, deal.direction)}  {deal.symbol}"
    if index is not None:
        head = f"{index}. {head}"

    lines = [
        head,
        f"   التقييم: {grade(deal)}",
        f"   السوق: {deal.market}  |  الثقة: {deal.confidence:.0f}/100  |  الدرجة: {deal.score:+.0f}",
        f"   السعر الحالي: {_fmt_price(deal.price)}",
    ]
    if deal.confirmed is True:
        lines[2] += "  |  ✅ مؤكّد"
    elif deal.confirmed is False:
        lines[2] += "  |  ⚠️ غير مؤكّد"
    if deal.is_actionable():
        lines.append(
            f"   الدخول: {_fmt_price(deal.entry)}  |  "
            f"وقف الخسارة: {_fmt_price(deal.stop_loss)}  |  "
            f"الهدف: {_fmt_price(deal.take_profit)}"
        )
        tgt, stp = expected_moves(deal)
        verb = "صعود" if deal.direction == "BUY" else "هبوط"
        lines.append(
            f"   الحركة المتوقّعة: {verb} ~+{tgt:.1f}% حتى الهدف  |  "
            f"−{stp:.1f}% عند وقف الخسارة"
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


_DIR_AR = {"bull": "🟢 صاعد", "bear": "🔴 هابط", "neutral": "⚪ حياد", "n/a": "➖ غير متوفّر"}


def _fmt_vol(v: float) -> str:
    if v >= 1e9:
        return f"{v/1e9:.2f}B"
    if v >= 1e6:
        return f"{v/1e6:.1f}M"
    if v >= 1e3:
        return f"{v/1e3:.0f}K"
    return f"{v:.0f}"


def format_gainers(gainers, title: str = "🔥 الأكثر ارتفاعًا الآن (24س)") -> str:
    """قائمة أكبر الرابحين مع تحذير صريح من ملاحقة القمة."""
    if not gainers:
        return f"— {title} —\nتعذّر جلب قائمة الرابحين الآن.\n\n" + DISCLAIMER
    parts = [title, ""]
    for i, g in enumerate(gainers, 1):
        chg = g["change_24h"]
        # تحذير من الملاحقة كلما زاد الارتفاع
        if chg >= 50:
            risk = "⛔ متأخر جدًا — ملاحقة قمة (خطر عالٍ)"
        elif chg >= 20:
            risk = "⚠️ ارتفاع كبير — احذر الدخول المتأخر"
        else:
            risk = "🟢 ارتفاع مبكّر نسبيًا"
        parts.append(f"{i}. {g['symbol']}  +{chg:.1f}%  ({g['name']})")
        parts.append(
            f"   السعر {_fmt_price(g['price'])} | حجم 24س {_fmt_vol(g['volume'])} | {risk}"
        )
        parts.append("")
    parts.append(
        "ℹ️ هذه عملات ارتفعت بالفعل — الدخول الآمن يكون مبكّرًا عبر قسمَي «بداية "
        "اندفاع» و«التجميع»، لا بمطاردة عملة تشبّعت (RSI مرتفع)."
    )
    parts.append("")
    parts.append(DISCLAIMER)
    return "\n".join(parts)


def format_trending(coins, title: str = "✨ عملات رائجة الآن (Trending)") -> str:
    """قائمة العملات الرائجة/الجديدة الأكثر اهتمامًا الآن."""
    if not coins:
        return f"— {title} —\nتعذّر جلب العملات الرائجة الآن.\n\n" + DISCLAIMER
    parts = [title, ""]
    for i, c in enumerate(coins, 1):
        chg = c.get("change_24h")
        chg_s = f"  ({chg:+.1f}% 24س)" if chg is not None else ""
        rank = f"  #ترتيب {c['rank']}" if c.get("rank") else ""
        parts.append(f"{i}. {c['symbol']} — {c['name']}{chg_s}{rank}")
    parts.append("")
    parts.append(
        "ℹ️ «رائجة» = الأكثر بحثًا/اهتمامًا الآن (غالبًا جديدة أو مُهيّجة). ابحث عن "
        "سبب الحركة قبل الدخول، ولا تطارد عملة تشبّعت — استخدم قسمَي «بداية اندفاع» "
        "و«التجميع» للدخول المبكّر بوقف خسارة."
    )
    parts.append("")
    parts.append(DISCLAIMER)
    return "\n".join(parts)


def format_confluence(rep) -> str:
    """صياغة تقرير تقاطع الأدلة بالشكل المؤسسي المطلوب."""
    lines = []
    lines.append(f"📋 الأصل / الإطار الزمني: {rep.symbol} ({rep.market}) — {rep.timeframe}")
    lines.append(f"السعر الحالي: {_fmt_price(rep.price)}")
    lines.append("")
    lines.append("ملخص المدارس:")
    for s in rep.schools:
        mark = _DIR_AR.get(s.direction, s.direction)
        note = f" — {s.note}" if s.note else ""
        avail = "" if s.available else "  (بيانات غير متوفّرة)"
        lines.append(f"   • {s.name}: {mark}{note}{avail}")
    lines.append("")
    lines.append(
        f"المدارس المتفقة: صعود {rep.agree_bull} / هبوط {rep.agree_bear} "
        f"(من {rep.available_count} متاحة)"
    )
    lines.append(f"القرار: {rep.decision}")

    if rep.decision in ("شراء", "بيع"):
        tgts = " ، ".join(_fmt_price(t) for t in rep.targets)
        lines.append(
            f"الدخول: {_fmt_price(rep.entry)} | وقف الخسارة: {_fmt_price(rep.stop_loss)} | "
            f"الأهداف: {tgts}"
        )
        lines.append(f"نسبة المخاطرة/العائد (الهدف الأول): 1:{rep.risk_reward:.1f}")
        lines.append(f"حجم المركز المقترح: {rep.position_pct:g}% من المحفظة")
    lines.append(
        f"مستوى الثقة: {rep.confidence} (عدد أدلة التأكيد: {rep.evidence_count})"
    )
    if rep.alternative:
        lines.append(f"سيناريو بديل: {rep.alternative}")
    if rep.notes:
        lines.append("ملاحظات المخاطر:")
        for nt in rep.notes:
            lines.append(f"   ⚠️ {nt}")
    lines.append("")
    lines.append(DISCLAIMER)
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
        tags = ("🚀 " if d.pump else "") + ("🐋 " if d.whale else "")
        if d.trend:
            label = "📈 اتجاه صاعد (ارتداد)"
        elif d.accumulation:
            label = "📥 تجميع"
        elif d.early_pump:
            label = "بداية اندفاع"
        else:
            label = _ARROW.get(d.direction, d.direction)
        head = f"{i}. {tags}{label} {d.symbol}  ({d.market}){badge}"
        parts.append(head)
        parts.append(f"   التقييم: {grade(d)}")
        parts.append(
            f"   الثقة {d.confidence:.0f}/100 | السعر {_fmt_price(d.price)}"
        )
        if d.is_actionable():
            tgt, stp = expected_moves(d)
            parts.append(f"   🎯 متوقّع ~+{tgt:.1f}% للهدف | −{stp:.1f}% للوقف")
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


def _pick_body(d: Deal) -> List[str]:
    """أسطر تفاصيل صفقة واحدة (دخول/وقف/هدف/حجم/سبب)."""
    tgt, stp = expected_moves(d)
    lines = []
    if getattr(d, "timeframe", None):
        lines.append(f"   {_tf_label(d.timeframe)}")
    lines += [
        f"   💵 السعر الآن: {_fmt_price(d.price)}",
        f"   🟢 الدخول: {_fmt_price(d.entry)}",
        f"   🛑 وقف الخسارة: {_fmt_price(d.stop_loss)}  (−{stp:.1f}%)",
        f"   🎯 الهدف السريع: {_fmt_price(d.take_profit)}  (+{tgt:.1f}%)",
    ]
    # هدف استثمار أكبر (فترة أطول) — نفس الدخول/الوقف، هدف أبعد بنسبة أعلى.
    # مقاس: RR أكبر يدّي ربحًا أعلى (+0.93R عند 3.5). تختار: تقفل بدري أو تسيبها تكمّل.
    inv_rr = getattr(config, "INVESTMENT_RR", 0.0)
    if inv_rr and inv_rr > d.risk_reward and d.entry > 0:
        risk = abs(d.entry - d.stop_loss)
        inv_target = d.entry + inv_rr * risk if d.direction == "BUY" else d.entry - inv_rr * risk
        inv_pct = abs(inv_target - d.entry) / d.entry * 100.0
        lines.append(
            f"   📈 هدف استثمار (فترة أطول): {_fmt_price(inv_target)}  "
            f"(+{inv_pct:.1f}% | RR {inv_rr:g})")
    lines.append(
        f"   ⚖️ مخاطرة/عائد 1:{d.risk_reward:.1f}  |  الثقة {d.confidence:.0f}%")
    eta = getattr(d, "eta_hours", None)
    if eta:
        lines.append(f"   ⏱️ الزمن المتوقّع للهدف: ~{_fmt_eta(eta)} (تقديري لا مضمون)")
        lines.append(f"   🗓️ نوع الصفقة: {_trade_horizon(eta)}")
    if d.qty is not None:
        lines.append(f"   📦 حجم مقترح: {d.qty:g} وحدة (تخاطر بـ {d.risk_amount:g})")
    # إدارة: وقف متحرّك (مُثبت بالقياس: يضاعف التوقّع +0.21R→+0.51R).
    act_r = getattr(config, "TREND_TRAIL_ACTIVATE_R", 0.0)
    tr_atr = getattr(config, "TREND_TRAIL_ATR", 0.0)
    if act_r and tr_atr and d.direction == "BUY" and d.entry > 0:
        risk = abs(d.entry - d.stop_loss)
        act_price = d.entry + act_r * risk
        lines.append(
            f"   🔒 إدارة: بعد ما توصل +{act_r:g}R ({_fmt_price(act_price)}) — "
            f"مشّي وقف الخسارة خلف أعلى سعر بمسافة {tr_atr:g}×ATR (يسيبها تجري وتمسك "
            "الحركة الكبيرة بدل هدف ثابت).")
    if d.reasons:
        lines.append(f"   • {d.reasons[0]}")
    return lines


def format_picks(picks: List[Deal]) -> str:
    """
    صياغة «هي دي» — تنادي على العملة باسمها بوضوح في الأعلى.

    Loud, unambiguous call-out: names the coin first ("👈 هي دي: SYMBOL"),
    then the entry / stop / target so the user knows exactly what to do.
    """
    parts: List[str] = []
    for i, d in enumerate(picks, 1):
        num = f" رقم {i}" if len(picks) > 1 else ""
        tag = " 🆕" if getattr(d, "_is_new", False) else " 🔁"
        parts.append(f"🎯👈 هي دي الصفقة{num}: {d.symbol}{tag}")
        parts.append(f"   📈 اتجاه صاعد (ارتداد للمتوسّط) — {grade(d)}")
        parts.append(f"   🎯 الثقة: {d.confidence:.0f}%  ({d.confidence:.0f}/100)")
        if d.confirmed is True:
            parts.append("   ✅ مؤكّدة على 30M (انغلاف + حجم + كسر بنية)")
        elif d.confirmed is False:
            # في الوضع الفوري (لا نشترط التأكيد) لا نقول «راقبها قبل الدخول» — ده
            # يناقض «قابلة للدخول الآن». الإشارة مكتملة على فريمها والتأكيد اختياري.
            if getattr(config, "ALERT_REQUIRE_CONFIRM", True):
                parts.append("   ⏳ بانتظار تأكيد 30M — راقبها قبل الدخول")
            else:
                parts.append("   ☑️ إشارة الفريم مكتملة — ادخل عند السعر ده "
                             "(تأكيد 30M اختياري لزيادة الثقة)")
        sent = getattr(d, "_sentiment", None)
        if sent:
            parts.append(f"   📰 مشاعر الأخبار: {sent}")
        parts.extend(_pick_body(d))
        parts.append("")
    parts.append(DISCLAIMER)
    return "\n".join(parts)


def format_watch(d: Deal, reason_missing: str) -> str:
    """أقرب مرشّح للمراقبة (لم يكتمل شرط الدخول بعد) — يظهر باسم العملة."""
    parts = [
        f"👀 أقرب مرشّح الآن: {d.symbol}",
        f"   (مراقبة فقط — لسه ما وصلش شرط الدخول: {reason_missing})",
        f"   📈 اتجاه صاعد (ارتداد) — {grade(d)}",
    ]
    parts.extend(_pick_body(d))
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

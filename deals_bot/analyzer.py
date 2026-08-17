"""
محرّك التقييم: يحوّل سلسلة الأسعار إلى صفقة مقترحة بدرجة ثقة.

Scoring engine. Turns a price Series into a scored Deal by combining several
technical signals (trend, RSI, MACD, momentum, volume). The output score is
signed: positive = bullish/BUY, negative = bearish/SELL.

Nothing here is financial advice — it's a rules-based heuristic ranking.
"""

from __future__ import annotations

from typing import List

from . import indicators as ind
from .models import Deal, Series

# معاملات المخاطرة لحساب وقف الخسارة وجني الأرباح من الـ ATR
STOP_ATR_MULT = 1.5
TARGET_ATR_MULT = 2.5

# عتبة الحياد: أي درجة أقل من هذه (بالقيمة المطلقة) تُعتبر بلا إشارة واضحة
NEUTRAL_BAND = 20.0

# نشاط الحيتان: حجم آخر شمعة ≥ هذا المضاعف من متوسط الحجم يعتبر "حوتًا"
WHALE_VOLUME_MULT = 2.5

# اندفاع (Pump): قفزة سعرية خلال عدد قليل من الشموع مع حجم مرتفع
PUMP_LOOKBACK = 3        # عدد الشموع الأخيرة لقياس الاندفاع
PUMP_MOVE_PCT = 3.0      # نسبة الحركة (٪) التي تعتبر اندفاعًا
PUMP_VOL_MULT = 2.0      # الحد الأدنى لارتفاع الحجم المصاحب

# بداية اندفاع (Early Breakout): كسر نطاق ضيّق لأول مرة بحجم، قبل أن يجري بعيدًا
EARLY_BASE_WINDOW = 20      # نافذة النطاق قبل الكسر
EARLY_MAX_RANGE = 25.0      # أقصى عرض للنطاق (٪) ليُعتبر تجميعًا/انضغاطًا
EARLY_MAX_EXTENSION = 8.0   # أقصى مسافة فوق قمة النطاق (٪) لتبقى "مبكّرًا"
EARLY_VOL_MULT = 1.5        # الحد الأدنى لحجم الكسر


def detect_early_pump(series: Series):
    """
    اكتشف بداية الاندفاع: كسر أول لقمة نطاق ضيّق بحجم عالٍ، قبل أن يجري السعر.

    Detects the *start* of a pump — the first breakout above a tight base with a
    volume surge, while the move is still small (so you enter early with a tight
    stop under the breakout level, instead of chasing a candle that already ran).
    Returns a details dict, or None.
    """
    closes = series.closes()
    highs = series.highs()
    vols = series.volumes()
    if len(closes) < 60:
        return None

    price = closes[-1]
    base = closes[-EARLY_BASE_WINDOW - 1:-1]      # النطاق المنتهي قبل الشمعة الحالية
    if not base:
        return None
    base_high = max(base)
    base_low = min(base)
    if base_high <= 0:
        return None

    range_pct = (base_high - base_low) / base_high * 100.0
    move = (price / base_high - 1.0) * 100.0        # كم فوق قمة النطاق
    vsurge = ind.volume_surge(vols, 20)
    rsi_v = ind.rsi(closes, 14)

    is_early = (
        price > base_high                            # كسر فوق النطاق
        and 0 < move <= EARLY_MAX_EXTENSION          # لسه قريب من الكسر (مبكّر)
        and range_pct <= EARLY_MAX_RANGE             # النطاق كان مضغوطًا
        and vsurge is not None and vsurge >= EARLY_VOL_MULT   # حجم الكسر
        and (rsi_v is None or rsi_v < 80)            # لم ينفجر تمامًا بعد
    )
    if not is_early:
        return None

    reasons = [
        "🚀 بداية اندفاع: كسر مقاومة النطاق لأول مرة بحجم",
        f"كسر فوق {base_high:.6g} (+{move:.1f}%)",
        f"حجم الكسر ×{vsurge:.1f}",
    ]
    if rsi_v is not None:
        reasons.append(f"RSI {rsi_v:.0f}")

    score = 55.0 + min(20.0, (vsurge - 1.5) * 12.0)      # حجم أعلى = أقوى
    score += max(0.0, (EARLY_MAX_EXTENSION - move))       # كل ما كان أبكر = أفضل
    # تأكيد تدفّق الأموال: OBV صاعد يؤكد أن الكسر مدعوم بشراء حقيقي (دقة أعلى)
    obv_up = ind.obv_rising(closes, series.volumes(), 10)
    if obv_up:
        score += 15.0
        reasons.append("💰 OBV صاعد — الكسر مدعوم بتدفّق شراء")
    elif obv_up is False:
        score -= 15.0        # كسر بلا تدفّق أموال حقيقي → غالبًا كاذب
    score = max(0.0, min(100.0, score))

    return {
        "reasons": reasons,
        "score": round(score, 1),
        "base_high": base_high,
        "base_low": base_low,
        "price": price,
        "obv_ok": bool(obv_up),
    }


def analyze_symbol(series: Series, momentum_lookback: int = 10) -> Deal:
    """
    حلّل سلسلة رمز واحد وأرجع صفقة مقترحة.

    Analyze one symbol's candle series and return a scored Deal. On insufficient
    data, returns a NEUTRAL Deal with an `error` message set.
    """
    closes = series.closes()
    highs = series.highs()
    lows = series.lows()
    volumes = series.volumes()

    if len(closes) < 60:
        return Deal(
            symbol=series.symbol,
            market=series.market,
            direction="NEUTRAL",
            score=0.0,
            confidence=0.0,
            price=closes[-1] if closes else 0.0,
            entry=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            risk_reward=0.0,
            error="بيانات غير كافية للتحليل (نحتاج 60 شمعة على الأقل).",
        )

    price = closes[-1]

    rsi_v = ind.rsi(closes, 14)
    ema_fast = ind.ema(closes, 9)
    ema_slow = ind.ema(closes, 21)
    ema_trend = ind.ema(closes, 50)
    macd_v = ind.macd(closes)          # (line, signal, hist) or None
    mom = ind.momentum_pct(closes, momentum_lookback)
    vsurge = ind.volume_surge(volumes, 20)
    mfi_v = ind.mfi(highs, lows, closes, volumes, 14)
    atr_v = ind.atr(highs, lows, closes, 14)

    bull = 0.0
    bear = 0.0
    reasons: List[str] = []

    # 1) الاتجاه عبر ترتيب المتوسطات المتحركة (أقوى إشارة)
    uptrend = downtrend = False
    if ema_fast and ema_slow and ema_trend:
        if ema_fast > ema_slow > ema_trend:
            uptrend = True
            bull += 30
            reasons.append("اتجاه صاعد: EMA9 > EMA21 > EMA50")
        elif ema_fast < ema_slow < ema_trend:
            downtrend = True
            bear += 30
            reasons.append("اتجاه هابط: EMA9 < EMA21 < EMA50")
        elif ema_fast > ema_slow:
            bull += 12
            reasons.append("تقاطع قصير المدى صاعد: EMA9 > EMA21")
        elif ema_fast < ema_slow:
            bear += 12
            reasons.append("تقاطع قصير المدى هابط: EMA9 < EMA21")

    # 2) RSI — متوافق مع الاتجاه: لا نراهن على الارتداد عكس اتجاه راسخ
    if rsi_v is not None:
        if rsi_v < 30:
            if downtrend:
                # التشبّع البيعي داخل اتجاه هابط = استمرار الضعف لا ارتداد
                bear += 8
                reasons.append(f"RSI تشبّع بيعي ({rsi_v:.0f}) مع اتجاه هابط — ضعف مستمر")
            else:
                bull += 18
                reasons.append(f"RSI تشبّع بيعي ({rsi_v:.0f}) — ارتداد محتمل")
        elif 45 <= rsi_v <= 65:
            bull += 12
            reasons.append(f"RSI في منطقة صحية صاعدة ({rsi_v:.0f})")
        elif rsi_v > 70:
            if uptrend:
                # التشبّع الشرائي داخل اتجاه صاعد = استمرار القوة لا انعكاس
                bull += 8
                reasons.append(f"RSI تشبّع شرائي ({rsi_v:.0f}) مع اتجاه صاعد — قوة مستمرة")
            else:
                bear += 16
                reasons.append(f"RSI تشبّع شرائي ({rsi_v:.0f}) — تصحيح محتمل")
        elif 35 <= rsi_v < 45:
            bear += 8
            reasons.append(f"RSI ضعيف ({rsi_v:.0f})")

    # 3) MACD
    if macd_v is not None:
        line, signal, hist = macd_v
        rising = ind.macd_hist_rising(closes)
        if hist > 0 and rising:
            bull += 18
            reasons.append("MACD إيجابي وفي تصاعد")
        elif hist > 0:
            bull += 9
            reasons.append("MACD إيجابي")
        elif hist < 0 and not rising:
            bear += 18
            reasons.append("MACD سلبي وفي تراجع")
        elif hist < 0:
            bear += 9
            reasons.append("MACD سلبي")

    # 4) الزخم (Momentum)
    if mom is not None:
        if mom > 1.5:
            bull += 14
            reasons.append(f"زخم إيجابي (+{mom:.1f}%)")
        elif mom < -1.5:
            bear += 14
            reasons.append(f"زخم سلبي ({mom:.1f}%)")

    # 5) تدفّق الأموال (MFI) — أين يتحرّك المال فعلًا (مؤشر ضغط الحيتان)
    money_flow_bull = money_flow_bear = False
    if mfi_v is not None:
        if mfi_v >= 55:
            money_flow_bull = True
            bull += 10
            reasons.append(f"تدفّق أموال إيجابي (MFI={mfi_v:.0f}) — ضغط شراء")
        elif mfi_v <= 45:
            money_flow_bear = True
            bear += 10
            reasons.append(f"تدفّق أموال سلبي (MFI={mfi_v:.0f}) — ضغط بيع")

    # 6) تدفّق الحجم العادي — يعزّز الإشارة القائمة
    if vsurge is not None and vsurge > 1.3:
        if bull >= bear:
            bull += 8
        else:
            bear += 8
        reasons.append(f"ارتفاع في حجم التداول (×{vsurge:.1f})")

    # 7) نشاط الحيتان — حجم ضخم + اتجاه واضح لتدفّق الأموال/السعر
    whale = False
    if vsurge is not None and vsurge >= WHALE_VOLUME_MULT:
        buy_side = money_flow_bull or (mom is not None and mom > 0)
        sell_side = money_flow_bear or (mom is not None and mom < 0)
        if buy_side and not sell_side:
            whale = True
            bull += 22
            reasons.insert(
                0, f"🐋 نشاط حيتان: حجم ضخم (×{vsurge:.1f}) مع تدفّق شراء قوي"
            )
        elif sell_side and not buy_side:
            whale = True
            bear += 22
            reasons.insert(
                0, f"🐋 نشاط حيتان: حجم ضخم (×{vsurge:.1f}) مع ضغط بيع قوي"
            )
        else:
            # حجم ضخم بلا اتجاه واضح — نعزّز الميل القائم فقط
            if bull >= bear:
                bull += 12
            else:
                bear += 12
            reasons.insert(0, f"🐋 حجم ضخم غير معتاد (×{vsurge:.1f})")

    # 8) اندفاع (Pump/Dump) — قفزة سعرية سريعة خلال شمعات قليلة مع حجم عالٍ
    pump = False
    short_mom = ind.momentum_pct(closes, PUMP_LOOKBACK)
    if short_mom is not None and vsurge is not None and vsurge >= PUMP_VOL_MULT:
        if short_mom >= PUMP_MOVE_PCT:
            pump = True
            bull += 16
            reasons.insert(
                0,
                f"🚀 اندفاع صاعد (Pump): +{short_mom:.1f}% خلال {PUMP_LOOKBACK} شموع "
                f"مع حجم ×{vsurge:.1f}",
            )
        elif short_mom <= -PUMP_MOVE_PCT:
            pump = True
            bear += 16
            reasons.insert(
                0,
                f"🚀 اندفاع هابط (Dump): {short_mom:.1f}% خلال {PUMP_LOOKBACK} شموع "
                f"مع حجم ×{vsurge:.1f}",
            )

    score = bull - bear                       # موجب = شراء، سالب = بيع
    score = max(-100.0, min(100.0, score))
    confidence = abs(score)

    if score >= NEUTRAL_BAND:
        direction = "BUY"
    elif score <= -NEUTRAL_BAND:
        direction = "SELL"
    else:
        direction = "NEUTRAL"

    # حساب الدخول / وقف الخسارة / الهدف من الـ ATR
    entry = price
    stop_loss = 0.0
    take_profit = 0.0
    risk_reward = 0.0
    if atr_v and atr_v > 0 and direction != "NEUTRAL":
        if direction == "BUY":
            stop_loss = price - STOP_ATR_MULT * atr_v
            take_profit = price + TARGET_ATR_MULT * atr_v
        else:  # SELL
            stop_loss = price + STOP_ATR_MULT * atr_v
            take_profit = price - TARGET_ATR_MULT * atr_v
        risk = abs(entry - stop_loss)
        reward = abs(take_profit - entry)
        risk_reward = (reward / risk) if risk > 0 else 0.0

    return Deal(
        symbol=series.symbol,
        market=series.market,
        direction=direction,
        score=round(score, 1),
        confidence=round(confidence, 1),
        price=price,
        entry=round(entry, 8),
        stop_loss=round(stop_loss, 8),
        take_profit=round(take_profit, 8),
        risk_reward=round(risk_reward, 2),
        reasons=reasons,
        whale=whale,
        pump=pump,
        indicators={
            "rsi": round(rsi_v, 1) if rsi_v is not None else None,
            "ema9": round(ema_fast, 6) if ema_fast else None,
            "ema21": round(ema_slow, 6) if ema_slow else None,
            "ema50": round(ema_trend, 6) if ema_trend else None,
            "macd_hist": round(macd_v[2], 6) if macd_v else None,
            "momentum_pct": round(mom, 2) if mom is not None else None,
            "volume_surge": round(vsurge, 2) if vsurge is not None else None,
            "mfi": round(mfi_v, 1) if mfi_v is not None else None,
            "atr": round(atr_v, 6) if atr_v else None,
        },
    )


# --- كشف مرحلة التجميع (بعد هبوط، نطاق عرضي ضيّق، بانتظار الاندفاع) ---
ACC_MIN_DROP = 15.0        # أقل نسبة هبوط (٪) من القمة لاعتبارها بعد هبوط
ACC_MAX_BASE_RANGE = 12.0  # أقصى عرض للنطاق العرضي (٪) ليُعتبر تجميعًا
ACC_LOOKBACK = 14          # عدد شموع النطاق الأخير


def detect_accumulation(series: Series):
    """
    اكتشف مرحلة التجميع: هبوط سابق ثم نطاق عرضي ضيّق مستقر (قيعان صامدة).

    Detects a Wyckoff-style accumulation base: a prior decline, then a tight
    sideways range holding above its lows with RSI recovering — a setup that
    often precedes a markup ("pump"). Returns a details dict, or None.
    """
    closes = series.closes()
    if len(closes) < 80:
        return None

    price = closes[-1]
    window = closes[-100:] if len(closes) >= 100 else closes
    swing_high = max(window)
    if swing_high <= 0:
        return None
    drop = (price / swing_high - 1.0) * 100.0            # سالبة = هبوط من القمة

    recent = closes[-ACC_LOOKBACK:]
    base_low = min(recent)
    base_high = max(recent)
    base_range = (base_high - base_low) / price * 100.0 if price else 999.0

    # القيعان صامدة: قاع النطاق الحالي ليس أدنى بكثير من النطاق السابق
    prior = closes[-2 * ACC_LOOKBACK:-ACC_LOOKBACK] if len(closes) >= 2 * ACC_LOOKBACK else recent
    prior_low = min(prior)
    holding = base_low >= prior_low * 0.97

    # الميل قصير المدى مسطّح أو يتجه لأعلى قليلًا
    first5 = sum(recent[:5]) / 5.0
    last5 = sum(recent[-5:]) / 5.0
    slope_pct = (last5 / first5 - 1.0) * 100.0 if first5 else 0.0

    rsi_v = ind.rsi(closes, 14)
    vsurge = ind.volume_surge(series.volumes(), 20)

    conditions = (
        drop <= -ACC_MIN_DROP           # حصل هبوط معتبر
        and base_range <= ACC_MAX_BASE_RANGE   # نطاق ضيّق
        and holding                      # لا يصنع قيعانًا جديدة
        and slope_pct >= -1.5            # توقّف الهبوط (مسطّح/يصعد)
        and (rsi_v is None or rsi_v <= 60)     # لم يندفع بعد
    )
    if not conditions:
        return None

    reasons = [
        "📥 تجميع بعد هبوط — بانتظار الاندفاع",
        f"هبوط سابق {drop:.0f}% من القمة",
        f"نطاق تجميع ضيّق (~{base_range:.1f}%)",
        "يحافظ على قيعانه (لا قيعان جديدة)",
    ]
    if rsi_v is not None:
        reasons.append(f"RSI في تعافٍ ({rsi_v:.0f})")

    # درجة قوة التجميع
    score = 50.0
    score += min(18.0, abs(drop) - ACC_MIN_DROP)          # هبوط أعمق = قاعدة أقوى
    score += max(0.0, (ACC_MAX_BASE_RANGE - base_range)) * 1.5  # نطاق أضيق = أفضل
    if vsurge is not None and vsurge > 1.2:
        score += 8.0
        reasons.append(f"حجم يبدأ بالارتفاع (×{vsurge:.1f})")
    # تأكيد تدفّق الأموال: OBV صاعد أثناء القاعدة = تجميع حقيقي (دقة أعلى)
    obv_up = ind.obv_rising(closes, series.volumes(), ACC_LOOKBACK)
    if obv_up:
        score += 15.0
        reasons.append("💰 تدفّق أموال يتجمّع بهدوء (OBV صاعد)")
    elif obv_up is False:
        score -= 12.0        # المال يخرج أثناء القاعدة → احتمال أضعف
    score = max(0.0, min(100.0, score))

    return {
        "reasons": reasons,
        "score": round(score, 1),
        "base_low": base_low,
        "base_high": base_high,
        "drop": drop,
        "price": price,
        "obv_ok": bool(obv_up),
    }


def _band_width(closes, i, period=20, mult=2.0):
    """عرض نطاق بولنجر النسبي عند الشمعة i: (العلوي−السفلي)/الوسط."""
    if i - period + 1 < 0:
        return None
    w = closes[i - period + 1:i + 1]
    mid = sum(w) / period
    if mid == 0:
        return None
    sd = (sum((x - mid) ** 2 for x in w) / period) ** 0.5
    return (2 * mult * sd) / mid


def detect_pre_pump(series: Series):
    """
    اكتشف الانضغاط قبل الاندفاع: تذبذب منخفض جدًا (نطاق بولنجر ضيّق) والحجم يبدأ
    بالتجمّع — «الهدوء الذي يسبق العاصفة»، قبل أن يتحرك السعر.

    Detects a pre-move volatility squeeze: Bollinger bandwidth compressed well
    below its recent average, a tight range, calm (not overbought) RSI, and
    volume no longer dead — a classic coil that precedes a breakout. Returns a
    details dict or None. This is a BEFORE-the-pump signal.
    """
    closes = series.closes()
    if len(closes) < 60:
        return None
    price = closes[-1]

    widths = [
        w for w in (_band_width(closes, i) for i in range(len(closes) - 30, len(closes)))
        if w is not None
    ]
    if len(widths) < 12:
        return None
    cur = widths[-1]
    avg = sum(widths) / len(widths)

    rsi_v = ind.rsi(closes, 14)
    vsurge = ind.volume_surge(series.volumes(), 20)
    recent = closes[-15:]
    base_low = min(recent)
    base_high = max(recent)
    range_pct = (base_high - base_low) / price * 100.0 if price else 999.0

    squeeze = cur < 0.70 * avg and cur < 0.15          # منضغط بشدة نسبيًا وصغير مطلقًا
    calm = rsi_v is None or 42 <= rsi_v <= 66           # لا تشبّع (لم ينفجر بعد)
    building = vsurge is None or vsurge >= 0.9          # الحجم لم يمت
    tight = range_pct <= 12.0

    if not (squeeze and calm and building and tight):
        return None

    reasons = [
        "🎯 انضغاط قبل الاندفاع — تذبذب منخفض جدًا (الهدوء قبل العاصفة)",
        f"نطاق ضيّق (~{range_pct:.1f}%)",
        f"انضغاط بولنجر ({cur*100:.1f}% مقابل متوسط {avg*100:.1f}%)",
    ]
    if vsurge is not None and vsurge > 1.1:
        reasons.append(f"الحجم يبدأ بالتجمّع (×{vsurge:.1f})")
    if rsi_v is not None:
        reasons.append(f"RSI هادئ ({rsi_v:.0f})")

    score = 60.0 + min(25.0, (0.70 * avg - cur) / (0.70 * avg) * 50.0)
    score = max(0.0, min(100.0, score))
    return {
        "reasons": reasons,
        "score": round(score, 1),
        "base_low": base_low,
        "base_high": base_high,
        "price": price,
    }


def detect_trend_pullback(series: Series, rr: float = 2.0, direction: str = "long",
                          require_momentum: bool = False, stop_buffer_atr: float = 0.0):
    """
    اكتشف «الارتداد داخل الاتجاه» — دخول مع الاتجاه لا ضدّه (Long أو Short).

    LONG : اتجاه صاعد مؤكّد EMA9>EMA21>EMA50 وEMA50 يصعد، السعر يلمس EMA21 من
           أعلى ثم يغلق فوقه، RSI لم ينهَر. الوقف تحت قاع الارتداد، الهدف أعلى.
    SHORT: عكسه تمامًا — اتجاه هابط EMA9<EMA21<EMA50 وEMA50 يهبط، السعر يرتفع
           ليلمس EMA21 من أسفل ثم يغلق تحته، RSI لم ينفجر. الوقف فوق قمة الارتداد.

    require_momentum: فلتر الزخم القوي — لا ندخل إلا لو الزخم الأساسي مؤيّد
      (MACD في اتجاه الصفقة + زخم سعري في نفس الاتجاه). يقلّل الانعكاس الفوري.

    stop_buffer_atr: مسافة تنفّس للوقف بمضاعف ATR — يبعد الوقف عن قاع/قمة الارتداد
      بمقدار (stop_buffer_atr × ATR) عشان الذيول السريعة (stop-hunt) ما تضربوش
      بدري. صفر = الوقف الملزوق الأصلي. يجب قياسه بالباك-تِست قبل تفعيله حيًّا.

    Returns a details dict (score + levels + direction) or None. Single source of
    truth shared by the live bot and the backtester.
    """
    closes = series.closes()
    n = len(closes)
    if n < 55:
        return None
    price = closes[-1]
    low = series.lows()[-1]
    high = series.highs()[-1]
    atr_v = (ind.atr(series.highs(), series.lows(), closes, 14)
             if stop_buffer_atr > 0 else None)
    e9 = ind.ema(closes, 9)
    e21 = ind.ema(closes, 21)
    e50 = ind.ema(closes, 50)
    e50_prev = ind.ema(closes[:-3], 50) if n > 53 else None
    rsi_v = ind.rsi(closes, 14)
    if None in (e9, e21, e50, e50_prev, rsi_v):
        return None

    vs = ind.volume_surge(series.volumes(), 20)
    obv_up = ind.obv_rising(closes, series.volumes(), 10)
    slope_pct = (e50 / e50_prev - 1.0) * 100.0
    # الزخم الأساسي (لفلتر الزخم القوي)
    macd_v = ind.macd(closes)
    mom_v = ind.momentum_pct(closes, 10)

    if direction == "short":
        downtrend = e9 < e21 < e50 and e50 < e50_prev
        touched_ma = high >= e21 >= price      # ارتد لأعلى للمتوسّط ثم أغلق تحته
        healthy = rsi_v <= 60.0
        if not (downtrend and touched_ma and healthy):
            return None
        if require_momentum:                   # زخم هابط قوي (MACD سلبي + زخم سالب)
            strong = ((macd_v is not None and macd_v[2] < 0)
                      and (mom_v is not None and mom_v < 0))
            if not strong:
                return None
        stop = max(high, e21) * 1.005
        if stop_buffer_atr > 0 and atr_v:
            stop += stop_buffer_atr * atr_v          # مسافة تنفّس فوق القمة
        risk = stop - price
        if risk <= 0:
            return None
        target = price - rr * risk
        reasons = [
            "📉 ارتداد داخل اتجاه هابط — بيع مع الاتجاه (Short)",
            "ترتيب هابط: EMA9<EMA21<EMA50 وEMA50 يهبط",
            f"ارتداد لأعلى على EMA21 ثم إغلاق تحته (RSI {rsi_v:.0f})",
        ]
        score = 60.0
        score += min(14.0, max(0.0, -slope_pct * 6.0))   # هبوط أقوى ميلًا = أفضل
        if 40.0 <= rsi_v <= 55.0:
            score += 8.0
            reasons.append("RSI في منطقة ارتداد صحّية للهبوط")
        if vs is not None and vs > 1.2:
            score += 6.0
            reasons.append(f"ارتفاع حجم عند الارتداد (×{vs:.1f})")
        if obv_up is False:
            score += 12.0
            reasons.append("💧 OBV هابط — تدفّق بيع يدعم الاتجاه")
        elif obv_up:
            score -= 10.0
        score = max(0.0, min(100.0, score))
        return {
            "reasons": reasons, "score": round(score, 1), "direction": "SELL",
            "price": price, "stop": stop, "target": target,
            "base_low": price, "base_high": high, "rsi": rsi_v,
        }

    # --- LONG (افتراضي) ---
    uptrend = e9 > e21 > e50 and e50 > e50_prev
    touched_ma = low <= e21 <= price          # ارتداد: لمس المتوسّط ثم أغلق فوقه
    healthy = rsi_v >= 40.0
    if not (uptrend and touched_ma and healthy):
        return None
    if require_momentum:                       # زخم صاعد قوي (MACD إيجابي + زخم موجب)
        strong = ((macd_v is not None and macd_v[2] > 0)
                  and (mom_v is not None and mom_v > 0))
        if not strong:
            return None

    stop = min(low, e21) * 0.995
    if stop_buffer_atr > 0 and atr_v:
        stop -= stop_buffer_atr * atr_v              # مسافة تنفّس تحت القاع
    risk = price - stop
    if risk <= 0:
        return None
    target = price + rr * risk

    reasons = [
        "📈 ارتداد داخل اتجاه صاعد — دخول مع الاتجاه (أقوى إحصائيًا)",
        "ترتيب صاعد: EMA9>EMA21>EMA50 وEMA50 يصعد",
        f"ارتداد على EMA21 ثم إغلاق فوقه (RSI {rsi_v:.0f})",
    ]
    score = 60.0
    score += min(14.0, max(0.0, slope_pct * 6.0))        # اتجاه أقوى ميلًا = أفضل
    if 45.0 <= rsi_v <= 60.0:
        score += 8.0
        reasons.append("RSI في منطقة ارتداد صحّية")
    if vs is not None and vs > 1.2:
        score += 6.0
        reasons.append(f"ارتفاع حجم عند الارتداد (×{vs:.1f})")
    if obv_up:
        score += 12.0
        reasons.append("💰 OBV صاعد — تدفّق شراء يدعم الاتجاه")
    elif obv_up is False:
        score -= 10.0
    score = max(0.0, min(100.0, score))

    return {
        "reasons": reasons, "score": round(score, 1), "direction": "BUY",
        "price": price, "stop": stop, "target": target,
        "base_low": low, "base_high": price, "rsi": rsi_v,
    }


def detect_breakout(series: Series, lookback: int = 20, rr: float = 2.0,
                    stop_buffer_atr: float = 0.5):
    """
    اكتشف «اختراق الاتجاه» (Donchian Breakout) — نظام تتبّع الاتجاه الكلاسيكي
    (أصل نظام السلاحف الذي بنت عليه صناديق CTA المؤسسية).

    يشتري حين يكسر السعر أعلى قمة آخر `lookback` شمعة (اختراق حقيقي) بشرط:
      • السوق في اتجاه صاعد بعيد المدى (السعر فوق EMA50 وEMA50 يصعد).
      • حجم الاختراق مرتفع (تأكيد أن الكسر مدعوم بشراء حقيقي).
      • RSI لم ينفجر بعد (لا نطارد شمعة جرت بعيدًا).
    الوقف تحت الاختراق بمسافة ATR، الهدف = الدخول + rr×المخاطرة.

    Returns a details dict (score + levels) or None. مصدر واحد للحقيقة يشاركه
    البوت الحيّ والباك-تِست. يجب قياسه قبل تفعيله حيًّا.
    """
    closes = series.closes()
    highs = series.highs()
    lows = series.lows()
    n = len(closes)
    if n < max(lookback + 5, 55):
        return None
    price = closes[-1]
    atr_v = ind.atr(highs, lows, closes, 14)
    e50 = ind.ema(closes, 50)
    e50_prev = ind.ema(closes[:-3], 50) if n > 53 else None
    rsi_v = ind.rsi(closes, 14)
    if None in (atr_v, e50, e50_prev, rsi_v) or atr_v <= 0:
        return None

    # قمة النطاق = أعلى قمة في آخر lookback شمعة قبل الشمعة الحالية
    prior_high = max(highs[-lookback - 1:-1])
    if prior_high <= 0:
        return None

    uptrend = price > e50 and e50 > e50_prev        # اتجاه بعيد المدى صاعد
    broke_out = price > prior_high                   # كسر أعلى النطاق
    healthy = rsi_v < 78.0                            # لم ينفجر تمامًا
    move = (price / prior_high - 1.0) * 100.0         # كم فوق الكسر (مبكّر؟)
    early = move <= 6.0                               # لسه قريب من نقطة الكسر
    vs = ind.volume_surge(series.volumes(), 20)
    vol_ok = vs is not None and vs >= 1.3            # حجم الاختراق

    if not (uptrend and broke_out and healthy and early and vol_ok):
        return None

    stop = prior_high - stop_buffer_atr * atr_v      # الوقف تحت مستوى الكسر
    risk = price - stop
    if risk <= 0:
        return None
    target = price + rr * risk

    reasons = [
        "🚀 اختراق اتجاه (Donchian) — تتبّع الاتجاه كالمؤسسات (CTA)",
        f"كسر أعلى قمة {lookback} شمعة عند {prior_high:.6g} (+{move:.1f}%)",
        f"فوق EMA50 صاعد | RSI {rsi_v:.0f} | حجم ×{vs:.1f}",
    ]
    score = 60.0
    score += min(14.0, max(0.0, (6.0 - move) * 2.0))     # كل ما كان أبكر = أفضل
    score += min(12.0, max(0.0, (vs - 1.3) * 8.0))        # حجم أعلى = أقوى
    obv_up = ind.obv_rising(closes, series.volumes(), 10)
    if obv_up:
        score += 12.0
        reasons.append("💰 OBV صاعد — الكسر مدعوم بتدفّق شراء")
    elif obv_up is False:
        score -= 10.0
    score = max(0.0, min(100.0, score))

    return {
        "reasons": reasons, "score": round(score, 1), "direction": "BUY",
        "price": price, "stop": stop, "target": target,
        "base_low": stop, "base_high": price, "rsi": rsi_v,
    }


def estimate_eta_hours(entry: float, target: float, atr: float,
                       tf_hours: float = 1.0):
    """
    قدّر الزمن المتوقّع لوصول السعر إلى الهدف (تقديري لا مضمون).

    Rough ETA: price travels ~ATR per candle on average, so candles-to-target ≈
    distance / ATR, and hours ≈ that × the timeframe length. This is a heuristic
    for setting expectations, NOT a promise — markets move irregularly.
    Returns hours (float) or None if it can't be computed.
    """
    if not atr or atr <= 0 or entry <= 0:
        return None
    distance = abs(target - entry)
    if distance <= 0:
        return None
    candles = distance / atr
    return round(candles * tf_hours, 1)


# طول الإطار الزمني بالساعات (لتقدير الزمن المتوقّع للهدف)
TF_HOURS = {"1m": 1 / 60, "5m": 5 / 60, "15m": 0.25, "30m": 0.5,
            "1h": 1.0, "6h": 6.0, "1d": 24.0}


def add_position_sizing(deal: Deal, balance: float, risk_pct: float) -> Deal:
    """
    احسب حجم الصفقة المقترح بناءً على رأس المال ونسبة المخاطرة.

    Position size = (balance * risk_pct) / risk_per_unit, where risk_per_unit is
    the distance between entry and stop-loss. Ensures you never risk more than
    `risk_pct` of the account on a single trade.
    """
    if not deal.is_actionable() or balance <= 0 or risk_pct <= 0:
        return deal
    risk_per_unit = abs(deal.entry - deal.stop_loss)
    if risk_per_unit <= 0:
        return deal
    risk_amount = balance * risk_pct
    deal.qty = round(risk_amount / risk_per_unit, 8)
    deal.risk_amount = round(risk_amount, 2)
    return deal


def rank_deals(
    all_series: List[Series],
    top: int = 5,
    direction: str = "any",
    momentum_lookback: int = 10,
    min_confidence: float = 0.0,
) -> List[Deal]:
    """
    حلّل عدة رموز ورتّبها لإرجاع أفضل الصفقات.

    Analyze many symbols and return the strongest `top` deals.
      direction = "buy"  → only BUY deals
      direction = "sell" → only SELL deals
      direction = "any"  → strongest signal in either direction
      min_confidence     → drop deals weaker than this (quality filter)
    """
    deals = [analyze_symbol(s, momentum_lookback=momentum_lookback) for s in all_series]
    actionable = [d for d in deals if d.is_actionable() and d.confidence >= min_confidence]

    if direction == "buy":
        actionable = [d for d in actionable if d.direction == "BUY"]
        actionable.sort(key=lambda d: d.score, reverse=True)
    elif direction == "sell":
        actionable = [d for d in actionable if d.direction == "SELL"]
        actionable.sort(key=lambda d: d.score)  # most negative first
    else:
        actionable.sort(key=lambda d: d.confidence, reverse=True)

    return actionable[:top]

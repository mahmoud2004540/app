#!/usr/bin/env python3
"""
شغّل باك-تِست على بيانات حقيقية لقياس نسبة نجاح الاستراتيجية.

Run a backtest on real historical data to see the strategy's honest win rate and
expectancy — so your expectations are grounded in numbers, not hype.

أمثلة / Examples:
    python backtest.py --market crypto
    python backtest.py --market stocks --timeframe 1d
    python backtest.py --market all --timeframe 1h
"""

from __future__ import annotations

import argparse
import sys

import config
from deals_bot.backtester import (
    backtest_prepump_series,
    backtest_series,
    backtest_trend_pullback_series,
    market_return_map,
    market_uptrend_map,
)
from deals_bot.providers import fetch, fetch_many
from deals_bot.strategy import resolve_symbols
from deals_bot.walkforward import summarize as wf_summarize
from deals_bot.walkforward import walk_forward

# حدّ أقصى لعدد رموز الكريبتو في الباك-تِست (لتحديد الوقت)
BACKTEST_MAX_CRYPTO = 80

_STRATEGIES = {
    "signals": backtest_series,
    "prepump": backtest_prepump_series,
    "trend": backtest_trend_pullback_series,
}
# استراتيجيات تفحص نطاقًا واسعًا من الكريبتو (لا لائحة ثابتة)
_BROAD_CRYPTO = {"prepump", "trend"}


def run(market: str, source: str, timeframe: str, strategy: str = "signals") -> int:
    markets = ["crypto", "stocks", "forex"] if market == "all" else [market]
    bt = _STRATEGIES[strategy]

    total_trades = total_wins = 0
    total_r = 0.0
    rows = []

    for mkt in markets:
        src = source if mkt == "crypto" else "yfinance"
        if mkt == "crypto" and strategy in _BROAD_CRYPTO:
            symbols = resolve_symbols("crypto", "auto")[:BACKTEST_MAX_CRYPTO]
        elif mkt == "crypto" and src == "binance":
            symbols = config.BINANCE_WATCHLIST
        else:
            symbols = config.WATCHLISTS[mkt]
        print(f"⏳ باك-تِست ({strategy}) {len(symbols)} رمزًا في «{mkt}» ({timeframe})...")
        series = fetch_many(symbols, mkt, src, timeframe, limit=1000)
        # للـ prepump: طبّق نفس عتبة الجودة المستخدمة حيًّا (لقياس النسخة الصارمة)
        pre_min = getattr(config, "PREPUMP_MIN_SCORE", 85) if strategy == "prepump" else 0.0
        for s in series:
            res = bt(s, min_score=pre_min) if strategy == "prepump" else bt(s)
            if res.n == 0:
                continue
            rows.append(res)
            total_trades += res.n
            total_wins += res.wins
            total_r += res.total_r
            print(
                f"  {s.symbol:<12} صفقات={res.n:<3} "
                f"نجاح={res.win_rate:5.1f}%  "
                f"عامل الربح={res.profit_factor:4.2f}  "
                f"إجمالي={res.total_r:+.1f}R"
            )

    print("\n" + "=" * 48)
    if total_trades == 0:
        print("لا توجد صفقات كافية في الفترة المختارة.")
        return 0
    win_rate = total_wins / total_trades * 100.0
    expectancy = total_r / total_trades
    print(f"الإجمالي: {total_trades} صفقة")
    print(f"نسبة النجاح: {win_rate:.1f}%")
    print(f"العائد المتوقّع لكل صفقة: {expectancy:+.2f}R")
    print(f"إجمالي العائد: {total_r:+.1f}R")
    print("=" * 48)
    print(
        "\nℹ️ ملاحظة: R = مضاعف المخاطرة. عائد +0.2R لكل صفقة يعني استراتيجية "
        "رابحة على المدى الطويل حتى لو نسبة النجاح أقل من 100%."
    )
    return 0


def trend_sweep(source: str, timeframe: str) -> int:
    """
    اختبار الانتقائية: هل «اختيار الأفضل فقط» + «فلتر حالة السوق» يقلب التوقّع لموجب؟

    يفحص كل العملات مرّة واحدة، ثم يجرّب استراتيجية الاتجاه عند عتبات درجة متعددة،
    مرّة بلا فلتر سوق ومرّة مع فلتر (لا ندخل إلا لما البيتكوين فوق متوسّطه).
    ناتج واحد يجيب سؤال المستخدم: صفقة واحدة أو اثنتان من الأفضل — هل تربح؟
    """
    symbols = resolve_symbols("crypto", "auto")[:BACKTEST_MAX_CRYPTO]
    print(f"⏳ فحص انتقائية الاتجاه على {len(symbols)} عملة ({timeframe})...")
    series = fetch_many(symbols, "crypto", "auto", timeframe, limit=1000)

    # حالة السوق من البيتكوين
    regime = None
    try:
        btc = fetch("BTC-USD", "crypto", "auto", timeframe, limit=1000)
        regime = market_uptrend_map(btc, 50)
        print(f"  ✅ خريطة حالة السوق من BTC ({len(regime)} شمعة).")
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️ تعذّر بناء فلتر السوق: {exc} — سنعرض بلا فلتر فقط.")

    thresholds = [0.0, 70.0, 80.0, 85.0, 90.0]
    print("\n" + "=" * 64)
    print(f"{'عتبة':>6} | {'فلتر سوق':>8} | {'صفقات':>6} | {'نجاح%':>6} | {'توقّع/R':>8} | {'إجمالي':>8}")
    print("-" * 64)

    def summarize(min_score: float, use_regime: bool):
        reg = regime if use_regime else None
        tt = tw = 0
        tr = 0.0
        for s in series:
            res = backtest_trend_pullback_series(s, min_score=min_score, regime=reg)
            tt += res.n
            tw += res.wins
            tr += res.total_r
        wr = (tw / tt * 100.0) if tt else 0.0
        exp = (tr / tt) if tt else 0.0
        tag = "نعم" if use_regime else "لا"
        print(f"{min_score:>6.0f} | {tag:>8} | {tt:>6} | {wr:>6.1f} | {exp:>+8.2f} | {tr:>+8.1f}")

    for th in thresholds:
        summarize(th, False)
    if regime is not None:
        print("-" * 64)
        for th in thresholds:
            summarize(th, True)
    print("=" * 64)

    # اختبار المتانة: هل ربح الإعداد الفائز (85 + فلتر سوق) موزّع على عملات كثيرة
    # أم مركّز في عملة أو اثنتين (حظّ)؟ نطبع توزيع الرابح/الخاسر وأهم المساهمين.
    win_score, win_reg = 85.0, (regime if regime is not None else None)
    per_coin = []
    for s in series:
        res = backtest_trend_pullback_series(s, min_score=win_score, regime=win_reg)
        if res.n:
            per_coin.append((s.symbol, res.n, res.win_rate, res.total_r))
    if per_coin:
        pos = [c for c in per_coin if c[3] > 0]
        neg = [c for c in per_coin if c[3] < 0]
        per_coin.sort(key=lambda c: c[3], reverse=True)
        print(f"\n🔬 متانة الإعداد الفائز (درجة ≥{win_score:.0f}"
              f"{' + فلتر سوق' if win_reg else ''}):")
        print(f"   عملات دخلت صفقات: {len(per_coin)} | رابحة: {len(pos)} | "
              f"خاسرة: {len(neg)} | متعادلة: {len(per_coin)-len(pos)-len(neg)}")
        share = (len(pos) / len(per_coin) * 100.0) if per_coin else 0.0
        print(f"   نسبة العملات الرابحة: {share:.0f}%")
        print("   أعلى 5 مساهمين:")
        for sym, n, wr, tr in per_coin[:5]:
            print(f"     {sym:<12} صفقات={n:<3} نجاح={wr:4.0f}%  {tr:+.1f}R")
        print("   أدنى 5 مساهمين:")
        for sym, n, wr, tr in per_coin[-5:]:
            print(f"     {sym:<12} صفقات={n:<3} نجاح={wr:4.0f}%  {tr:+.1f}R")
        print(
            "\n   ✅ لو النسبة الرابحة ≥55% والربح غير مركّز في عملة واحدة → أفضلية "
            "حقيقية موزّعة (نثق بها). لو مركّز → حظّ، لا ننشره كإستراتيجية رابحة."
        )
    print("=" * 64)
    print(
        "\nℹ️ نبحث عن صفّ توقّعه موجب (+). التوقّع الموجب = أفضلية حقيقية على المدى "
        "الطويل. لو كل الصفوف سالبة، فلا أفضلية في الإشارات الآلية المجّانية عبر كل "
        "العملات، وسنكون صرحاء بذلك."
    )
    return 0


def optimize(source: str, timeframe: str) -> int:
    """
    تحسين مقاس بالدليل: عند الإعداد الفائز (درجة ≥85 + فلتر سوق)، جرّب نِسَب
    هدف/مخاطرة مختلفة وفلتر EMA200، واطبع التوقّع لكلٍّ لاختيار الأفضل.
    """
    symbols = resolve_symbols("crypto", "auto")[:BACKTEST_MAX_CRYPTO]
    print(f"⏳ تحسين إعداد الاتجاه على {len(symbols)} عملة ({timeframe})...")
    series = fetch_many(symbols, "crypto", "auto", timeframe, limit=1000)

    regime = None
    try:
        btc = fetch("BTC-USD", "crypto", "auto", timeframe, limit=1000)
        regime = market_uptrend_map(btc, 50)
        print(f"  ✅ خريطة حالة السوق من BTC ({len(regime)} شمعة).")
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️ تعذّر بناء فلتر السوق: {exc}")

    def summarize(label: str, rr: float, ema200: bool, be_r: float = 0.0):
        tt = tw = 0
        tr = 0.0
        for s in series:
            res = backtest_trend_pullback_series(
                s, rr=rr, min_score=85.0, regime=regime,
                require_ema200=ema200, breakeven_r=be_r,
            )
            tt += res.n
            tw += res.wins
            tr += res.total_r
        wr = (tw / tt * 100.0) if tt else 0.0
        exp = (tr / tt) if tt else 0.0
        print(f"{label:>26} | {tt:>6} | {wr:>6.1f} | {exp:>+8.2f} | {tr:>+8.1f}")
        return exp, tt

    print("\n" + "=" * 64)
    print(f"{'التهيئة':>26} | {'صفقات':>6} | {'نجاح%':>6} | {'توقّع/R':>8} | {'إجمالي':>8}")
    print("-" * 64)
    results = {}
    for rr in (1.5, 2.0, 2.5, 3.0):
        results[f"rr={rr}"] = summarize(f"RR {rr} (أساسي)", rr, False)
    print("-" * 64)
    for rr in (2.0, 2.5, 3.0):
        results[f"rr={rr}+ema200"] = summarize(f"RR {rr} + EMA200", rr, True)
    print("-" * 64)
    # اختبار نقل الوقف لنقطة التعادل عند +1R (مع أفضل تهيئة: EMA200)
    for rr in (2.0, 2.5, 3.0):
        results[f"rr={rr}+ema200+be1"] = summarize(
            f"RR {rr} + EMA200 + تعادل@1R", rr, True, be_r=1.0
        )
    print("=" * 64)

    # أفضل تهيئة بالتوقّع (بشرط عدد صفقات معقول ≥20 لتفادي عيّنة صغيرة)
    valid = {k: v for k, v in results.items() if v[1] >= 20}
    if valid:
        best = max(valid, key=lambda k: valid[k][0])
        exp, tt = valid[best]
        print(f"\n🏆 الأفضل: {best} → توقّع {exp:+.2f}R على {tt} صفقة.")
        print("   ثبّتها في config.py لو أعلى بوضوح من التهيئة الحالية (RR 2.0).")
    print(
        "\nℹ️ نختار أعلى توقّع مع عدد صفقات كافٍ. زيادة RR ترفع الربح لكن تقلّل نسبة "
        "النجاح؛ فلتر EMA200 يقلّل الصفقات مقابل جودة أعلى."
    )
    return 0


def walk_forward_run(source: str, timeframe: str) -> int:
    """
    اختبار المشي الأمامي: يدرّب العتبة داخل العيّنة ويختبرها خارجها عبر عدة طيّات.
    يجيب سؤال: هل الأفضلية تصمد على بيانات لم تُضبط عليها؟
    """
    symbols = resolve_symbols("crypto", "auto")[:BACKTEST_MAX_CRYPTO]
    print(f"⏳ Walk-Forward على {len(symbols)} عملة ({timeframe})...")
    series = fetch_many(symbols, "crypto", "auto", timeframe, limit=1000)
    results = walk_forward(series, folds=4, thresholds=(80.0, 85.0, 90.0), require_ema200=True)

    print("\n" + "=" * 60)
    print(f"{'طيّة':>5} | {'عتبة تدريب':>10} | {'توقّع تدريب':>11} | "
          f"{'صفقات اختبار':>12} | {'توقّع اختبار':>12}")
    print("-" * 60)
    for r in results:
        print(f"{r.fold:>5} | {r.train_best_score:>10.0f} | {r.train_expectancy:>+11.2f} | "
              f"{r.test_trades:>12} | {r.test_expectancy:>+12.2f}")
    print("=" * 60)
    s = wf_summarize(results)
    print(f"خارج العيّنة (OOS): {s['oos_trades']} صفقة | "
          f"توقّع {s['oos_expectancy']:+.2f}R | إجمالي {s['oos_total_r']:+.1f}R")
    print(
        "\nℹ️ التوقّع الموجب خارج العيّنة = الأفضلية تصمد على بيانات لم تُضبط عليها "
        "(تعميم حقيقي، لا مبالغة في المطابقة)."
    )
    return 0


def short_test(source: str, timeframe: str) -> int:
    """
    قياس استراتيجية Short (نفس منطق الاتجاه لكن معكوس): درجة ≥85 + فلتر سوق هابط
    + السعر تحت EMA200. نجيب نسبة النجاح والتوقّع الحقيقيين قبل أي تفعيل حيّ.
    """
    symbols = resolve_symbols("crypto", "auto")[:BACKTEST_MAX_CRYPTO]
    print(f"⏳ قياس Short على {len(symbols)} عملة ({timeframe})...")
    series = fetch_many(symbols, "crypto", "auto", timeframe, limit=1000)

    # فلتر السوق للـ Short = عكس الصعود (البيتكوين تحت متوسّطه)
    bearish = None
    try:
        btc = fetch("BTC-USD", "crypto", "auto", timeframe, limit=1000)
        up = market_uptrend_map(btc, 50)
        bearish = {ts: (not v) for ts, v in up.items()}
        print(f"  ✅ خريطة السوق الهابط من BTC ({len(bearish)} شمعة).")
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️ تعذّر بناء فلتر السوق: {exc}")

    def summarize(label, min_score, use_regime, ema200):
        reg = bearish if use_regime else None
        tt = tw = 0
        tr = 0.0
        for s in series:
            res = backtest_trend_pullback_series(
                s, direction="short", min_score=min_score, regime=reg,
                require_ema200=ema200,
            )
            tt += res.n
            tw += res.wins
            tr += res.total_r
        wr = (tw / tt * 100.0) if tt else 0.0
        exp = (tr / tt) if tt else 0.0
        print(f"{label:>28} | {tt:>6} | {wr:>6.1f} | {exp:>+8.2f} | {tr:>+8.1f}")
        return exp, tt

    print("\n" + "=" * 66)
    print(f"{'تهيئة Short':>28} | {'صفقات':>6} | {'نجاح%':>6} | {'توقّع/R':>8} | {'إجمالي':>8}")
    print("-" * 66)
    summarize("درجة≥0 بلا فلاتر", 0.0, False, False)
    summarize("درجة≥85", 85.0, False, False)
    summarize("درجة≥85 + سوق هابط", 85.0, True, False)
    summarize("درجة≥85 + سوق + EMA200", 85.0, True, True)
    print("=" * 66)
    print(
        "\nℹ️ نبحث عن توقّع موجب (+). لو موجب → نفعّل Short في السوق الهابط. "
        "لو سالب → لا نفعّله ونقولها بصراحة."
    )
    return 0


def precision_test(source: str, timeframe: str) -> int:
    """
    اختبار الدقة: يجرّب عتبات درجة أعلى ونِسَب هدف مختلفة (مع فلتر السوق + EMA200)
    ويقيس نسبة النجاح الحقيقية — لاختيار أعلى دقة مع أفضلية موجبة وعدد صفقات كافٍ.
    """
    symbols = resolve_symbols("crypto", "auto")[:BACKTEST_MAX_CRYPTO]
    print(f"⏳ اختبار الدقة على {len(symbols)} عملة ({timeframe})...")
    series = fetch_many(symbols, "crypto", "auto", timeframe, limit=1000)

    regime = None
    try:
        btc = fetch("BTC-USD", "crypto", "auto", timeframe, limit=1000)
        regime = market_uptrend_map(btc, 50)
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️ تعذّر بناء فلتر السوق: {exc}")

    def summarize(min_score, rr):
        tt = tw = 0
        tr = 0.0
        for s in series:
            res = backtest_trend_pullback_series(
                s, rr=rr, min_score=min_score, regime=regime, require_ema200=True)
            tt += res.n
            tw += res.wins
            tr += res.total_r
        wr = (tw / tt * 100.0) if tt else 0.0
        exp = (tr / tt) if tt else 0.0
        flag = "✅" if (exp > 0 and tt >= 20) else ("⚠️" if tt < 20 else "❌")
        print(f"{flag} درجة≥{min_score:>2.0f}  RR {rr:>3.1f} | صفقات {tt:>4} | "
              f"نجاح {wr:>5.1f}% | توقّع {exp:>+6.2f}R | إجمالي {tr:>+6.1f}R")
        return wr, exp, tt

    print("\n" + "=" * 62)
    print("الهدف: أعلى نسبة نجاح مع توقّع موجب وعدد صفقات ≥20 (✅)")
    print("-" * 62)
    best = None
    for rr in (1.5, 2.0):
        for th in (85.0, 88.0, 90.0, 92.0):
            wr, exp, tt = summarize(th, rr)
            if exp > 0 and tt >= 20 and (best is None or wr > best[0]):
                best = (wr, exp, tt, th, rr)
        print("-" * 62)
    print("=" * 62)
    if best:
        print(f"\n🏆 أعلى دقة رابحة: درجة≥{best[3]:.0f} + RR {best[4]:.1f} → "
              f"نجاح {best[0]:.1f}% بتوقّع {best[1]:+.2f}R على {best[2]} صفقة.")
    else:
        print("\nℹ️ لا تهيئة تجمع دقة عالية + توقّع موجب + عيّنة كافية — نبقى على الحالي.")
    return 0


def momentum_test(source: str, timeframe: str) -> int:
    """
    قارن الإعداد الحالي مقابل «+ فلتر الزخم القوي» (MACD + زخم سعري) بالأرقام.
    نفعّل الفلتر حيًّا فقط لو رفع نسبة النجاح/التوقّع مع عيّنة كافية.
    """
    symbols = resolve_symbols("crypto", "auto")[:BACKTEST_MAX_CRYPTO]
    print(f"⏳ اختبار فلتر الزخم على {len(symbols)} عملة ({timeframe})...")
    series = fetch_many(symbols, "crypto", "auto", timeframe, limit=1000)
    regime = None
    try:
        btc = fetch("BTC-USD", "crypto", "auto", timeframe, limit=1000)
        regime = market_uptrend_map(btc, 50)
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️ تعذّر بناء فلتر السوق: {exc}")

    def summarize(label, momentum):
        tt = tw = 0
        tr = 0.0
        for s in series:
            res = backtest_trend_pullback_series(
                s, rr=2.0, min_score=85.0, regime=regime,
                require_ema200=True, require_momentum=momentum)
            tt += res.n
            tw += res.wins
            tr += res.total_r
        wr = (tw / tt * 100.0) if tt else 0.0
        exp = (tr / tt) if tt else 0.0
        print(f"{label:>26} | صفقات {tt:>4} | نجاح {wr:>5.1f}% | "
              f"توقّع {exp:>+6.2f}R | إجمالي {tr:>+6.1f}R")
        return wr, exp, tt

    print("\n" + "=" * 60)
    base = summarize("الحالي (بلا فلتر زخم)", False)
    mom = summarize("+ فلتر الزخم القوي", True)
    print("=" * 60)
    print(
        f"\nالحكم: فلتر الزخم "
        + ("✅ يحسّن — يُنصح بتفعيله." if mom[1] > base[1] and mom[2] >= 15
           else "⚠️ لا يحسّن بوضوح (أو عيّنة صغيرة) — نبقى على الحالي.")
    )
    return 0


# عدد عملات أكبر للاختبار الموسّع لمسافة الوقف (عيّنة أكبر = ثقة أعلى)
STOPBUFFER_MAX_CRYPTO = 150


def stop_buffer_test(source: str, timeframe: str) -> int:
    """
    اختبار موسّع لمسافة تنفّس الوقف (ATR buffer): هل إبعاد الوقف عن قاع الارتداد
    بمضاعف ATR يقلّل الخروج المبكر «اتضرب ستوب وبعدها طلع للهدف» ويحسّن التوقّع؟

    لتكبير العيّنة نقيس على 150 عملة ونعرض جدولين:
      (أ) بدون فلتر السوق — عيّنة كبيرة تعزل تأثير مسافة الوقف نفسها بثقة إحصائية.
      (ب) مع فلتر السوق — الشرط الواقعي المطبَّق حيًّا (أصغر عيّنة في سوق هابط).
    نثق في القرار حين يتّفق الجدولان ويكون في (أ) عيّنة كافية (≥40 صفقة).
    """
    symbols = resolve_symbols("crypto", "auto")[:STOPBUFFER_MAX_CRYPTO]
    print(f"⏳ اختبار موسّع لمسافة الوقف على {len(symbols)} عملة ({timeframe})...")
    series = fetch_many(symbols, "crypto", "auto", timeframe, limit=1000)

    regime = None
    try:
        btc = fetch("BTC-USD", "crypto", "auto", timeframe, limit=1000)
        regime = market_uptrend_map(btc, 50)
        print(f"  ✅ خريطة حالة السوق من BTC ({len(regime)} شمعة).")
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️ تعذّر بناء فلتر السوق: {exc}")

    def summarize(buf: float, reg):
        tt = tw = 0
        tr = 0.0
        for s in series:
            res = backtest_trend_pullback_series(
                s, rr=2.0, min_score=85.0, regime=reg,
                require_ema200=True, stop_buffer_atr=buf,
            )
            tt += res.n
            tw += res.wins
            tr += res.total_r
        wr = (tw / tt * 100.0) if tt else 0.0
        exp = (tr / tt) if tt else 0.0
        print(f"  مسافة {buf:>4.2f}×ATR | صفقات {tt:>4} | نجاح {wr:>5.1f}% | "
              f"توقّع {exp:>+6.2f}R | إجمالي {tr:>+6.1f}R")
        return exp, tt, wr, buf

    buffers = (0.0, 0.25, 0.5, 0.75, 1.0, 1.5)

    def sweep(title, reg, min_n):
        print("\n" + "=" * 60)
        print(title)
        print("-" * 60)
        rows = [summarize(b, reg) for b in buffers]
        print("=" * 60)
        base = next((r for r in rows if r[3] == 0.0), None)
        valid = [r for r in rows if r[1] >= min_n]
        verdict = None
        if valid and base:
            best = max(valid, key=lambda r: r[0])
            if best[3] != 0.0 and best[0] > base[0] + 0.03:
                verdict = best[3]
                print(f"👉 الأفضل هنا: {best[3]:.2f}×ATR → {best[0]:+.2f}R "
                      f"(مقابل {base[0]:+.2f}R للملزوق) على {best[1]} صفقة.")
            else:
                print(f"👉 لا تحسّن مُعتَد به (الملزوق {base[0]:+.2f}R يكفي).")
        else:
            print("👉 عيّنة غير كافية للحكم في هذا الجدول.")
        return verdict

    v_no = sweep("(أ) بدون فلتر السوق — عيّنة كبيرة لعزل تأثير الوقف", None, 40)
    v_reg = sweep("(ب) مع فلتر السوق — الشرط الواقعي المطبَّق حيًّا", regime, 20)

    print("\n" + "#" * 60)
    if v_no and v_reg and abs(v_no - v_reg) <= 0.25:
        pick = round((v_no + v_reg) / 2, 2)
        print(f"✅ الجدولان متّفقان → مسافة ≈ {pick:.2f}×ATR تحسّن حقيقي وموثوق. "
              f"ثبّتها في TREND_STOP_BUFFER_ATR.")
    elif v_no:
        print(f"✅ العيّنة الكبيرة (أ) تؤكّد تحسّن مسافة {v_no:.2f}×ATR — إشارة قوية "
              f"رغم صِغَر عيّنة السوق الهابط. مرشّح جيّد للتثبيت.")
    elif v_reg:
        print(f"⚠️ فقط الجدول الواقعي (ب) أظهر تحسّنًا ({v_reg:.2f}×ATR) بعيّنة صغيرة — "
              f"مبشّر لكن ننتظر عيّنة أكبر قبل الجزم.")
    else:
        print("ℹ️ لا تحسّن مؤكّد — الوقف الملزوق (0.0) يبقى الخيار الآمن.")
    print("#" * 60)
    return 0


def breakout_test(source: str, timeframe: str) -> int:
    """
    قياس استراتيجية «اختراق الاتجاه» (Donchian breakout) — تنويع محترف مقترح.

    نقيسها على 1h و1d (بيانات يومية تاريخها أطول) مع فلتر السوق، ونقارنها
    بالاستراتيجية الرابحة الحالية. نضيفها للتنويع فقط لو توقّعها موجب وعيّنتها كافية.
    """
    from deals_bot.backtester import backtest_breakout_series

    frames = [timeframe, "1d"] if timeframe != "1d" else ["1h", "1d"]
    symbols = resolve_symbols("crypto", "auto")[:BACKTEST_MAX_CRYPTO]
    print(f"⏳ قياس اختراق الاتجاه على {len(symbols)} عملة، فريمات {frames}...")

    print("\n" + "=" * 64)
    print(f"{'فريم':>5} | {'إستراتيجية':>12} | {'صفقات':>6} | {'نجاح%':>6} | "
          f"{'توقّع/R':>8} | {'إجمالي':>8}")
    print("-" * 64)

    def run_frame(tf):
        try:
            series = fetch_many(symbols, "crypto", "auto", tf, limit=1000)
        except Exception as exc:  # noqa: BLE001
            print(f"{tf:>5} | تعذّر الجلب: {exc}")
            return
        regime = None
        try:
            btc = fetch("BTC-USD", "crypto", "auto", tf, limit=1000)
            regime = market_uptrend_map(btc, 50)
        except Exception:  # noqa: BLE001
            pass

        def tally(fn, **kw):
            tt = tw = 0
            tr = 0.0
            for s in series:
                res = fn(s, regime=regime, **kw)
                tt += res.n
                tw += res.wins
                tr += res.total_r
            wr = (tw / tt * 100.0) if tt else 0.0
            exp = (tr / tt) if tt else 0.0
            return tt, wr, exp, tr

        bo = tally(backtest_breakout_series, rr=2.0, min_score=85.0)
        tp = tally(backtest_trend_pullback_series, rr=2.0, min_score=85.0,
                   require_ema200=True,
                   stop_buffer_atr=getattr(config, "TREND_STOP_BUFFER_ATR", 0.5))
        print(f"{tf:>5} | {'اختراق':>12} | {bo[0]:>6} | {bo[1]:>6.1f} | "
              f"{bo[2]:>+8.2f} | {bo[3]:>+8.1f}")
        print(f"{tf:>5} | {'ارتداد(حالي)':>12} | {tp[0]:>6} | {tp[1]:>6.1f} | "
              f"{tp[2]:>+8.2f} | {tp[3]:>+8.1f}")
        print("-" * 64)
        return bo

    verdicts = {}
    for tf in frames:
        verdicts[tf] = run_frame(tf)
    print("=" * 64)
    good = [tf for tf, v in verdicts.items() if v and v[2] > 0 and v[0] >= 20]
    if good:
        print(f"\n✅ اختراق الاتجاه رابح وبعيّنة كافية على: {', '.join(good)} — "
              f"مرشّح قوي لإضافته كتنويع ثانٍ.")
    else:
        print("\n⚠️ اختراق الاتجاه لم يُثبت أفضلية موجبة بعيّنة كافية الآن — "
              "لا نضيفه (نبقى على الاستراتيجية الرابحة الوحيدة).")
    print(
        "\nℹ️ التنويع الحقيقي = استراتيجيتان مقاستان موجبتان وغير مترابطتين. "
        "نضيف فقط ما يجتاز القياس — تمامًا كما تفعل الصناديق المؤسسية."
    )
    return 0


def tf_sweep(source: str, timeframe: str) -> int:
    """
    قياس الفريمات الأعلى: هل فريم أكبر (4h/6h/1d) يرفع نسبة النجاح/الربح مقابل 1h؟
    نقيس نفس الإعداد الحيّ (درجة≥العتبة + فلتر السوق + EMA200 + مسافة وقف + RR)
    على كل فريم عبر الكون الكامل، ونطبع النجاح والتوقّع وعدد الصفقات.
    """
    frames = ["1h", "4h", "6h", "1d"]
    symbols = resolve_symbols("crypto", "auto")
    print(f"⏳ قياس الفريمات {frames} على {len(symbols)} عملة — الكون الكامل...")
    th = float(getattr(config, "TREND_MIN_SCORE", 82))
    buf = getattr(config, "TREND_STOP_BUFFER_ATR", 0.5)
    rr = float(getattr(config, "TREND_RR", 2.0))

    print("\n" + "=" * 62)
    print(f"{'فريم':>5} | {'صفقات':>6} | {'نجاح%':>6} | {'توقّع/R':>8} | {'إجمالي':>8} | الحكم")
    print("-" * 62)
    rows = []
    for tf in frames:
        try:
            series = fetch_many(symbols, "crypto", "auto", tf, limit=1000)
        except Exception as exc:  # noqa: BLE001
            print(f"{tf:>5} | تعذّر الجلب: {exc}")
            continue
        regime = None
        try:
            btc = fetch("BTC-USD", "crypto", "auto", tf, limit=1000)
            regime = market_uptrend_map(btc, 50)
        except Exception:  # noqa: BLE001
            pass
        tt = tw = 0
        tr = 0.0
        for s in series:
            res = backtest_trend_pullback_series(
                s, rr=rr, min_score=th, regime=regime,
                require_ema200=True, stop_buffer_atr=buf)
            tt += res.n
            tw += res.wins
            tr += res.total_r
        wr = (tw / tt * 100.0) if tt else 0.0
        exp = (tr / tt) if tt else 0.0
        ok = exp > 0 and tt >= 20
        verdict = "✅ رابح" if ok else ("⚠️ عيّنة صغيرة" if tt < 20 else "❌ خاسر")
        mark = " ← الحالي" if tf == "1h" else ""
        rows.append((tf, tt, wr, exp, ok))
        print(f"{tf:>5} | {tt:>6} | {wr:>6.1f} | {exp:>+8.2f} | {tr:>+8.1f} | {verdict}{mark}")
    print("=" * 62)
    valid = [r for r in rows if r[4]]
    cur = next((r for r in rows if r[0] == "1h"), None)
    if valid and cur:
        best_wr = max(valid, key=lambda r: r[2])
        best_exp = max(valid, key=lambda r: r[3])
        print(f"\n📈 أعلى نجاح: «{best_wr[0]}» ({best_wr[2]:.1f}%) | "
              f"💰 أعلى ربح: «{best_exp[0]}» ({best_exp[3]:+.2f}R)")
        if best_exp[0] == "1h":
            print("👉 الساعة (1h) تبقى الأفضل ربحًا — لا داعي للتغيير.")
        else:
            print(f"👉 «{best_exp[0]}» تتفوّق ربحًا على 1h — مرشّحة، لكن صفقاتها أندر ومدتها أطول.")
    print(
        "\nℹ️ الفريم الأعلى أقل ضجيجًا لكن صفقاته أندر بكثير ومدتها أطول. نختار الأعلى "
        "ربحًا (توقّع) بعيّنة كافية — لا الأعلى نجاحًا فقط."
    )
    return 0


def multi_tf(source: str, timeframe: str) -> int:
    """
    قياس الدمج متعدّد الفريمات: النتيجة المجمّعة (اتحاد) لفريمات TREND_TIMEFRAMES
    كما سيرسلها البوت فعلًا. نطبع لكل فريم + الإجمالي المدمج (صفقات/نجاح/توقّع/ربح).
    الهدف: إثبات أن دمج الفريمات الرابحة يزيد الفرص بلا تخفيف الجودة.
    """
    frames = getattr(config, "TREND_TIMEFRAMES", ["1h", "6h", "1d"])
    symbols = resolve_symbols("crypto", "auto")
    print(f"⏳ قياس الدمج متعدّد الفريمات {frames} على {len(symbols)} عملة...")
    th = float(getattr(config, "TREND_MIN_SCORE", 82))
    buf = getattr(config, "TREND_STOP_BUFFER_ATR", 0.5)
    rr = float(getattr(config, "TREND_RR", 2.0))
    rsi_max = getattr(config, "TREND_RSI_MAX", None)

    print("\n" + "=" * 62)
    print(f"{'فريم':>6} | {'صفقات':>6} | {'نجاح%':>6} | {'توقّع/R':>8} | {'إجمالي':>8}")
    print("-" * 62)
    g_tt = g_tw = 0
    g_tr = 0.0
    for tf in frames:
        try:
            series = fetch_many(symbols, "crypto", "auto", tf, limit=1000)
        except Exception as exc:  # noqa: BLE001
            print(f"{tf:>6} | تعذّر الجلب: {exc}")
            continue
        regime = None
        try:
            btc = fetch("BTC-USD", "crypto", "auto", tf, limit=1000)
            regime = market_uptrend_map(btc, 50)
        except Exception:  # noqa: BLE001
            pass
        tt = tw = 0
        tr = 0.0
        for s in series:
            res = backtest_trend_pullback_series(
                s, rr=rr, min_score=th, regime=regime,
                require_ema200=True, stop_buffer_atr=buf, rsi_max=rsi_max)
            tt += res.n
            tw += res.wins
            tr += res.total_r
        wr = (tw / tt * 100.0) if tt else 0.0
        exp = (tr / tt) if tt else 0.0
        print(f"{tf:>6} | {tt:>6} | {wr:>6.1f} | {exp:>+8.2f} | {tr:>+8.1f}")
        g_tt += tt
        g_tw += tw
        g_tr += tr
    print("-" * 62)
    g_wr = (g_tw / g_tt * 100.0) if g_tt else 0.0
    g_exp = (g_tr / g_tt) if g_tt else 0.0
    print(f"{'مدمج':>6} | {g_tt:>6} | {g_wr:>6.1f} | {g_exp:>+8.2f} | {g_tr:>+8.1f}")
    print("=" * 62)
    verdict = ("✅ الدمج رابح — فرص أكثر بلا تخفيف الجودة"
               if g_exp > 0 and g_tt >= 20 else "⚠️ راجع النتيجة")
    print(f"\n{verdict}")
    print(
        "\nℹ️ «مدمج» = اتحاد كل الفريمات (زي ما البوت هيبعت). التوقّع المدمج هو المتوسّط "
        "المرجّح بعدد الصفقات؛ الأهم أنه موجب وأن عدد الفرص أكبر من أي فريم لوحده."
    )
    return 0


def threshold_cmp(source: str, timeframe: str) -> int:
    """
    مقارنة العتبات (82 / 85 / 90) بالإعداد الحيّ الكامل على الكون الكامل.

    نفس فلاتر البوت (فلتر السوق + EMA200 + مسافة وقف + سقف RSI + RR) عبر كل
    العملات، عند كل عتبة — عشان القرار يكون بالأرقام: كل ما ترفع العتبة تقلّ
    الصفقات؛ نتأكّد إن التوقّع يفضل موجب وإن عدد الفرص لسه معقول.
    """
    symbols = resolve_symbols("crypto", "auto")
    buf = getattr(config, "TREND_STOP_BUFFER_ATR", 0.5)
    rr = float(getattr(config, "TREND_RR", 2.0))
    rsi_max = getattr(config, "TREND_RSI_MAX", None)
    print(f"⏳ مقارنة العتبات على {len(symbols)} عملة ({timeframe})...")
    series = fetch_many(symbols, "crypto", "auto", timeframe, limit=1000)
    regime = None
    try:
        btc = fetch("BTC-USD", "crypto", "auto", timeframe, limit=1000)
        regime = market_uptrend_map(btc, 50)
    except Exception:  # noqa: BLE001
        pass

    print("\n" + "=" * 64)
    print(f"{'عتبة':>6} | {'صفقات':>6} | {'نجاح%':>6} | {'توقّع/R':>8} | {'إجمالي':>8} | الحكم")
    print("-" * 64)
    rows = []
    for th in [82.0, 85.0, 90.0]:
        tt = tw = 0
        tr = 0.0
        for s in series:
            res = backtest_trend_pullback_series(
                s, rr=rr, min_score=th, regime=regime,
                require_ema200=True, stop_buffer_atr=buf, rsi_max=rsi_max)
            tt += res.n
            tw += res.wins
            tr += res.total_r
        wr = (tw / tt * 100.0) if tt else 0.0
        exp = (tr / tt) if tt else 0.0
        ok = exp > 0 and tt >= 20
        verdict = "✅ رابح" if ok else ("⚠️ عيّنة صغيرة" if tt < 20 else "❌ خاسر")
        cur = " ← المختار" if int(th) == int(getattr(config, "TREND_MIN_SCORE", 90)) else ""
        rows.append((th, tt, wr, exp, tr, ok))
        print(f"{th:>6.0f} | {tt:>6} | {wr:>6.1f} | {exp:>+8.2f} | {tr:>+8.1f} | {verdict}{cur}")
    print("=" * 64)
    chosen = next((r for r in rows if int(r[0]) == int(getattr(config, "TREND_MIN_SCORE", 90))), None)
    if chosen and chosen[1] < 20:
        print(f"\n⚠️ عند العتبة {int(chosen[0])}: {chosen[1]} صفقة فقط — عيّنة صغيرة "
              "وفرص نادرة جدًا. ممكن تعدّي أيام بلا أي صفقة.")
    print(
        "\nℹ️ العتبة الأعلى = صفقات أنقى لكن أندر بكثير. الأهم: التوقّع يفضل موجب "
        "وعدد الفرص يكفيك. لو الصفقات قلّت أوي، فكّر ترجع 85."
    )
    return 0


def rr_cmp(source: str, timeframe: str) -> int:
    """
    مقارنة بُعد الهدف (RR) بالإعداد الحيّ الكامل على الكون الكامل.

    نجيب لكل RR: نسبة الوصول للهدف (نجاح%) + التوقّع + الربح الإجمالي — عشان
    نختار «الأحسن» بالأرقام: الهدف الأقرب يوصل أكتر لكن ربحه أصغر، والأبعد
    يربح أكبر لكن يوصل أقل. الأحسن = أعلى ربح إجمالي بنسبة وصول معقولة.
    """
    symbols = resolve_symbols("crypto", "auto")
    th = float(getattr(config, "TREND_MIN_SCORE", 85))
    buf = getattr(config, "TREND_STOP_BUFFER_ATR", 0.5)
    rsi_max = getattr(config, "TREND_RSI_MAX", None)
    print(f"⏳ مقارنة بُعد الهدف (RR) على {len(symbols)} عملة ({timeframe})...")
    series = fetch_many(symbols, "crypto", "auto", timeframe, limit=1000)
    regime = None
    try:
        btc = fetch("BTC-USD", "crypto", "auto", timeframe, limit=1000)
        regime = market_uptrend_map(btc, 50)
    except Exception:  # noqa: BLE001
        pass

    print("\n" + "=" * 64)
    print(f"{'RR':>5} | {'صفقات':>6} | {'يوصل%':>6} | {'توقّع/R':>8} | {'إجمالي':>8} | الحكم")
    print("-" * 64)
    best = None
    for rr in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]:
        tt = tw = 0
        tr = 0.0
        for s in series:
            res = backtest_trend_pullback_series(
                s, rr=rr, min_score=th, regime=regime,
                require_ema200=True, stop_buffer_atr=buf, rsi_max=rsi_max)
            tt += res.n
            tw += res.wins
            tr += res.total_r
        wr = (tw / tt * 100.0) if tt else 0.0
        exp = (tr / tt) if tt else 0.0
        ok = exp > 0 and tt >= 20
        verdict = "✅ رابح" if ok else ("⚠️ عيّنة صغيرة" if tt < 20 else "❌ خاسر")
        cur = " ← الحالي" if abs(rr - float(getattr(config, "TREND_RR", 2.0))) < 0.01 else ""
        if ok and (best is None or tr > best[4]):
            best = (rr, tt, wr, exp, tr)
        print(f"{rr:>5.1f} | {tt:>6} | {wr:>6.1f} | {exp:>+8.2f} | {tr:>+8.1f} | {verdict}{cur}")
    print("=" * 64)
    if best:
        print(f"\n💰 أعلى ربح إجمالي: RR {best[0]:.1f} → {best[4]:+.1f}R "
              f"({best[1]} صفقة، توصل الهدف {best[2]:.0f}%).")
    print(
        "\nℹ️ الهدف الأقرب (RR أقل) يوصل أكتر لكن ربحه أصغر؛ الأبعد يربح أكبر لكن "
        "يوصل أقل. «الأحسن» = أعلى ربح إجمالي بعيّنة كافية — مع بقاء وقف الخسارة."
    )
    return 0


def pro_filter(source: str, timeframe: str) -> int:
    """
    قياس فلاتر «الاحترافية» فوق الإعداد الرابح الحالي — واحدة واحدة ثم مجمّعة.

    نقيس على الكون الكامل بالإطار المطلوب (افتراضي 1h — أكبر عيّنة) نفس الإعداد
    الحيّ (سكور≥العتبة + فلتر السوق + EMA200 + مسافة وقف + RR)، ونضيف كل فلتر
    احترافي على حدة عشان نعرف أيّهم يرفع التوقّع فعلًا قبل تفعيله:
      • سقف RSI (يرفض الارتداد الضعيف/التمدّد)
      • حد أدنى لميل الاتجاه (اتجاه قويّ الميل فقط)
      • القوة النسبية مقابل BTC (نشتري القادة فقط)
    """
    symbols = resolve_symbols("crypto", "auto")
    th = float(getattr(config, "TREND_MIN_SCORE", 82))
    buf = getattr(config, "TREND_STOP_BUFFER_ATR", 0.5)
    rr = float(getattr(config, "TREND_RR", 2.0))
    print(f"⏳ قياس الفلاتر الاحترافية على {len(symbols)} عملة ({timeframe})...")

    series = fetch_many(symbols, "crypto", "auto", timeframe, limit=1000)
    regime = None
    btc_ret = {}
    try:
        btc = fetch("BTC-USD", "crypto", "auto", timeframe, limit=1000)
        regime = market_uptrend_map(btc, 50)
        btc_ret = market_return_map(btc, 20)
    except Exception:  # noqa: BLE001
        pass

    variants = [
        ("الأساس (الحالي)", {}),
        ("+ سقف RSI ≤ 65", {"rsi_max": 65.0}),
        ("+ سقف RSI ≤ 68", {"rsi_max": 68.0}),
        ("+ ميل ≥ 0.10%", {"min_slope_pct": 0.10}),
        ("+ ميل ≥ 0.20%", {"min_slope_pct": 0.20}),
        ("+ أقوى من BTC", {"rel_strength": {"lookback": 20, "btc_ret": btc_ret}}),
        ("+ الثلاثة معًا", {"rsi_max": 68.0, "min_slope_pct": 0.10,
                            "rel_strength": {"lookback": 20, "btc_ret": btc_ret}}),
    ]

    print("\n" + "=" * 70)
    print(f"{'الفلتر':>18} | {'صفقات':>6} | {'نجاح%':>6} | {'توقّع/R':>8} | {'إجمالي':>8}")
    print("-" * 70)
    base_exp = None
    rows = []
    for name, kw in variants:
        tt = tw = 0
        tr = 0.0
        for s in series:
            res = backtest_trend_pullback_series(
                s, rr=rr, min_score=th, regime=regime,
                require_ema200=True, stop_buffer_atr=buf, **kw)
            tt += res.n
            tw += res.wins
            tr += res.total_r
        wr = (tw / tt * 100.0) if tt else 0.0
        exp = (tr / tt) if tt else 0.0
        if base_exp is None:
            base_exp = exp
        rows.append((name, tt, wr, exp, tr))
        print(f"{name:>18} | {tt:>6} | {wr:>6.1f} | {exp:>+8.2f} | {tr:>+8.1f}")
    print("=" * 70)

    # الحكم: أعلى توقّع بعيّنة كافية (≥30 صفقة) يتفوّق على الأساس بهامش واضح
    valid = [r for r in rows[1:] if r[1] >= 30]
    if valid:
        best = max(valid, key=lambda r: r[3])
        if best[3] > (base_exp or 0) + 0.03:
            print(f"\n✅ «{best[0]}» يرفع التوقّع من {base_exp:+.2f}R إلى {best[3]:+.2f}R "
                  f"({best[1]} صفقة) — مرشّح للتفعيل.")
        else:
            print(f"\nℹ️ لا فلتر يتفوّق على الأساس ({base_exp:+.2f}R) بهامش واضح وعيّنة كافية — "
                  "الأساس يبقى الأفضل (لا نعقّد بلا فائدة مقاسة).")
    else:
        print("\n⚠️ العيّنات بعد الفلاتر صغيرة — لا قرار موثوق.")
    print(
        "\nℹ️ نضيف فلترًا فقط لو رفع التوقّع بعيّنة كافية. تقليل الصفقات بلا رفع "
        "التوقّع = خسارة فرص، مش احتراف."
    )
    return 0


def tca(source: str, timeframe: str) -> int:
    """
    تحليل تكلفة الصفقة (TCA) — انضباط مؤسسي: هل ميزتنا تصمد بعد الرسوم الحقيقية؟

    نأخذ صفقات الإعداد الحيّ الكامل ونخصم من كل صفقة تكلفة ذهاب+عودة (رسوم +
    انزلاق) كنسبة من مسافة الوقف (R)، عند مستويات تكلفة واقعية لكل جهة. الرسوم
    ثابتة بالنسبة المئوية، فالوقف الواسع (6س/يومي) يمتصّها بسهولة بينما الوقف
    الضيّق (مضاربة) تأكله. نبيّن التوقّع الإجمالي مقابل الصافي بعد التكلفة.
    """
    symbols = resolve_symbols("crypto", "auto")
    th = float(getattr(config, "TREND_MIN_SCORE", 85))
    buf = getattr(config, "TREND_STOP_BUFFER_ATR", 0.5)
    rr = float(getattr(config, "TREND_RR", 2.0))
    base_kw = dict(
        rr=rr, min_score=th, require_ema200=True, stop_buffer_atr=buf,
        rsi_max=getattr(config, "TREND_RSI_MAX", 68.0),
        require_macd=getattr(config, "TREND_REQUIRE_MACD", False),
        stoch_max=getattr(config, "TREND_STOCH_MAX", None),
        fib_min=getattr(config, "TREND_FIB_MIN", None),
        fib_max=getattr(config, "TREND_FIB_MAX", None),
    )
    print(f"⏳ تحليل تكلفة الصفقة (TCA) على {len(symbols)} عملة ({timeframe})...")

    series = fetch_many(symbols, "crypto", "auto", timeframe, limit=1000)
    regime = None
    try:
        btc = fetch("BTC-USD", "crypto", "auto", timeframe, limit=1000)
        regime = market_uptrend_map(btc, 50)
    except Exception:  # noqa: BLE001
        pass

    # اجمع كل الصفقات مرة واحدة (entry/stop لحساب التكلفة نسبةً لـ R)
    trades = []
    for s in series:
        res = backtest_trend_pullback_series(s, regime=regime, **base_kw)
        trades.extend(res.trades)
    n = len(trades)
    if not n:
        print("لا صفقات لقياسها.")
        return 0
    gross = sum(t.result_r for t in trades) / n

    # متوسط مسافة الوقف كنسبة من السعر (يوضّح لماذا الفريم الأوسع أرخص نسبيًا)
    stop_pcts = [abs(t.entry - t.stop) / t.entry for t in trades if t.entry > 0]
    avg_stop_pct = (sum(stop_pcts) / len(stop_pcts) * 100.0) if stop_pcts else 0.0

    print("\n" + "=" * 70)
    print(f"صفقات: {n} | التوقّع الإجمالي (بلا تكلفة): {gross:+.3f}R | "
          f"متوسّط مسافة الوقف: {avg_stop_pct:.1f}% من السعر")
    print("-" * 70)
    print(f"{'تكلفة/جهة':>10} | {'تكلفة ذهاب+عودة (R)':>20} | {'التوقّع الصافي':>16}")
    print("-" * 70)
    for side_cost in (0.001, 0.003, 0.005, 0.006):     # 0.1% .. 0.6% لكل جهة
        cost_r_sum = 0.0
        net_sum = 0.0
        for t in trades:
            risk = abs(t.entry - t.stop)
            cost_r = (2 * side_cost * t.entry) / risk if risk > 0 else 0.0
            cost_r_sum += cost_r
            net_sum += t.result_r - cost_r
        avg_cost_r = cost_r_sum / n
        net_exp = net_sum / n
        flag = "✅ يصمد" if net_exp > 0.05 else ("⚠️ ضعيف" if net_exp > 0 else "❌ يُمحى")
        print(f"{side_cost*100:>8.1f}% | {avg_cost_r:>20.3f} | "
              f"{net_exp:>+13.3f}R  {flag}")
    print("=" * 70)
    print(
        "\nℹ️ الخلاصة: الرسوم ثابتة %، فكل ما اتّسع الوقف (6س/يومي) قلّت تكلفتها "
        "بالنسبة لـ R. لهذا مسار الاستثمار (وقف واسع) يصمد بعد الرسوم، بينما "
        "المضاربة (وقف ضيّق) تأكلها الرسوم — دليل إضافي لاختيارنا 6س/يومي."
    )
    return 0


def fibonacci(source: str, timeframe: str) -> int:
    """
    قياس فلتر فيبوناتشي: هل اشتراط أن يقع الارتداد في منطقة فيبوناتشي يرفع الربح؟

    نضيف على الإعداد الحيّ الكامل شرطًا: عمق ارتداد الصفقة (بالنسبة للموجة الصاعدة
    الأخيرة قاع→قمة) لازم يقع في منطقة فيبوناتشي (مثلاً 0.382–0.618 الذهبية). نقيس
    كل منطقة على الكون الكامل ونفعّل فقط ما يرفع التوقّع فعلًا (لا نعقّد بلا فائدة).
    """
    symbols = resolve_symbols("crypto", "auto")
    th = float(getattr(config, "TREND_MIN_SCORE", 85))
    buf = getattr(config, "TREND_STOP_BUFFER_ATR", 0.5)
    rr = float(getattr(config, "TREND_RR", 2.0))
    base_kw = dict(
        rr=rr, min_score=th, require_ema200=True, stop_buffer_atr=buf,
        rsi_max=getattr(config, "TREND_RSI_MAX", 68.0),
        require_macd=getattr(config, "TREND_REQUIRE_MACD", False),
        stoch_max=getattr(config, "TREND_STOCH_MAX", None),
    )
    print(f"⏳ قياس فلتر فيبوناتشي على {len(symbols)} عملة ({timeframe})...")

    series = fetch_many(symbols, "crypto", "auto", timeframe, limit=1000)
    regime = None
    try:
        btc = fetch("BTC-USD", "crypto", "auto", timeframe, limit=1000)
        regime = market_uptrend_map(btc, 50)
    except Exception:  # noqa: BLE001
        pass

    variants = [
        ("الأساس (بلا فيبو)", {}),
        ("منطقة 0.382–0.618 (ذهبية)", {"fib_min": 0.382, "fib_max": 0.618}),
        ("منطقة 0.500–0.786 (أعمق)", {"fib_min": 0.5, "fib_max": 0.786}),
        ("منطقة 0.236–0.618 (أوسع)", {"fib_min": 0.236, "fib_max": 0.618}),
        ("منطقة 0.382–0.786", {"fib_min": 0.382, "fib_max": 0.786}),
    ]

    print("\n" + "=" * 74)
    print(f"{'المنطقة':>26} | {'صفقات':>6} | {'نجاح%':>6} | {'توقّع/R':>8} | {'إجمالي':>8}")
    print("-" * 74)
    base_exp = None
    rows = []
    for name, kw in variants:
        tt = tw = 0
        tr = 0.0
        for s in series:
            res = backtest_trend_pullback_series(s, regime=regime, **base_kw, **kw)
            tt += res.n
            tw += res.wins
            tr += res.total_r
        wr = (tw / tt * 100.0) if tt else 0.0
        exp = (tr / tt) if tt else 0.0
        if base_exp is None:
            base_exp = exp
        rows.append((name, tt, wr, exp, tr))
        print(f"{name:>26} | {tt:>6} | {wr:>6.1f} | {exp:>+8.2f} | {tr:>+8.1f}")
    print("=" * 74)

    valid = [r for r in rows[1:] if r[1] >= 30]
    if valid:
        best = max(valid, key=lambda r: r[3])
        if best[3] > (base_exp or 0) + 0.03:
            print(f"\n✅ «{best[0]}» يرفع التوقّع من {base_exp:+.2f}R إلى {best[3]:+.2f}R "
                  f"({best[1]} صفقة) — مرشّح للتفعيل.")
        else:
            print(f"\nℹ️ لا منطقة فيبوناتشي تتفوّق على الأساس ({base_exp:+.2f}R) بهامش واضح "
                  "وعيّنة كافية — الأساس يبقى الأفضل (لا نضيف فيبو بلا فائدة مقاسة).")
    else:
        print("\n⚠️ العيّنات بعد فلتر فيبوناتشي صغيرة جدًا — لا قرار موثوق.")
    return 0


def reversal(source: str, timeframe: str) -> int:
    """
    قياس «الانعكاس» (MAE): كم تتحرّك الصفقة عكسك قبل ما تشتغل؟

    «زيرو انعكاس» مستحيل — كل صفقة (حتى الكسبانة) بتنزل شوية أولًا. نقيس على الكون
    الكامل بالإعداد الحيّ: توزيع أقصى انعكاس (MAE بمضاعفات الوقف R) للصفقات
    الكسبانة تحديدًا — عشان نعرف «النزول الطبيعي» اللي تحته بس تقلق، ونمنع الخروج
    المرعوب اللي بيخسّرك صفقة كانت هتكسب.
    """
    symbols = resolve_symbols("crypto", "auto")
    th = float(getattr(config, "TREND_MIN_SCORE", 85))
    buf = getattr(config, "TREND_STOP_BUFFER_ATR", 0.5)
    rr = float(getattr(config, "TREND_RR", 2.0))
    base_kw = dict(
        rr=rr, min_score=th, require_ema200=True, stop_buffer_atr=buf,
        rsi_max=getattr(config, "TREND_RSI_MAX", 68.0),
        require_macd=getattr(config, "TREND_REQUIRE_MACD", False),
        stoch_max=getattr(config, "TREND_STOCH_MAX", None),
    )
    print(f"⏳ قياس الانعكاس (MAE) على {len(symbols)} عملة ({timeframe})...")

    series = fetch_many(symbols, "crypto", "auto", timeframe, limit=1000)
    regime = None
    try:
        btc = fetch("BTC-USD", "crypto", "auto", timeframe, limit=1000)
        regime = market_uptrend_map(btc, 50)
    except Exception:  # noqa: BLE001
        pass

    win_mae, loss_mae = [], []
    for s in series:
        res = backtest_trend_pullback_series(s, regime=regime, **base_kw)
        for t in res.trades:
            (win_mae if t.won else loss_mae).append(t.mae_r)

    def _pct(vals, thr):
        return (sum(1 for v in vals if v <= thr) / len(vals) * 100.0) if vals else 0.0

    def _median(vals):
        if not vals:
            return 0.0
        sv = sorted(vals)
        m = len(sv) // 2
        return sv[m] if len(sv) % 2 else (sv[m - 1] + sv[m]) / 2.0

    nW = len(win_mae)
    print("\n" + "=" * 66)
    print(f"الصفقات الكسبانة: {nW} | الخاسرة: {len(loss_mae)}")
    print("-" * 66)
    if nW:
        print(f"  متوسط الانعكاس قبل الفوز: {sum(win_mae)/nW:+.2f}R "
              f"(الوسيط {_median(win_mae):.2f}R)")
        print(f"  أقصى انعكاس لصفقة كسبانة: {max(win_mae):.2f}R")
        print("  توزيع الصفقات الكسبانة حسب أقصى انعكاس:")
        print(f"    • انعكست أقل من 0.25R (شبه بدون انعكاس): {_pct(win_mae,0.25):.0f}%")
        print(f"    • انعكست أقل من 0.50R (نصف المسافة للوقف): {_pct(win_mae,0.50):.0f}%")
        print(f"    • انعكست أقل من 0.75R: {_pct(win_mae,0.75):.0f}%")
        print(f"    • انعكست أقل من 1.00R (لمست الوقف تقريبًا): {_pct(win_mae,1.0):.0f}%")
    print("=" * 66)
    print(
        "\nℹ️ القراءة: «زيرو انعكاس» غير موجود — لكن أغلب الصفقات الكسبانة بتنزل "
        "بمقدار محدود (وسيط الانعكاس) ثم تطلع. طالما الصفقة ما لمستش الوقف = طبيعية؛ "
        "الخروج المرعوب قبل الوقف هو اللي بيحوّل صفقة كسبانة لخسارة. سيبها للوقف/الهدف."
    )
    return 0


def breakeven(source: str, timeframe: str) -> int:
    """
    قياس «نقل الوقف لنقطة الدخول» (breakeven): يقلّل عدد الصفقات الخاسرة؟

    نقيس فوق الإعداد الحيّ الكامل (سكور + سوق + EMA200 + مسافة وقف + سقف RSI +
    فلتر المؤشرات MACD/Stochastic) نفس الاستراتيجية، مع نقل الوقف لنقطة الدخول
    بعد ربح R معيّن. نعدّ لكل مستوى: كسبانة / خاسرة فعلًا / خارجة بصفر (تعادل) +
    التوقّع، عشان نعرف: هل يقلّل الخسائر بلا خفض الربح؟ (يُفعَّل فقط لو نعم).
    """
    symbols = resolve_symbols("crypto", "auto")
    th = float(getattr(config, "TREND_MIN_SCORE", 85))
    buf = getattr(config, "TREND_STOP_BUFFER_ATR", 0.5)
    rr = float(getattr(config, "TREND_RR", 2.0))
    base_kw = dict(
        rr=rr, min_score=th, require_ema200=True, stop_buffer_atr=buf,
        rsi_max=getattr(config, "TREND_RSI_MAX", 68.0),
        require_macd=getattr(config, "TREND_REQUIRE_MACD", False),
        stoch_max=getattr(config, "TREND_STOCH_MAX", None),
    )
    print(f"⏳ قياس نقل الوقف لنقطة الدخول على {len(symbols)} عملة ({timeframe})...")

    series = fetch_many(symbols, "crypto", "auto", timeframe, limit=1000)
    regime = None
    try:
        btc = fetch("BTC-USD", "crypto", "auto", timeframe, limit=1000)
        regime = market_uptrend_map(btc, 50)
    except Exception:  # noqa: BLE001
        pass

    levels = [("الأساس (بلا نقل)", 0.0), ("breakeven @0.5R", 0.5),
              ("breakeven @1.0R", 1.0), ("breakeven @1.5R", 1.5)]

    print("\n" + "=" * 82)
    print(f"{'المستوى':>18} | {'صفقات':>6} | {'كسب':>5} | {'خسارة':>6} | "
          f"{'تعادل':>6} | {'نجاح%':>6} | {'توقّع/R':>8} | {'إجمالي':>8}")
    print("-" * 82)
    base_exp = None
    base_loss = None
    for name, be in levels:
        tt = wins = losses = scratch = 0
        tr = 0.0
        for s in series:
            res = backtest_trend_pullback_series(
                s, regime=regime, breakeven_r=be, **base_kw)
            for t in res.trades:
                tt += 1
                tr += t.result_r
                if t.won:
                    wins += 1
                elif t.result_r < 0:
                    losses += 1
                else:
                    scratch += 1
        wr = (wins / tt * 100.0) if tt else 0.0
        exp = (tr / tt) if tt else 0.0
        if base_exp is None:
            base_exp, base_loss = exp, losses
        print(f"{name:>18} | {tt:>6} | {wins:>5} | {losses:>6} | {scratch:>6} | "
              f"{wr:>6.1f} | {exp:>+8.2f} | {tr:>+8.1f}")
    print("=" * 82)
    print(
        "\nℹ️ «تعادل» = صفقات خرجت بصفر بدل خسارة (نقل الوقف أنقذها). القرار: نفعّل "
        "المستوى الذي يقلّل «خسارة» بوضوح مع بقاء «توقّع/R» ≥ الأساس (لا نضحّي بالربح "
        "مقابل تقليل شكل الخسائر). نقل الوقف لا يجعل صفقة واحدة تخسر — يقلّل عددها فقط."
    )
    return 0


def confluence(source: str, timeframe: str) -> int:
    """
    قياس «تلاقي المؤشرات»: أضف كل مؤشر شائع (MACD/OBV/Stochastic/MFI/Bollinger)
    كفلتر فوق الإعداد الرابح الحالي — واحدًا واحدًا ثم أفضلها مجمّعة — على الكون
    الكامل، عشان نعرف أيّهم يرفع التوقّع فعلًا (لا نكدّس مؤشرات بلا فائدة مقاسة).
    """
    symbols = resolve_symbols("crypto", "auto")
    th = float(getattr(config, "TREND_MIN_SCORE", 85))
    buf = getattr(config, "TREND_STOP_BUFFER_ATR", 0.5)
    rr = float(getattr(config, "TREND_RR", 2.0))
    rsi_cap = getattr(config, "TREND_RSI_MAX", 68.0)
    print(f"⏳ قياس تلاقي المؤشرات على {len(symbols)} عملة ({timeframe})...")

    series = fetch_many(symbols, "crypto", "auto", timeframe, limit=1000)
    regime = None
    try:
        btc = fetch("BTC-USD", "crypto", "auto", timeframe, limit=1000)
        regime = market_uptrend_map(btc, 50)
    except Exception:  # noqa: BLE001
        pass

    # الأساس = الإعداد الحيّ الكامل (سكور≥العتبة + سوق + EMA200 + مسافة وقف + سقف RSI)
    base_kw = dict(rr=rr, min_score=th, regime=regime,
                   require_ema200=True, stop_buffer_atr=buf, rsi_max=rsi_cap)
    variants = [
        ("الأساس (الحالي)", {}),
        ("+ MACD صاعد", {"require_macd": True}),
        ("+ OBV صاعد", {"require_obv": True}),
        ("+ Stochastic ≤ 80", {"stoch_max": 80.0}),
        ("+ Stochastic ≤ 70", {"stoch_max": 70.0}),
        ("+ MFI 40–85", {"mfi_min": 40.0, "mfi_max": 85.0}),
        ("+ داخل بولنجر", {"require_bb_inside": True}),
    ]

    print("\n" + "=" * 72)
    print(f"{'الفلتر':>20} | {'صفقات':>6} | {'نجاح%':>6} | {'توقّع/R':>8} | {'إجمالي':>8}")
    print("-" * 72)
    base_exp = None
    rows = []
    for name, kw in variants:
        tt = tw = 0
        tr = 0.0
        for s in series:
            res = backtest_trend_pullback_series(s, **base_kw, **kw)
            tt += res.n
            tw += res.wins
            tr += res.total_r
        wr = (tw / tt * 100.0) if tt else 0.0
        exp = (tr / tt) if tt else 0.0
        if base_exp is None:
            base_exp = exp
        rows.append((name, tt, wr, exp, tr, kw))
        print(f"{name:>20} | {tt:>6} | {wr:>6.1f} | {exp:>+8.2f} | {tr:>+8.1f}")

    # جرّب دمج كل الفلاتر اللي تفوّقت على الأساس (بعيّنة كافية) معًا
    winners = [r for r in rows[1:] if r[1] >= 30 and r[3] > (base_exp or 0) + 0.02]
    if len(winners) >= 2:
        combo = {}
        for r in winners:
            combo.update(r[5])
        tt = tw = 0
        tr = 0.0
        for s in series:
            res = backtest_trend_pullback_series(s, **base_kw, **combo)
            tt += res.n
            tw += res.wins
            tr += res.total_r
        wr = (tw / tt * 100.0) if tt else 0.0
        exp = (tr / tt) if tt else 0.0
        rows.append(("+ أفضلها مجمّعة", tt, wr, exp, tr, combo))
        print(f"{'+ أفضلها مجمّعة':>20} | {tt:>6} | {wr:>6.1f} | {exp:>+8.2f} | {tr:>+8.1f}")
    print("=" * 72)

    valid = [r for r in rows[1:] if r[1] >= 30]
    if valid:
        best = max(valid, key=lambda r: r[3])
        if best[3] > (base_exp or 0) + 0.03:
            print(f"\n✅ «{best[0]}» يرفع التوقّع من {base_exp:+.2f}R إلى {best[3]:+.2f}R "
                  f"({best[1]} صفقة) — مرشّح للتفعيل الحيّ.")
        else:
            print(f"\nℹ️ لا مؤشر يتفوّق على الأساس ({base_exp:+.2f}R) بهامش واضح وعيّنة كافية. "
                  "المؤشرات موجودة كلها بالفعل — لكن حشرها شرطًا لا يرفع الربح (overfit).")
    else:
        print("\n⚠️ العيّنات بعد الفلاتر صغيرة جدًا — لا قرار موثوق (المؤشرات تشدّد أكثر من اللازم).")
    print("\nℹ️ الخلاصة: «صفقة ممتازة» = مؤشرات مقاسة إنها ترفع الربح، مش أكبر عدد مؤشرات.")
    return 0


def frame_sweep(source: str, timeframe: str) -> int:
    """
    قياس متعدد الفريمات: يجرّب نفس الإعداد الرابح (درجة≥85 + فلتر السوق + EMA200 +
    مسافة وقف 0.5×ATR + RR 2) على 15m و30m و1h، ويطبع التوقّع لكل فريم — عشان
    نعرف أنهي فريمات تستاهل الدخول فعلًا قبل ما نفعّل البحث متعدد الفريمات.
    """
    frames = ["15m", "30m", "1h"]
    symbols = resolve_symbols("crypto", "auto")[:BACKTEST_MAX_CRYPTO]
    print(f"⏳ قياس الفريمات {frames} على {len(symbols)} عملة...")

    buf = getattr(config, "TREND_STOP_BUFFER_ATR", 0.5)
    print("\n" + "=" * 62)
    print(f"{'فريم':>6} | {'صفقات':>6} | {'نجاح%':>6} | {'توقّع/R':>8} | "
          f"{'إجمالي':>8} | الحكم")
    print("-" * 62)
    verdicts = {}
    for tf in frames:
        try:
            series = fetch_many(symbols, "crypto", "auto", tf, limit=1000)
        except Exception as exc:  # noqa: BLE001
            print(f"{tf:>6} | تعذّر الجلب: {exc}")
            continue
        regime = None
        try:
            btc = fetch("BTC-USD", "crypto", "auto", tf, limit=1000)
            regime = market_uptrend_map(btc, 50)
        except Exception:  # noqa: BLE001
            pass
        tt = tw = 0
        tr = 0.0
        for s in series:
            res = backtest_trend_pullback_series(
                s, rr=2.0, min_score=85.0, regime=regime,
                require_ema200=True, stop_buffer_atr=buf)
            tt += res.n
            tw += res.wins
            tr += res.total_r
        wr = (tw / tt * 100.0) if tt else 0.0
        exp = (tr / tt) if tt else 0.0
        ok = exp > 0 and tt >= 20
        verdict = "✅ رابح" if ok else ("⚠️ عيّنة صغيرة" if tt < 20 else "❌ خاسر")
        verdicts[tf] = (exp, tt, ok)
        print(f"{tf:>6} | {tt:>6} | {wr:>6.1f} | {exp:>+8.2f} | {tr:>+8.1f} | {verdict}")
    print("=" * 62)
    winners = [tf for tf, (e, n, ok) in verdicts.items() if ok]
    if winners:
        print(f"\n✅ فريمات رابحة نثق بها للدخول: {', '.join(winners)}")
    else:
        print("\n⚠️ لا فريم بعيّنة كافية + توقّع موجب الآن — 1h يبقى الأساس المُثبت.")
    print(
        "\nℹ️ نفعّل البحث متعدد الفريمات على الفريمات الرابحة فقط. الفريمات الأقصر "
        "أسرع للهدف لكنها غالبًا أكثر ضجيجًا — لذلك نقيس قبل أن نثق."
    )
    return 0


def pipeline_diag(source: str, timeframe: str) -> int:
    """
    تشخيص حيّ: ليه البوت الورقي مش بيفتح صفقات؟ يمرّر كل عملة على نفس خط القرار
    (evaluate) المستخدَم في التداول الورقي، ويعدّ أين تتوقّف كل عملة بالظبط:
      • لا إعداد اتجاه+ارتداد أصلًا
      • درجة AI أقل من الحد
      • فشل تأكيد 15m
      • رُفضت في العائد/المخاطرة
      • APPROVED (كانت هتُفتح)
    فيبان الاختناق الحقيقي بدل التخمين.
    """
    from deals_bot import indicators as ind
    from deals_bot.pipeline import (APPROVED, NO_TRADE, REJECTED, WAIT,
                                    _risk_engine, evaluate)
    from deals_bot.risk_engine import DailyState

    # نفس الكون الكامل الذي يتداوله البوت الورقي فعليًا (كل عملات Coinbase) — بلا اقتصاص.
    symbols = resolve_symbols("crypto", "auto")
    print(f"⏳ تشخيص خط القرار على {len(symbols)} عملة (كل الكون، {timeframe})...")

    # حالة السوق العامة (BTC فوق/تحت متوسّطه) — للسياق فقط
    try:
        btc = fetch("BTC-USD", "crypto", "auto", timeframe, limit=300)
        e50 = ind.ema(btc.closes(), 50)
        px = btc.closes()[-1]
        regime = "صاعد 🟢" if (e50 and px > e50) else "هابط 🔴"
        print(f"  🧭 حالة السوق (BTC): {regime}  (السعر {px:.0f} مقابل EMA50 "
              f"{e50:.0f})" if e50 else f"  🧭 حالة السوق (BTC): {regime}")
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️ تعذّر جلب حالة BTC: {exc}")

    engine = _risk_engine()
    equity = getattr(config, "ACCOUNT_BALANCE", 1000.0)
    daily = DailyState(starting_equity=equity, current_equity=equity,
                       trades_today=0, consecutive_losses=0, open_positions=0)

    tally = {NO_TRADE: 0, WAIT: 0, REJECTED: 0, APPROVED: 0}
    no_setup = 0
    low_score = 0
    confirm_fail = 0
    approved_syms = []
    scores = []

    for sym in symbols:
        try:
            base = fetch(sym, "crypto", "auto", timeframe, limit=300)
        except Exception:  # noqa: BLE001
            continue
        try:
            conf = fetch(sym, "crypto", "auto", "15m", limit=60)
        except Exception:  # noqa: BLE001
            conf = None
        dec = evaluate(base, equity, daily, conf, engine)
        tally[dec.status] = tally.get(dec.status, 0) + 1
        if dec.ai_score:
            scores.append(dec.ai_score)
        joined = " | ".join(dec.reasons)
        if "لا يوجد اتجاه صاعد" in joined:
            no_setup += 1
        elif "درجة AI <" in joined:
            low_score += 1
        elif dec.status == WAIT and dec.ai_score >= getattr(config, "AI_APPROVE_SCORE", 80):
            confirm_fail += 1
        if dec.status == APPROVED:
            approved_syms.append((sym, dec.ai_score))

    print("\n" + "=" * 58)
    print("أين تتوقّف كل عملة في خط القرار؟")
    print("-" * 58)
    print(f"  ⛔ لا يوجد اتجاه صاعد + ارتداد صالح : {no_setup}")
    print(f"  ⛔ درجة AI أقل من الحد الأدنى        : {low_score}")
    print(f"  ⏳ نجحت الدرجة لكن فشل تأكيد 15m     : {confirm_fail}")
    print(f"  ❌ رُفضت في العائد/المخاطرة          : {tally.get(REJECTED,0)}")
    print(f"  ⏳ إجمالي WAIT (درجة/تأكيد)          : {tally.get(WAIT,0)}")
    print(f"  ✅ APPROVED (كانت ستُفتح)            : {tally.get(APPROVED,0)}")
    print("=" * 58)
    if scores:
        scores.sort(reverse=True)
        top = ", ".join(f"{s:.0f}" for s in scores[:8])
        print(f"  أعلى درجات AI ظهرت: {top}  (الحد للفتح ≥"
              f"{getattr(config,'AI_APPROVE_SCORE',80):.0f})")
    if approved_syms:
        print("  ✅ عملات كانت ستُفتح الآن:")
        for s, sc in approved_syms:
            print(f"     {s:<12} AI {sc:.0f}")
    else:
        print("  ℹ️ لا عملة تجتاز كل البوّابات الآن — لذلك السجل الورقي فاضي.")
    print(
        "\nℹ️ الخلاصة: البوت شغّال بس بيرفض يدخل عشان الشروط صارمة (اتجاه+ارتداد "
        "+ درجة≥80 + تأكيد 15m + عائد≥2). ده بيحمي السجل من صفقات ضعيفة."
    )
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="باك-تِست لاستراتيجية بوت الصفقات.")
    p.add_argument("--market", "-m", choices=["crypto", "stocks", "forex", "all"], default="crypto")
    p.add_argument("--source", "-s", choices=["yfinance", "binance"], default=config.DEFAULT_SOURCE)
    p.add_argument("--timeframe", "-t", choices=["1m", "5m", "15m", "1h", "6h", "1d"], default="1h")
    p.add_argument(
        "--strategy",
        choices=["signals", "prepump", "trend", "compare", "trendsweep",
                 "optimize", "walkforward", "short", "precision", "momentum",
                 "stopbuffer", "diag", "framesweep", "breakout", "tfsweep",
                 "multitf", "profilter", "confluence", "breakeven",
                 "reversal", "fibonacci", "tca", "thresholds", "rrcmp"],
        default="signals",
        help="signals=إشارات شراء/بيع؛ prepump=ما قبل الاندفاع؛ "
        "trend=ارتداد داخل اتجاه صاعد؛ compare=قارن prepump مقابل trend؛ "
        "trendsweep=اختبار الانتقائية + فلتر السوق؛ "
        "optimize=اختر أفضل RR وفلتر EMA200؛ "
        "walkforward=اختبار خارج العيّنة (تعميم الأفضلية)",
    )
    args = p.parse_args(argv)
    if args.strategy == "compare":
        print("\n### استراتيجية ما قبل الاندفاع (prepump) ###")
        run(args.market, args.source, args.timeframe, "prepump")
        print("\n\n### استراتيجية الارتداد داخل الاتجاه (trend) ###")
        run(args.market, args.source, args.timeframe, "trend")
        return 0
    if args.strategy == "trendsweep":
        return trend_sweep(args.source, args.timeframe)
    if args.strategy == "optimize":
        return optimize(args.source, args.timeframe)
    if args.strategy == "walkforward":
        return walk_forward_run(args.source, args.timeframe)
    if args.strategy == "short":
        return short_test(args.source, args.timeframe)
    if args.strategy == "precision":
        return precision_test(args.source, args.timeframe)
    if args.strategy == "momentum":
        return momentum_test(args.source, args.timeframe)
    if args.strategy == "stopbuffer":
        return stop_buffer_test(args.source, args.timeframe)
    if args.strategy == "diag":
        return pipeline_diag(args.source, args.timeframe)
    if args.strategy == "framesweep":
        return frame_sweep(args.source, args.timeframe)
    if args.strategy == "tfsweep":
        return tf_sweep(args.source, args.timeframe)
    if args.strategy == "multitf":
        return multi_tf(args.source, args.timeframe)
    if args.strategy == "profilter":
        return pro_filter(args.source, args.timeframe)
    if args.strategy == "confluence":
        return confluence(args.source, args.timeframe)
    if args.strategy == "breakeven":
        return breakeven(args.source, args.timeframe)
    if args.strategy == "reversal":
        return reversal(args.source, args.timeframe)
    if args.strategy == "fibonacci":
        return fibonacci(args.source, args.timeframe)
    if args.strategy == "tca":
        return tca(args.source, args.timeframe)
    if args.strategy == "thresholds":
        return threshold_cmp(args.source, args.timeframe)
    if args.strategy == "rrcmp":
        return rr_cmp(args.source, args.timeframe)
    if args.strategy == "breakout":
        return breakout_test(args.source, args.timeframe)
    return run(args.market, args.source, args.timeframe, args.strategy)


if __name__ == "__main__":
    sys.exit(main())

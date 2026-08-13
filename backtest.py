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


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="باك-تِست لاستراتيجية بوت الصفقات.")
    p.add_argument("--market", "-m", choices=["crypto", "stocks", "forex", "all"], default="crypto")
    p.add_argument("--source", "-s", choices=["yfinance", "binance"], default=config.DEFAULT_SOURCE)
    p.add_argument("--timeframe", "-t", choices=["1m", "5m", "15m", "1h", "6h", "1d"], default="1h")
    p.add_argument(
        "--strategy",
        choices=["signals", "prepump", "trend", "compare", "trendsweep",
                 "optimize", "walkforward", "short", "precision"],
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
    return run(args.market, args.source, args.timeframe, args.strategy)


if __name__ == "__main__":
    sys.exit(main())

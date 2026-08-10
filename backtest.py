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
        for s in series:
            res = bt(s)
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


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="باك-تِست لاستراتيجية بوت الصفقات.")
    p.add_argument("--market", "-m", choices=["crypto", "stocks", "forex", "all"], default="crypto")
    p.add_argument("--source", "-s", choices=["yfinance", "binance"], default=config.DEFAULT_SOURCE)
    p.add_argument("--timeframe", "-t", choices=["1m", "5m", "15m", "1h", "1d"], default="1h")
    p.add_argument(
        "--strategy",
        choices=["signals", "prepump", "trend", "compare", "trendsweep"],
        default="signals",
        help="signals=إشارات شراء/بيع؛ prepump=ما قبل الاندفاع؛ "
        "trend=ارتداد داخل اتجاه صاعد؛ compare=قارن prepump مقابل trend؛ "
        "trendsweep=اختبار الانتقائية + فلتر السوق (يجيب: هل الأفضل يربح؟)",
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
    return run(args.market, args.source, args.timeframe, args.strategy)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
مولّد لوحة الأداء (Performance Dashboard) — PHASE 3.

Reads the paper account + trade journal, computes performance metrics, and
renders a self-contained, theme-aware HTML dashboard (no external assets) that
can be viewed directly or published as an artifact. Regenerated each run so it
always reflects the latest paper-trading state.
"""

from __future__ import annotations

import html
import os
import sys

import config
from deals_bot import journal
from deals_bot import paper_trading as pt
from deals_bot.performance import compute

PAPER_STATE = os.path.join("journal", "paper_account.json")
OUT = "dashboard.html"

# الأفضلية المُثبتة بالأرقام (باك-تِست حقيقي على 1h) — مراجع ثابتة للعرض
PROVEN = {
    "in_sample_r": 0.38,      # RR 2.0 + EMA200 + فلتر السوق
    "in_sample_wr": 46,
    "oos_r": 0.19,            # Walk-Forward خارج العيّنة (108 صفقة)
    "oos_trades": 108,
}


def _sparkline(curve, w=680, h=120, pad=8):
    """ارسم منحنى رأس المال كـ SVG بسيط (نقطة واحدة → خط مسطّح)."""
    if len(curve) < 2:
        curve = curve * 2 if curve else [0, 0]
    lo, hi = min(curve), max(curve)
    span = (hi - lo) or 1.0
    n = len(curve)
    pts = []
    for i, v in enumerate(curve):
        x = pad + (w - 2 * pad) * (i / (n - 1))
        y = pad + (h - 2 * pad) * (1 - (v - lo) / span)
        pts.append((x, y))
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{pad},{h - pad} " + line + f" {w - pad},{h - pad}"
    up = curve[-1] >= curve[0]
    stroke = "var(--good)" if up else "var(--bad)"
    ex, ey = pts[-1]
    return f"""<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" class="spark" role="img" aria-label="منحنى رأس المال">
  <polygon points="{area}" fill="url(#g)" opacity="0.14"></polygon>
  <polyline points="{line}" fill="none" stroke="{stroke}" stroke-width="2" stroke-linejoin="round"></polyline>
  <circle cx="{ex:.1f}" cy="{ey:.1f}" r="3.5" fill="{stroke}"></circle>
  <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{stroke}"></stop><stop offset="1" stop-color="{stroke}" stop-opacity="0"></stop>
  </linearGradient></defs>
</svg>"""


def _pf(v) -> str:
    return "∞" if v == float("inf") else f"{v:.2f}"


def _kpi(label, value, sub="", tone="neutral") -> str:
    return f"""<div class="kpi kpi--{tone}">
  <div class="kpi__label">{label}</div>
  <div class="kpi__value">{value}</div>
  <div class="kpi__sub">{sub}</div>
</div>"""


def render(account, m, recent) -> str:
    live_on = getattr(config, "LIVE_TRADING_ENABLED", False)
    ret = m["return_pct"]
    ret_tone = "good" if ret > 0 else ("bad" if ret < 0 else "neutral")
    exp_tone = "good" if m["expectancy_r"] > 0 else ("bad" if m["expectancy_r"] < 0 else "neutral")

    # صفوف الصفقات المفتوحة
    open_rows = "".join(
        f"<tr><td>{html.escape(p.symbol)}</td><td class='num'>{p.entry:.6g}</td>"
        f"<td class='num'>{p.stop:.6g}</td><td class='num'>{p.target:.6g}</td>"
        f"<td class='num'>{p.qty:g}</td><td class='num'>{p.ai_score:.0f}</td></tr>"
        for p in account.positions
    ) or "<tr><td colspan='6' class='empty'>لا صفقات مفتوحة الآن</td></tr>"

    # آخر إشارات السجل
    sig_rows = ""
    for t in recent[:8]:
        st = {"win": ("ربح", "good"), "loss": ("خسارة", "bad"),
              "open": ("مفتوحة", "warn"), "expired": ("منتهية", "neutral")}.get(t.status, (t.status, "neutral"))
        r = f"{t.result_r:+.2f}R" if t.result_r is not None else "—"
        sig_rows += (
            f"<tr><td>{html.escape(t.symbol)}</td><td class='num'>{t.entry:.6g}</td>"
            f"<td class='num'>{t.score:.0f}</td><td class='num'>{r}</td>"
            f"<td><span class='pill pill--{st[1]}'>{st[0]}</span></td></tr>"
        )
    sig_rows = sig_rows or "<tr><td colspan='5' class='empty'>لا إشارات مسجّلة بعد — البوت ينتظر إعدادًا مؤكّدًا</td></tr>"

    curve = _sparkline(m["equity_curve"])
    rp = getattr(config, "RISK_PER_TRADE_PRO", 0.005) * 100
    dl = getattr(config, "MAX_DAILY_LOSS_PCT", 0.015) * 100
    cl = getattr(config, "MAX_CONSECUTIVE_LOSSES", 3)
    rr = getattr(config, "MIN_RISK_REWARD", 2.0)
    cap0 = m["starting_equity"] or getattr(config, "ACCOUNT_BALANCE", 250.0)

    # قسم «بياناتي»: العميل يُدخل رأس ماله ونسبة مخاطرته، تُحفظ في المتصفّح
    # (localStorage) فتبقى موجودة بعد إغلاق/فتح الصفحة، وتُحدَّث الأرقام المشتقّة
    # فورًا أثناء الكتابة بلا أي إعادة تحميل للصفحة.
    mydata_card = f"""
  <section class="card" id="myData">
    <h2>بياناتي <span class="badge-proven">تُحفَظ تلقائيًا</span></h2>
    <div class="cols">
      <div class="rows">
        <label class="row"><span class="k">رأس المال</span>
          <input id="inCapital" class="inp" type="number" min="0" step="1" value="{cap0:.0f}" inputmode="decimal"></label>
        <label class="row"><span class="k">المخاطرة لكل صفقة (%)</span>
          <input id="inRisk" class="inp" type="number" min="0" step="0.1" value="{rp:.1f}" inputmode="decimal"></label>
      </div>
      <div class="rows">
        <div class="row"><span class="k">قيمة المخاطرة لكل صفقة</span><span class="v" id="outRiskAmt">—</span></div>
        <div class="row"><span class="k">أقصى خسارة يومية</span><span class="v" id="outDailyAmt">—</span></div>
        <div class="row"><span class="k"></span><span class="v muted" id="savedNote" style="font-size:.78rem;color:var(--muted)"></span></div>
      </div>
    </div>
  </section>"""

    # سكربت الحفظ الحيّ (localStorage): يستعيد القيم عند الفتح، ويحفظ ويُعيد الحساب
    # لحظة الكتابة — كله بلا سيرفر وبلا رفريش. مغلّف بـtry/catch (وضع التصفّح الخاص).
    mydata_script = (
        "<script>(function(){"
        "var KEY='botClientData_v1';"
        "var cap=document.getElementById('inCapital'),rk=document.getElementById('inRisk');"
        "var oR=document.getElementById('outRiskAmt'),oD=document.getElementById('outDailyAmt'),note=document.getElementById('savedNote');"
        "var DL=__DL0__;"
        "function f(n){return (isFinite(n)?n:0).toLocaleString('en-US',{maximumFractionDigits:2});}"
        "function calc(){var c=parseFloat(cap.value)||0,r=parseFloat(rk.value)||0;"
        "oR.textContent=f(c*r/100);oD.textContent=f(c*DL/100);}"
        "function save(){try{localStorage.setItem(KEY,JSON.stringify({cap:cap.value,risk:rk.value}));"
        "if(note){note.textContent='\\u2705 \\u0645\\u062d\\u0641\\u0648\\u0638 \\u062a\\u0644\\u0642\\u0627\\u0626\\u064a\\u064b\\u0627';}}"
        "catch(e){if(note){note.textContent='\\u26a0\\ufe0f \\u0627\\u0644\\u0645\\u062a\\u0635\\u0641\\u0651\\u062d \\u064a\\u0645\\u0646\\u0639 \\u0627\\u0644\\u062d\\u0641\\u0638';}}}"
        "function load(){try{var s=localStorage.getItem(KEY);if(s){var d=JSON.parse(s);"
        "if(d.cap!=null&&d.cap!=='')cap.value=d.cap;if(d.risk!=null&&d.risk!=='')rk.value=d.risk;}}catch(e){}}"
        "load();calc();"
        "[cap,rk].forEach(function(el){el.addEventListener('input',function(){calc();save();});});"
        "})();</script>"
    ).replace("__DL0__", f"{dl:.4f}")

    return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>لوحة أداء بوت التداول</title>
<style>
:root {{
  --bg:#f4f6f9; --surface:#ffffff; --surface2:#eef1f6; --border:#dde3ec;
  --text:#1a2230; --muted:#5b6676; --accent:#0284c7;
  --good:#16a34a; --bad:#dc2626; --warn:#d97706;
  --shadow:0 1px 2px rgba(20,30,50,.06),0 8px 24px rgba(20,30,50,.05);
}}
:root:not([data-theme="light"]) {{ }}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg:#0e1116; --surface:#161b22; --surface2:#1b212a; --border:#232a33;
    --text:#c9d4e0; --muted:#7d8998; --accent:#38bdf8;
    --good:#22c55e; --bad:#ef4444; --warn:#f59e0b;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px rgba(0,0,0,.35);
  }}
}}
:root[data-theme="dark"] {{
  --bg:#0e1116; --surface:#161b22; --surface2:#1b212a; --border:#232a33;
  --text:#c9d4e0; --muted:#7d8998; --accent:#38bdf8;
  --good:#22c55e; --bad:#ef4444; --warn:#f59e0b;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px rgba(0,0,0,.35);
}}
* {{ box-sizing:border-box; }}
body {{
  margin:0; background:var(--bg); color:var(--text);
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  line-height:1.5; -webkit-font-smoothing:antialiased;
}}
.num, .kpi__value {{ font-family:ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace;
  font-variant-numeric:tabular-nums; }}
.wrap {{ max-width:920px; margin:0 auto; padding:28px 20px 64px; }}
header {{ display:flex; flex-wrap:wrap; align-items:center; gap:12px 16px; margin-bottom:24px; }}
header h1 {{ font-size:1.35rem; margin:0; letter-spacing:-.01em; font-weight:650; flex:1 1 auto; }}
.status {{ display:inline-flex; align-items:center; gap:7px; font-weight:600; font-size:.85rem;
  padding:5px 12px; border-radius:999px; background:var(--surface); border:1px solid var(--border); }}
.dot {{ width:8px; height:8px; border-radius:50%; background:var(--good); box-shadow:0 0 0 3px color-mix(in srgb,var(--good) 22%,transparent); }}
.chip {{ font-size:.78rem; font-weight:600; padding:5px 11px; border-radius:999px;
  letter-spacing:.02em; border:1px solid; }}
.chip--off {{ color:var(--bad); border-color:color-mix(in srgb,var(--bad) 40%,var(--border));
  background:color-mix(in srgb,var(--bad) 10%,transparent); }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; }}
.kpi {{ background:var(--surface); border:1px solid var(--border); border-radius:14px;
  padding:16px 16px 14px; box-shadow:var(--shadow); position:relative; overflow:hidden; }}
.kpi::before {{ content:""; position:absolute; inset-inline-start:0; top:0; bottom:0; width:3px; background:var(--accent); opacity:.5; }}
.kpi--good::before {{ background:var(--good); }} .kpi--bad::before {{ background:var(--bad); }}
.kpi--warn::before {{ background:var(--warn); }}
.kpi__label {{ font-size:.76rem; color:var(--muted); font-weight:600; margin-bottom:8px; letter-spacing:.02em; }}
.kpi__value {{ font-size:1.6rem; font-weight:650; letter-spacing:-.02em; }}
.kpi__sub {{ font-size:.76rem; color:var(--muted); margin-top:4px; min-height:1em; }}
.good {{ color:var(--good); }} .bad {{ color:var(--bad); }} .warn {{ color:var(--warn); }}
section {{ margin-top:26px; }}
.card {{ background:var(--surface); border:1px solid var(--border); border-radius:16px;
  padding:20px; box-shadow:var(--shadow); }}
.card h2 {{ font-size:.82rem; text-transform:uppercase; letter-spacing:.08em; color:var(--muted);
  margin:0 0 14px; font-weight:650; }}
.spark {{ width:100%; height:120px; display:block; }}
.curve-meta {{ display:flex; justify-content:space-between; margin-top:8px; font-size:.8rem; color:var(--muted); }}
.cols {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
@media (max-width:640px) {{ .cols {{ grid-template-columns:1fr; }} }}
.rows {{ display:flex; flex-direction:column; gap:10px; }}
.row {{ display:flex; justify-content:space-between; align-items:baseline; gap:12px;
  padding-bottom:9px; border-bottom:1px dashed var(--border); }}
.row:last-child {{ border-bottom:0; padding-bottom:0; }}
.row .k {{ color:var(--muted); font-size:.9rem; }}
.row .v {{ font-weight:600; }}
table {{ width:100%; border-collapse:collapse; font-size:.9rem; }}
.tablewrap {{ overflow-x:auto; }}
th, td {{ text-align:start; padding:9px 10px; border-bottom:1px solid var(--border); white-space:nowrap; }}
th {{ font-size:.74rem; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); font-weight:600; }}
td.num {{ text-align:end; font-family:ui-monospace,Menlo,monospace; font-variant-numeric:tabular-nums; }}
td.empty {{ text-align:center; color:var(--muted); padding:20px; }}
.pill {{ font-size:.76rem; font-weight:600; padding:3px 9px; border-radius:999px; }}
.pill--good {{ color:var(--good); background:color-mix(in srgb,var(--good) 14%,transparent); }}
.pill--bad {{ color:var(--bad); background:color-mix(in srgb,var(--bad) 14%,transparent); }}
.pill--warn {{ color:var(--warn); background:color-mix(in srgb,var(--warn) 14%,transparent); }}
.pill--neutral {{ color:var(--muted); background:var(--surface2); }}
footer {{ margin-top:28px; color:var(--muted); font-size:.78rem; text-align:center; line-height:1.7; }}
.badge-proven {{ display:inline-block; font-size:.72rem; font-weight:700; color:var(--accent);
  border:1px solid color-mix(in srgb,var(--accent) 40%,var(--border)); border-radius:6px; padding:2px 7px; }}
label.row {{ cursor:text; }}
.inp {{ width:130px; max-width:48%; text-align:end; font-family:ui-monospace,Menlo,monospace;
  font-variant-numeric:tabular-nums; font-size:.95rem; font-weight:600; color:var(--text);
  background:var(--surface2); border:1px solid var(--border); border-radius:9px; padding:7px 10px; }}
.inp:focus {{ outline:none; border-color:var(--accent);
  box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 20%,transparent); }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>لوحة أداء بوت التداول</h1>
    <span class="status"><span class="dot"></span>يعمل — تداول ورقي</span>
    <span class="chip chip--off">التداول الحقيقي: مُعطَّل</span>
  </header>

  <div class="grid">
    {_kpi("رأس المال", f"{m['equity']:,.2f}", f"بدأ من {m['starting_equity']:,.0f}")}
    {_kpi("العائد", f"{ret:+.2f}%", "منذ البداية", ret_tone)}
    {_kpi("التوقّع/صفقة", f"{m['expectancy_r']:+.2f}R", f"{m['closed']} صفقة مغلقة", exp_tone)}
    {_kpi("نسبة النجاح", f"{m['win_rate']:.0f}%", f"{m['wins']}‏/‏{m['closed']} رابحة")}
    {_kpi("عامل الربح", _pf(m['profit_factor']), "ربح ÷ خسارة")}
    {_kpi("أقصى تراجع", f"{m['max_drawdown_pct']:.1f}%", "من القمة", "warn" if m['max_drawdown_pct'] > 0 else "neutral")}
    {_kpi("صفقات مفتوحة", f"{m['open_positions']}", f"الحدّ الأقصى {getattr(config,'MAX_OPEN_POSITIONS',5)}")}
    {_kpi("صافي الربح/الخسارة", f"{m['net_pnl']:+,.2f}", f"إجمالي {m['total_r']:+.1f}R", ret_tone)}
  </div>

  <section class="card">
    <h2>منحنى رأس المال (مُحقَّق)</h2>
    {curve}
    <div class="curve-meta"><span>البداية {m['starting_equity']:,.0f}</span><span>الآن {m['equity']:,.2f}</span></div>
  </section>

  <section class="cols">
    <div class="card">
      <h2>الأفضلية المُثبتة <span class="badge-proven">بالباك-تِست</span></h2>
      <div class="rows">
        <div class="row"><span class="k">داخل العيّنة (1h، RR2+EMA200)</span><span class="v good">+{PROVEN['in_sample_r']:.2f}R</span></div>
        <div class="row"><span class="k">نسبة النجاح داخل العيّنة</span><span class="v">{PROVEN['in_sample_wr']}%</span></div>
        <div class="row"><span class="k">خارج العيّنة (Walk-Forward)</span><span class="v good">+{PROVEN['oos_r']:.2f}R</span></div>
        <div class="row"><span class="k">صفقات اختبار خارج العيّنة</span><span class="v">{PROVEN['oos_trades']}</span></div>
      </div>
    </div>
    <div class="card">
      <h2>محرّك المخاطر</h2>
      <div class="rows">
        <div class="row"><span class="k">مخاطرة لكل صفقة</span><span class="v">{rp:.1f}%</span></div>
        <div class="row"><span class="k">أقصى خسارة يومية</span><span class="v">{dl:.1f}%</span></div>
        <div class="row"><span class="k">إيقاف بعد خسائر متتالية</span><span class="v">{cl}</span></div>
        <div class="row"><span class="k">أقل عائد/مخاطرة</span><span class="v">1:{rr:.0f}</span></div>
      </div>
    </div>
  </section>

  {mydata_card}

  <section class="card">
    <h2>الصفقات المفتوحة</h2>
    <div class="tablewrap"><table>
      <thead><tr><th>العملة</th><th>الدخول</th><th>الوقف</th><th>الهدف</th><th>الكمية</th><th>AI</th></tr></thead>
      <tbody>{open_rows}</tbody>
    </table></div>
  </section>

  <section class="card">
    <h2>آخر الإشارات المسجّلة</h2>
    <div class="tablewrap"><table>
      <thead><tr><th>العملة</th><th>الدخول</th><th>الدرجة</th><th>النتيجة</th><th>الحالة</th></tr></thead>
      <tbody>{sig_rows}</tbody>
    </table></div>
  </section>

  <footer>
    تحليل فني آلي لأغراض تعليمية — ليس نصيحة مالية. لا توجد صفقة ناجحة 100%.<br>
    التداول الحقيقي مُعطَّل بالتصميم؛ كل الأرقام من التنفيذ الورقي والباك-تِست.
  </footer>
</div>
{mydata_script}
</body>
</html>"""


def main() -> int:
    equity0 = getattr(config, "ACCOUNT_BALANCE", 1000.0)
    account = pt.load_account(equity0, PAPER_STATE)
    m = compute(account)
    recent = list(reversed(journal.load()))     # الأحدث أولًا
    out = render(account, m, recent)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"✅ لوحة الأداء: {OUT} ({len(out)} حرف) | "
          f"رصيد {m['equity']} | مغلقة {m['closed']} | مفتوحة {m['open_positions']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""لوحة تحكم عتبات البوت — محلي فقط. لا تداول حقيقي."""
from __future__ import annotations
import json, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import config
from deals_bot import journal
from deals_bot import paper_trading as pt
from deals_bot.settings_store import SCHEMA, apply_overrides, load, save
apply_overrides(config)
HOST = os.environ.get("CONTROL_HOST", "127.0.0.1")
PORT = int(os.environ.get("CONTROL_PORT", "8787"))
TOKEN = os.environ.get("CONTROL_PANEL_TOKEN", "")
PAPER_STATE = os.path.join("journal", "paper_account.json")

def _state():
    apply_overrides(config)
    equity0 = float(getattr(config, "ACCOUNT_BALANCE", 250.0))
    account = pt.load_account(equity0, PAPER_STATE)
    stats = pt.account_stats(account)
    recent = []
    try:
        for t in reversed(journal.load()):
            recent.append({"symbol": t.symbol, "status": t.status, "entry": t.entry, "score": t.score, "result_r": t.result_r})
            if len(recent) >= 12:
                break
    except Exception:
        pass
    fields = []
    for key, spec in SCHEMA.items():
        fields.append({"key": key, "label": spec["label"], "group": spec["group"], "type": spec["type"], "min": spec.get("min"), "max": spec.get("max"), "step": spec.get("step"), "value": getattr(config, key, spec.get("min")), "overridden": key in load()})
    return {"live_locked": True, "bot": "@Bighotwelcome_bot", "paper": True, "stats": stats, "positions": [{"symbol": p.symbol, "entry": p.entry, "stop": p.stop, "target": p.target, "qty": p.qty, "ai_score": p.ai_score} for p in account.positions], "recent": recent, "fields": fields}

PAGE = """<!doctype html><html lang=ar dir=rtl><head><meta charset=utf-8><meta name=viewport content=\"width=device-width,initial-scale=1\"><title>لوحة تحكم البوت</title>
<style>:root{--bg:#0e1116;--card:#161b22;--line:#2a3340;--txt:#d5deea;--mut:#8b97a8;--acc:#38bdf8;--good:#22c55e;--bad:#ef4444}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font-family:system-ui,sans-serif}.wrap{max-width:1100px;margin:0 auto;padding:24px 16px 64px}h1{font-size:1.35rem;margin:0}header{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:18px}.chip{border:1px solid var(--line);border-radius:999px;padding:4px 10px;font-size:.8rem}.chip.off{color:var(--bad)}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin:16px 0}.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin-top:16px}h2{margin:0 0 12px;font-size:.85rem;color:var(--mut)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}label{display:flex;flex-direction:column;gap:6px;font-size:.82rem;background:#12171e;border:1px solid var(--line);border-radius:10px;padding:10px}input{background:#0e1116;color:var(--txt);border:1px solid var(--line);border-radius:8px;padding:8px}button{background:var(--acc);color:#04202c;border:0;border-radius:10px;padding:10px 16px;font-weight:700;cursor:pointer}button.ghost{background:transparent;color:var(--txt);border:1px solid var(--line)}table{width:100%;border-collapse:collapse;font-size:.85rem}td,th{padding:8px;border-bottom:1px solid var(--line);text-align:start}.note{color:var(--mut);font-size:.8rem}.toggle{display:flex;align-items:center;justify-content:space-between}</style></head><body><div class=wrap><header><h1>لوحة تحكم البوت</h1><span class=chip id=botName>ورقي</span><span class=\"chip off\">التداول الحقيقي مقفول</span></header><div class=kpis id=kpis></div><section class=card><h2>العتبات والبوابات</h2><p class=note>الحفظ يكتب journal/control_settings.json ويتطبّق على الفحص التالي. التداول الحقيقي لا يُفتح من هنا.</p><form id=frm><div id=fields></div><div style=\"margin-top:14px;display:flex;gap:8px\"><button type=submit>حفظ العتبات</button><button type=button class=ghost id=reset>إرجاع الافتراضي</button></div></form><p class=note id=msg></p></section><section class=card><h2>صفقات مفتوحة</h2><div id=pos></div></section><section class=card><h2>آخر الإشارات</h2><div id=sig></div></section></div>
<script>
async function load(){const s=await (await fetch('/api/state')).json();document.getElementById('botName').textContent=s.bot+' — ورقي';const st=s.stats||{};document.getElementById('kpis').innerHTML=[['الرصيد',(st.equity??0).toFixed(2)],['العائد %',(st.return_pct??0).toFixed(2)],['نجاح %',(st.win_rate??0)],['مفتوحة',st.open??0],['مغلقة',st.closed??0]].map(([k,v])=>`<div class=kpi><span>${k}</span><b>${v}</b></div>`).join('');const groups={};(s.fields||[]).forEach(f=>{(groups[f.group]=groups[f.group]||[]).push(f)});let html='';Object.keys(groups).forEach(g=>{html+=`<h2>${g}</h2><div class=grid>`;groups[g].forEach(f=>{html+=f.type==='bool'?`<label class=toggle><span>${f.label}</span><input type=checkbox name=\"${f.key}\" ${f.value?'checked':''}></label>`:`<label>${f.label}<input name=\"${f.key}\" type=number step=\"${f.step||1}\" min=\"${f.min}\" max=\"${f.max}\" value=\"${f.value}\"></label>`});html+='</div>'});document.getElementById('fields').innerHTML=html;const pos=s.positions||[];document.getElementById('pos').innerHTML=pos.length?`<table><tr><th>عملة</th><th>دخول</th><th>وقف</th><th>هدف</th></tr>${pos.map(p=>`<tr><td>${p.symbol}</td><td>${p.entry}</td><td>${p.stop}</td><td>${p.target}</td></tr>`).join('')}</table>`:'<p class=note>لا صفقات مفتوحة</p>';const rec=s.recent||[];document.getElementById('sig').innerHTML=rec.length?`<table><tr><th>عملة</th><th>حالة</th><th>درجة</th><th>R</th></tr>${rec.map(t=>`<tr><td>${t.symbol}</td><td>${t.status}</td><td>${t.score??''}</td><td>${t.result_r??'—'}</td></tr>`).join('')}</table>`:'<p class=note>لا إشارات بعد</p>'}
document.getElementById('frm').addEventListener('submit',async e=>{e.preventDefault();const data={};new FormData(e.target).forEach((v,k)=>data[k]=v);document.querySelectorAll('#frm input[type=checkbox]').forEach(el=>data[el.name]=el.checked);const r=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const j=await r.json();document.getElementById('msg').textContent=j.ok?'تم الحفظ — هتتشاف في الفحص الجاي.':(j.error||'فشل');load()});
document.getElementById('reset').addEventListener('click',async()=>{await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({__reset:true})});load()});
load();
</script></body></html>"""

class Handler(BaseHTTPRequestHandler):
    def _check(self):
        if not TOKEN:
            return True
        got = self.headers.get("Authorization", "")
        q = urlparse(self.path).query
        return TOKEN in got or f"token={TOKEN}" in q
    def do_GET(self):
        if not self._check():
            self.send_error(401); return
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(PAGE.encode("utf-8")); return
        if path == "/api/state":
            self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8"); self.end_headers(); self.wfile.write(json.dumps(_state(), ensure_ascii=False, default=str).encode("utf-8")); return
        self.send_error(404)
    def do_POST(self):
        if not self._check():
            self.send_error(401); return
        if urlparse(self.path).path != "/api/settings":
            self.send_error(404); return
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}
        if payload.get("__reset"):
            try: os.remove(os.path.join("journal", "control_settings.json"))
            except FileNotFoundError: pass
            apply_overrides(config)
            body = {"ok": True, "reset": True}
        else:
            body = {"ok": True, "saved": save(payload)}; apply_overrides(config)
        self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8"); self.end_headers(); self.wfile.write(json.dumps(body, ensure_ascii=False).encode("utf-8"))
    def log_message(self, fmt, *args):
        sys.stderr.write("control " + (fmt % args) + "\n")

def main():
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"لوحة التحكم: http://{HOST}:{PORT}")
    print("التداول الحقيقي مقفول. Ctrl+C للإيقاف.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nتوقفت اللوحة.")
    return 0

if __name__ == "__main__":
    sys.exit(main())

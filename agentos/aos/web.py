"""Thin, read-only web control plane over the same state.

Same state, another surface. A stdlib http.server exposes JSON endpoints + one
HTML page that polls them, so a human can "see anything" in a browser without new
storage. READ-ONLY by design — no side effects, no mutations; the CLI remains the
control surface for action. The data layer is pure functions (testable without a
socket); the HTTP layer is a thin shell.

Endpoints:
  GET /                     → single-page dashboard (polls the APIs)
  GET /api/snapshot         → portfolio rollup + metrics
  GET /api/events?since=ID  → events with id > ID (the live stream, via polling)
  GET /api/goal?id=GID      → one project rollup
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import engine, rollup, skills
from .db import connect, jloads


def snapshot(conn) -> dict:
    return {"portfolio": rollup.portfolio_rollup(conn),
            "metrics": engine.metrics(conn),
            "skills": skills.listing(conn)}


def events_since(conn, since: int = 0, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        "SELECT id, ts, kind, goal_id, task_id, data FROM events WHERE id>? ORDER BY id LIMIT ?",
        (since, limit)).fetchall()
    return [{"id": r["id"], "ts": r["ts"], "kind": r["kind"],
             "goal_id": r["goal_id"], "task_id": r["task_id"],
             "data": jloads(r["data"], {})} for r in rows]


HTML = """<!doctype html><meta charset=utf-8><title>AgentOS</title>
<style>
 body{font:14px/1.5 ui-monospace,Menlo,monospace;margin:0;background:#0b0b0c;color:#d7d7db}
 header{padding:12px 18px;background:#141417;border-bottom:1px solid #26262b}
 h1{font-size:15px;margin:0;color:#e8b873} main{display:grid;grid-template-columns:1fr 1fr;gap:14px;padding:14px}
 .card{background:#141417;border:1px solid #26262b;border-radius:8px;padding:12px}
 .card h2{font-size:12px;margin:0 0 8px;color:#9aa0a6;text-transform:uppercase;letter-spacing:.06em}
 .k{color:#9aa0a6} .v{color:#e8e8ea} .row{display:flex;justify-content:space-between}
 .attn{color:#e06c75} .ok{color:#98c379} .ev{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .badge{display:inline-block;min-width:1.6em;text-align:center;border-radius:4px;padding:0 5px;background:#222}
</style>
<header><h1>AgentOS — control plane</h1><span class=k id=ts></span></header>
<main>
 <div class=card><h2>Portfolio</h2><div id=port></div></div>
 <div class=card><h2>Metrics</h2><div id=metrics></div></div>
 <div class=card style=grid-column:1/3><h2>Needs attention</h2><div id=attn></div></div>
 <div class=card style=grid-column:1/3><h2>Registered skills</h2><div id=skills></div></div>
 <div class=card style=grid-column:1/3><h2>Live events</h2><div id=events></div></div>
</main>
<script>
let since=0;
const el=id=>document.getElementById(id);
const row=(k,v)=>`<div class=row><span class=k>${k}</span><span class=v>${v}</span></div>`;
async function tick(){
 try{
  const s=await (await fetch('/api/snapshot')).json();
  el('ts').textContent=new Date().toISOString();
  const p=s.portfolio;
  el('port').innerHTML=row('goals',`${p.goals} (active ${p.active}/done ${p.done}/failed ${p.failed})`)
    +row('blocked tasks',p.blocked_tasks)+row('failed tasks',p.failed_tasks)
    +row('dangerous paths',p.dangerous_paths)
    +row('pending approvals',p.pending_approvals)+row('cost ticks',p.cost_ticks)
    +'<hr style=border-color:#26262b>'+p.projects.map(x=>row(`[${x.status}] ${x.title}`,`${x.done}/${x.total}`)).join('');
  el('metrics').innerHTML=Object.entries(s.metrics).map(([k,v])=>row(k,v)).join('');
  el('attn').innerHTML=p.attention.length?p.attention.map(a=>`<div class=attn>• ${a}</div>`).join(''):'<div class=ok>nothing needs attention</div>';
  el('skills').innerHTML=(s.skills&&s.skills.length)?s.skills.map(k=>row(k.name,k.scripts.length?('scripts: '+k.scripts.join(', ')):'guidance')).join(''):'<div class=k>no skills registered</div>';
  const evs=await (await fetch('/api/events?since='+since)).json();
  if(evs.length){since=evs[evs.length-1].id;
   const box=el('events');
   for(const e of evs){const d=document.createElement('div');d.className='ev';
    d.innerHTML=`<span class=k>${e.ts}</span> <span class=badge>${e.kind}</span> ${e.task_id||e.goal_id||''}`;
    box.prepend(d);}
   while(box.childElementCount>40)box.lastChild.remove();}
 }catch(err){el('ts').textContent='disconnected';}
}
tick();setInterval(tick,2000);
</script>"""


def make_handler(db_path=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, code, body, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body.encode())

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/":
                return self._send(200, HTML, "text/html; charset=utf-8")
            conn = connect(db_path)
            try:
                if u.path == "/api/snapshot":
                    return self._send(200, json.dumps(snapshot(conn)))
                if u.path == "/api/events":
                    since = int((parse_qs(u.query).get("since", ["0"])[0]) or 0)
                    return self._send(200, json.dumps(events_since(conn, since)))
                if u.path == "/api/goal":
                    gid = parse_qs(u.query).get("id", [""])[0]
                    return self._send(200, json.dumps(rollup.project_rollup(conn, gid) or {}))
                if u.path == "/api/skills":
                    return self._send(200, json.dumps(skills.listing(conn)))
                return self._send(404, json.dumps({"error": "not found"}))
            finally:
                conn.close()
    return Handler


def serve(port=8787, db_path=None):
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(db_path))
    print(f"AgentOS web control plane (read-only) → http://127.0.0.1:{port}  (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()

"""skim stats server — real-time usage dashboard for BATWTechworks.

A lightweight HTTP server (stdlib only, no Flask required) that:
- Receives POST /api/report from skim CLI clients
- Stores data in SQLite
- Serves a real-time web dashboard at GET /
- Provides JSON API at GET /api/stats
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, parse_qs


_DB_PATH = Path.home() / ".local" / "share" / "skim" / "server.db"

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    email TEXT NOT NULL,
    command TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    saved_tokens INTEGER NOT NULL,
    mode TEXT,
    project TEXT,
    hostname TEXT
);
CREATE INDEX IF NOT EXISTS idx_reports_email ON reports(email);
CREATE INDEX IF NOT EXISTS idx_reports_ts ON reports(timestamp);
"""


def _get_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.executescript(_SCHEMA)
    return conn


def _query_stats(conn: sqlite3.Connection, days: int = 30) -> dict[str, Any]:
    cutoff = time.time() - (days * 86400)

    users = conn.execute(
        """SELECT email,
                  COUNT(*) as ops,
                  COALESCE(SUM(input_tokens), 0) as total_input,
                  COALESCE(SUM(saved_tokens), 0) as total_saved,
                  MAX(timestamp) as last_seen
           FROM reports WHERE timestamp >= ?
           GROUP BY email ORDER BY total_saved DESC""",
        (cutoff,),
    ).fetchall()

    by_mode = conn.execute(
        """SELECT mode,
                  COUNT(*) as ops,
                  COALESCE(SUM(saved_tokens), 0) as total_saved
           FROM reports WHERE timestamp >= ?
           GROUP BY mode ORDER BY total_saved DESC""",
        (cutoff,),
    ).fetchall()

    daily = conn.execute(
        """SELECT date(timestamp, 'unixepoch', 'localtime') as day,
                  COUNT(*) as ops,
                  SUM(saved_tokens) as saved
           FROM reports WHERE timestamp >= ?
           GROUP BY day ORDER BY day""",
        (cutoff,),
    ).fetchall()

    by_project = conn.execute(
        """SELECT project,
                  COUNT(*) as ops,
                  COALESCE(SUM(saved_tokens), 0) as total_saved
           FROM reports WHERE timestamp >= ?
           GROUP BY project ORDER BY total_saved DESC LIMIT 10""",
        (cutoff,),
    ).fetchall()

    recent = conn.execute(
        """SELECT timestamp, email, command, input_tokens, saved_tokens, mode, project
           FROM reports ORDER BY timestamp DESC LIMIT 20""",
    ).fetchall()

    total_ops = sum(u[1] for u in users)
    total_saved = sum(u[3] for u in users)
    total_input = sum(u[2] for u in users)

    return {
        "days": days,
        "total_operations": total_ops,
        "total_tokens_saved": total_saved,
        "total_savings_pct": round(total_saved / total_input * 100) if total_input > 0 else 0,
        "est_cost_saved_monthly": round(total_saved / 1_000_000 * 3.0 * (30 / max(days, 1)), 2),
        "active_users": len(users),
        "users": [
            {
                "email": email,
                "operations": ops,
                "tokens_saved": saved,
                "savings_pct": round(saved / inp * 100) if inp > 0 else 0,
                "last_seen": time.strftime("%Y-%m-%d %H:%M", time.localtime(last)),
            }
            for email, ops, inp, saved, last in users
        ],
        "by_mode": [
            {"mode": mode or "unknown", "operations": ops, "tokens_saved": saved}
            for mode, ops, saved in by_mode
        ],
        "daily": [
            {"date": day, "operations": ops, "tokens_saved": saved}
            for day, ops, saved in daily
        ],
        "by_project": [
            {"project": proj or "unknown", "operations": ops, "tokens_saved": saved}
            for proj, ops, saved in by_project
        ],
        "recent": [
            {
                "time": time.strftime("%H:%M:%S", time.localtime(ts)),
                "email": email.split("@")[0] if email else "?",
                "command": cmd[:40],
                "input": inp,
                "saved": saved,
                "mode": mode or "",
                "project": proj or "",
            }
            for ts, email, cmd, inp, saved, mode, proj in recent
        ],
    }


_DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>skim — Usage Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0a0e14;--bg2:#0d1219;--surface:rgba(22,27,34,.65);--glass:rgba(22,27,34,.45);
  --border:rgba(55,65,81,.45);--border-h:rgba(55,65,81,.7);
  --text:#e2e8f0;--dim:#64748b;--muted:#94a3b8;
  --cyan:#22d3ee;--cyan2:#06b6d4;--green:#34d399;--green2:#10b981;
  --yellow:#fbbf24;--purple:#a78bfa;--rose:#fb7185;--blue:#60a5fa;
  --grad-cyan:linear-gradient(135deg,#22d3ee,#06b6d4);
  --grad-green:linear-gradient(135deg,#34d399,#10b981);
  --grad-yellow:linear-gradient(135deg,#fbbf24,#f59e0b);
  --grad-purple:linear-gradient(135deg,#a78bfa,#8b5cf6);
  --grad-rose:linear-gradient(135deg,#fb7185,#f43f5e);
  --radius:12px;--radius-sm:8px;
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;overflow-x:hidden}
body::before{content:'';position:fixed;top:-50%;left:-50%;width:200%;height:200%;background:radial-gradient(circle at 30% 20%,rgba(34,211,238,.04) 0%,transparent 50%),radial-gradient(circle at 70% 80%,rgba(52,211,153,.03) 0%,transparent 50%);pointer-events:none;z-index:0}

.shell{max-width:1360px;margin:0 auto;padding:2rem 2.5rem;position:relative;z-index:1}

/* Header */
.hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:2rem;padding-bottom:1.5rem;border-bottom:1px solid var(--border)}
.hdr-left{display:flex;align-items:center;gap:1rem}
.logo{font-family:'JetBrains Mono',monospace;font-size:1.6rem;font-weight:700;background:var(--grad-cyan);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.tagline{color:var(--dim);font-size:.82rem;font-weight:500}
.hdr-right{display:flex;align-items:center;gap:1.2rem}
.live-dot{width:7px;height:7px;border-radius:50%;background:var(--green);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(52,211,153,.5)}50%{opacity:.7;box-shadow:0 0 0 6px rgba(52,211,153,0)}}
.live-text{color:var(--dim);font-size:.75rem;font-weight:500;letter-spacing:.03em}
.countdown{font-family:'JetBrains Mono',monospace;color:var(--dim);font-size:.7rem;min-width:24px;text-align:right}

/* KPI Cards */
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:1rem;margin-bottom:2rem}
.kpi{background:var(--surface);backdrop-filter:blur(12px);border:1px solid var(--border);border-radius:var(--radius);padding:1.25rem 1.4rem;transition:border-color .2s,transform .15s}
.kpi:hover{border-color:var(--border-h);transform:translateY(-1px)}
.kpi-icon{width:32px;height:32px;border-radius:var(--radius-sm);display:flex;align-items:center;justify-content:center;font-size:.95rem;margin-bottom:.8rem}
.kpi-label{color:var(--dim);font-size:.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.35rem}
.kpi-val{font-size:1.75rem;font-weight:700;font-variant-numeric:tabular-nums;line-height:1.1}
.kpi-sub{color:var(--dim);font-size:.72rem;margin-top:.3rem}

/* Cards / Panels */
.grid{display:grid;gap:1.25rem;margin-bottom:1.25rem}
.g2{grid-template-columns:1fr 1fr}
.g3{grid-template-columns:2fr 1fr}
.g4{grid-template-columns:1fr 1fr 1fr}
.card{background:var(--surface);backdrop-filter:blur(12px);border:1px solid var(--border);border-radius:var(--radius);padding:1.4rem 1.5rem;transition:border-color .2s}
.card:hover{border-color:var(--border-h)}
.card-title{font-size:.72rem;font-weight:600;color:var(--dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:1rem;display:flex;align-items:center;gap:.5rem}
.card-title .icon{font-size:.85rem}

/* Tables */
table{width:100%;border-collapse:collapse}
th{color:var(--dim);font-size:.68rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;padding:.6rem .8rem;text-align:left;border-bottom:1px solid var(--border)}
td{padding:.65rem .8rem;font-size:.82rem;border-bottom:1px solid rgba(55,65,81,.2)}
tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(255,255,255,.02)}
.r{text-align:right;font-variant-numeric:tabular-nums;font-family:'JetBrains Mono',monospace;font-size:.78rem}
.pct{color:var(--green);font-weight:600}
.email{color:var(--cyan);font-weight:500}
.mode-tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.7rem;font-weight:500;font-family:'JetBrains Mono',monospace}
.mode-structural{background:rgba(34,211,238,.12);color:var(--cyan)}
.mode-dedup{background:rgba(52,211,153,.12);color:var(--green)}
.mode-compress{background:rgba(251,191,36,.12);color:var(--yellow)}
.mode-symbol{background:rgba(167,139,250,.12);color:var(--purple)}
.mode-head_tail{background:rgba(96,165,250,.12);color:var(--blue)}
.mode-full{background:rgba(100,116,139,.12);color:var(--dim)}

/* SVG Chart */
.chart-wrap{position:relative;width:100%;height:180px}
.chart-wrap svg{width:100%;height:100%}

/* Donut */
.donut-wrap{display:flex;align-items:center;gap:2rem}
.donut-legend{display:flex;flex-direction:column;gap:.5rem}
.legend-item{display:flex;align-items:center;gap:.5rem;font-size:.78rem}
.legend-dot{width:8px;height:8px;border-radius:2px;flex-shrink:0}

/* Bar Chart */
.hbar{display:flex;align-items:center;gap:.7rem;margin-bottom:.55rem}
.hbar-label{min-width:90px;font-size:.78rem;color:var(--muted);text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hbar-track{flex:1;height:22px;background:rgba(255,255,255,.03);border-radius:4px;overflow:hidden;position:relative}
.hbar-fill{height:100%;border-radius:4px;transition:width .6s cubic-bezier(.4,0,.2,1);min-width:2px}
.hbar-val{min-width:65px;font-family:'JetBrains Mono',monospace;font-size:.75rem;color:var(--muted);text-align:right}

/* Feed */
.feed-row{display:flex;align-items:center;gap:.7rem;padding:.5rem 0;border-bottom:1px solid rgba(55,65,81,.15);font-size:.78rem}
.feed-row:last-child{border-bottom:none}
.feed-time{font-family:'JetBrains Mono',monospace;color:var(--dim);min-width:60px;font-size:.72rem}
.feed-user{color:var(--cyan);min-width:70px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.feed-cmd{flex:1;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:'JetBrains Mono',monospace;font-size:.72rem}
.feed-saved{font-family:'JetBrains Mono',monospace;color:var(--green);font-weight:600;min-width:55px;text-align:right;font-size:.75rem}

/* Empty state */
.empty{text-align:center;padding:3rem;color:var(--dim)}
.empty-icon{font-size:2.5rem;margin-bottom:.8rem;opacity:.4}
.empty-text{font-size:.9rem}
.empty-hint{font-size:.78rem;margin-top:.5rem;color:var(--dim)}

@media(max-width:900px){.kpis{grid-template-columns:repeat(2,1fr)} .g2,.g3,.g4{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="shell">
<div class="hdr">
  <div class="hdr-left"><span class="logo">skim</span><span class="tagline">BATWTechworks Token Analytics</span></div>
  <div class="hdr-right"><div class="live-dot"></div><span class="live-text">LIVE</span><span class="countdown" id="cd">10</span></div>
</div>
<div id="app"></div>
</div>
<script>
const M = {structural:'mode-structural',dedup:'mode-dedup',compress:'mode-compress',symbol:'mode-symbol',head_tail:'mode-head_tail',full:'mode-full'};
const MC = {structural:'#22d3ee',dedup:'#34d399',compress:'#fbbf24',symbol:'#a78bfa',head_tail:'#60a5fa',full:'#64748b'};
function fmt(n){return n!=null?n.toLocaleString():'0'}
function tag(mode){return `<span class="mode-tag ${M[mode]||'mode-full'}">${mode||'—'}</span>`}

function sparkSVG(data,w,h){
  if(!data.length) return '';
  const max=Math.max(...data.map(d=>d.tokens_saved),1);
  const step=w/(data.length-1||1);
  const pts=data.map((d,i)=>[i*step, h-4-(d.tokens_saved/max)*(h-12)]);
  const line=pts.map((p,i)=>(i===0?'M':'L')+p[0].toFixed(1)+','+p[1].toFixed(1)).join(' ');
  const area=line+` L${w},${h} L0,${h} Z`;
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <defs><linearGradient id="ag" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#22d3ee" stop-opacity=".25"/><stop offset="100%" stop-color="#22d3ee" stop-opacity="0"/></linearGradient></defs>
    <path d="${area}" fill="url(#ag)"/>
    <path d="${line}" fill="none" stroke="#22d3ee" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
    ${pts.length?`<circle cx="${pts[pts.length-1][0]}" cy="${pts[pts.length-1][1]}" r="3" fill="#22d3ee" stroke="#0a0e14" stroke-width="2"/>`:''}
  </svg>`;
}

function donutSVG(modes,size){
  if(!modes.length) return '<div style="width:'+size+'px;height:'+size+'px"></div>';
  const total=modes.reduce((s,m)=>s+m.tokens_saved,0)||1;
  const r=size/2-4, cx=size/2, cy=size/2;
  let cum=0; const paths=[];
  modes.forEach(m=>{
    const pct=m.tokens_saved/total;
    if(pct<=0) return;
    const a1=cum*2*Math.PI-Math.PI/2, a2=(cum+pct)*2*Math.PI-Math.PI/2;
    const lg=pct>.5?1:0;
    const x1=cx+r*Math.cos(a1), y1=cy+r*Math.sin(a1);
    const x2=cx+r*Math.cos(a2), y2=cy+r*Math.sin(a2);
    paths.push(`<path d="M${cx},${cy} L${x1.toFixed(1)},${y1.toFixed(1)} A${r},${r} 0 ${lg} 1 ${x2.toFixed(1)},${y2.toFixed(1)} Z" fill="${MC[m.mode]||'#64748b'}" opacity=".85"/>`);
    cum+=pct;
  });
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">${paths.join('')}<circle cx="${cx}" cy="${cy}" r="${r*.55}" fill="#0d1219"/></svg>`;
}

function render(d){
  if(!d.total_operations){
    document.getElementById('app').innerHTML=`<div class="empty"><div class="empty-icon">📊</div><div class="empty-text">No data yet</div><div class="empty-hint">Usage data will appear here once team members start using skim.<br>Run <code style="color:var(--cyan)">skim read &lt;file&gt;</code> to generate data.</div></div>`;
    return;
  }
  const daily=d.daily.slice(-14);
  const maxBar=Math.max(...(d.by_project||[]).map(p=>p.tokens_saved),1);
  document.getElementById('app').innerHTML=`
  <div class="kpis">
    <div class="kpi"><div class="kpi-icon" style="background:rgba(34,211,238,.1)">👥</div><div class="kpi-label">Active Users</div><div class="kpi-val" style="color:var(--cyan)">${d.active_users}</div><div class="kpi-sub">last ${d.days} days</div></div>
    <div class="kpi"><div class="kpi-icon" style="background:rgba(96,165,250,.1)">⚡</div><div class="kpi-label">Operations</div><div class="kpi-val">${fmt(d.total_operations)}</div><div class="kpi-sub">total commands</div></div>
    <div class="kpi"><div class="kpi-icon" style="background:rgba(52,211,153,.1)">🪙</div><div class="kpi-label">Tokens Saved</div><div class="kpi-val" style="color:var(--green)">${fmt(d.total_tokens_saved)}</div><div class="kpi-sub">cumulative</div></div>
    <div class="kpi"><div class="kpi-icon" style="background:rgba(52,211,153,.1)">📉</div><div class="kpi-label">Avg Savings</div><div class="kpi-val" style="color:var(--green)">${d.total_savings_pct}%</div><div class="kpi-sub">reduction rate</div></div>
    <div class="kpi"><div class="kpi-icon" style="background:rgba(251,191,36,.1)">💰</div><div class="kpi-label">Cost Saved</div><div class="kpi-val" style="color:var(--yellow)">$${d.est_cost_saved_monthly}</div><div class="kpi-sub">per month est.</div></div>
  </div>

  <div class="grid g3">
    <div class="card">
      <div class="card-title"><span class="icon">📈</span> Daily Token Savings (14d)</div>
      <div class="chart-wrap">${sparkSVG(daily,600,180)}</div>
      <div style="display:flex;justify-content:space-between;margin-top:.5rem">
        <span style="font-size:.7rem;color:var(--dim)">${daily.length?daily[0].date:''}</span>
        <span style="font-size:.7rem;color:var(--dim)">${daily.length?daily[daily.length-1].date:''}</span>
      </div>
    </div>
    <div class="card">
      <div class="card-title"><span class="icon">🍩</span> By Mode</div>
      <div class="donut-wrap">
        ${donutSVG(d.by_mode,120)}
        <div class="donut-legend">${d.by_mode.map(m=>`<div class="legend-item"><span class="legend-dot" style="background:${MC[m.mode]||'#64748b'}"></span><span style="color:var(--muted)">${m.mode||'—'}</span><span style="margin-left:auto;font-family:'JetBrains Mono',monospace;font-size:.72rem;color:var(--text)">${fmt(m.tokens_saved)}</span></div>`).join('')}</div>
      </div>
    </div>
  </div>

  <div class="grid g2">
    <div class="card">
      <div class="card-title"><span class="icon">👤</span> Per-User Savings</div>
      <table>
        <tr><th>User</th><th class="r">Ops</th><th class="r">Tokens Saved</th><th class="r">Savings</th><th class="r">Last Active</th></tr>
        ${d.users.map(u=>`<tr><td class="email">${u.email}</td><td class="r">${fmt(u.operations)}</td><td class="r">${fmt(u.tokens_saved)}</td><td class="r pct">-${u.savings_pct}%</td><td class="r" style="color:var(--dim);font-size:.75rem">${u.last_seen}</td></tr>`).join('')}
      </table>
    </div>
    <div class="card">
      <div class="card-title"><span class="icon">📁</span> Top Projects</div>
      ${(d.by_project||[]).map(p=>`<div class="hbar"><span class="hbar-label">${p.project}</span><div class="hbar-track"><div class="hbar-fill" style="width:${Math.max(p.tokens_saved/maxBar*100,1)}%;background:var(--grad-purple)"></div></div><span class="hbar-val">${fmt(p.tokens_saved)}</span></div>`).join('')||'<div style="color:var(--dim);font-size:.82rem;padding:1rem 0">No project data</div>'}
    </div>
  </div>

  <div class="card" style="margin-top:0">
    <div class="card-title"><span class="icon">🔄</span> Recent Operations</div>
    ${(d.recent||[]).slice(0,12).map(r=>`<div class="feed-row"><span class="feed-time">${r.time}</span><span class="feed-user">${r.email}</span>${tag(r.mode)}<span class="feed-cmd">${r.command}</span><span class="feed-saved">-${fmt(r.saved)}</span></div>`).join('')||'<div style="color:var(--dim);padding:.8rem 0">No recent operations</div>'}
  </div>`;
}

let sec=10;
async function refresh(){
  try{ const r=await fetch('/api/stats'); render(await r.json()); }catch(e){console.error(e)}
  sec=10;
}
refresh();
setInterval(()=>{sec--;document.getElementById('cd').textContent=sec;if(sec<=0)refresh()},1000);
</script>
</body>
</html>
"""


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/stats":
            params = parse_qs(parsed.query)
            days = int(params.get("days", ["30"])[0])
            conn = _get_db()
            stats = _query_stats(conn, days)
            conn.close()
            self._json_response(200, stats)
        elif parsed.path == "/":
            self._html_response(200, _DASHBOARD_HTML)
        else:
            self._json_response(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/api/report":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._json_response(400, {"error": "invalid JSON"})
                return

            conn = _get_db()
            conn.execute(
                """INSERT INTO reports
                   (timestamp, email, command, input_tokens, output_tokens,
                    saved_tokens, mode, project, hostname)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    data.get("timestamp", time.time()),
                    data.get("email", ""),
                    data.get("command", ""),
                    data.get("input_tokens", 0),
                    data.get("output_tokens", 0),
                    data.get("saved_tokens", 0),
                    data.get("mode", ""),
                    data.get("project", ""),
                    data.get("hostname", ""),
                ),
            )
            conn.commit()
            conn.close()
            self._json_response(200, {"ok": True})
        else:
            self._json_response(404, {"error": "not found"})

    def _json_response(self, code: int, data: Any) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html_response(self, code: int, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_server(host: str = "0.0.0.0", port: int = 7745) -> None:
    """Start the skim stats server."""
    from skim.style import BOLD, CYAN, DIM, RESET, GREEN

    _get_db()

    server = HTTPServer((host, port), _Handler)
    print()
    print(f"  {BOLD}{CYAN}skim{RESET} {DIM}stats server{RESET}")
    print()
    print(f"  {GREEN}Dashboard:{RESET}  {BOLD}http://localhost:{port}{RESET}")
    print(f"  {DIM}API:{RESET}        http://localhost:{port}/api/stats")
    print(f"  {DIM}Database:{RESET}   {_DB_PATH}")
    print()
    print(f"  {DIM}Press Ctrl+C to stop.{RESET}")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n  {DIM}Server stopped.{RESET}")
        server.server_close()

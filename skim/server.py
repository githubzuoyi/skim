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
    }


_DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>skim — Usage Dashboard</title>
<style>
  :root {
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text: #e6edf3; --dim: #8b949e; --accent: #58a6ff;
    --green: #3fb950; --yellow: #d29922; --cyan: #39d2c0;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, 'SF Mono', Menlo, monospace; background: var(--bg); color: var(--text); padding: 2rem; }
  .header { display: flex; align-items: baseline; gap: 1rem; margin-bottom: 2rem; }
  .header h1 { font-size: 1.8rem; color: var(--cyan); }
  .header .sub { color: var(--dim); font-size: 0.9rem; }
  .kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
  .kpi { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1.2rem; }
  .kpi .label { color: var(--dim); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
  .kpi .value { font-size: 1.8rem; font-weight: 700; margin-top: 0.3rem; }
  .kpi .value.green { color: var(--green); }
  .kpi .value.cyan { color: var(--cyan); }
  .kpi .value.yellow { color: var(--yellow); }
  table { width: 100%; border-collapse: collapse; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; margin-bottom: 2rem; }
  th, td { padding: 0.7rem 1rem; text-align: left; border-bottom: 1px solid var(--border); }
  th { color: var(--dim); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
  td { font-size: 0.9rem; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  .pct { color: var(--green); font-weight: 600; }
  .section-title { color: var(--dim); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.8rem; }
  .chart-bar { height: 18px; background: var(--cyan); border-radius: 3px; opacity: 0.7; min-width: 2px; }
  .chart-row { display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.3rem; }
  .chart-label { min-width: 80px; color: var(--dim); font-size: 0.8rem; text-align: right; }
  .chart-value { color: var(--dim); font-size: 0.8rem; min-width: 60px; }
  .auto-refresh { color: var(--dim); font-size: 0.75rem; }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; }
  @media (max-width: 800px) { .grid-2 { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="header">
  <h1>skim</h1>
  <span class="sub">BATWTechworks Usage Dashboard</span>
  <span class="auto-refresh">auto-refreshes every 10s</span>
</div>

<div id="app">Loading...</div>

<script>
function fmt(n) { return n.toLocaleString(); }
function render(d) {
  const maxDaily = Math.max(...d.daily.map(r => r.tokens_saved), 1);
  document.getElementById('app').innerHTML = `
    <div class="kpi-row">
      <div class="kpi"><div class="label">Active Users</div><div class="value cyan">${d.active_users}</div></div>
      <div class="kpi"><div class="label">Total Operations</div><div class="value">${fmt(d.total_operations)}</div></div>
      <div class="kpi"><div class="label">Tokens Saved</div><div class="value green">${fmt(d.total_tokens_saved)}</div></div>
      <div class="kpi"><div class="label">Avg Savings</div><div class="value green">${d.total_savings_pct}%</div></div>
      <div class="kpi"><div class="label">Est. Cost Saved</div><div class="value yellow">$${d.est_cost_saved_monthly}/mo</div></div>
    </div>

    <div class="section-title">Per-User Savings (last ${d.days} days)</div>
    <table>
      <tr><th>User</th><th class="num">Operations</th><th class="num">Tokens Saved</th><th class="num">Savings</th><th>Last Active</th></tr>
      ${d.users.map(u => `
        <tr>
          <td>${u.email}</td>
          <td class="num">${fmt(u.operations)}</td>
          <td class="num">${fmt(u.tokens_saved)}</td>
          <td class="num pct">-${u.savings_pct}%</td>
          <td style="color:var(--dim)">${u.last_seen}</td>
        </tr>
      `).join('')}
    </table>

    <div class="grid-2">
      <div>
        <div class="section-title">By Mode</div>
        <table>
          <tr><th>Mode</th><th class="num">Ops</th><th class="num">Saved</th></tr>
          ${d.by_mode.map(m => `
            <tr><td>${m.mode}</td><td class="num">${fmt(m.operations)}</td><td class="num">${fmt(m.tokens_saved)}</td></tr>
          `).join('')}
        </table>
      </div>
      <div>
        <div class="section-title">Daily Activity</div>
        ${d.daily.slice(-14).map(r => `
          <div class="chart-row">
            <span class="chart-label">${r.date.slice(5)}</span>
            <div class="chart-bar" style="width:${Math.max(r.tokens_saved/maxDaily*200,2)}px"></div>
            <span class="chart-value">${fmt(r.tokens_saved)}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

async function refresh() {
  try {
    const r = await fetch('/api/stats');
    const d = await r.json();
    render(d);
  } catch(e) { console.error(e); }
}

refresh();
setInterval(refresh, 10000);
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

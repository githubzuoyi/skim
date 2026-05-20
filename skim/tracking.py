"""SQLite-based analytics for token savings tracking.

Records every skim operation with input/output token counts, enabling
``skim gain`` to show cumulative savings over time.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

from skim.pricing import estimate_input_cost, resolve_pricing_model, savings_pct, format_usd
from skim.session import estimate_tokens


# ---------------------------------------------------------------------------
# Database path
# ---------------------------------------------------------------------------

def _db_path() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME", "")
    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".local" / "share"
    return base / "skim" / "history.db"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    command TEXT NOT NULL,
    project TEXT,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    saved_tokens INTEGER NOT NULL,
    mode TEXT,
    session_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_commands_timestamp ON commands(timestamp);
CREATE INDEX IF NOT EXISTS idx_commands_mode ON commands(mode);
CREATE INDEX IF NOT EXISTS idx_commands_project_session ON commands(project, session_id);
"""


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------

class Tracker:
    """Records and reports on token savings."""

    def __init__(self, db_path: Path | None = None):
        self._db_path = db_path or _db_path()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.executescript(_SCHEMA)

    def record(
        self,
        command: str,
        raw_output: str,
        skim_output: str,
        mode: str,
        *,
        project: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """Record a single skim operation."""
        input_tokens = estimate_tokens(raw_output)
        output_tokens = estimate_tokens(skim_output)
        saved = input_tokens - output_tokens

        if project is None:
            try:
                project = Path.cwd().name
            except OSError:
                project = "unknown"

        if session_id is None:
            session_id = _current_tracker_session_id() or str(os.getppid())

        self._conn.execute(
            """INSERT INTO commands
               (timestamp, command, project, input_tokens, output_tokens, saved_tokens, mode, session_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (time.time(), command, project, input_tokens, output_tokens, saved, mode, session_id),
        )
        self._conn.commit()

    def _session_totals(
        self,
        session_id: str | None,
        project: str | None = None,
    ) -> dict[str, int]:
        """Aggregate tracker rows tied to one recorded session id."""

        if not session_id:
            return {
                "operations": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "saved_tokens": 0,
            }

        query = (
            "SELECT COUNT(*), COALESCE(SUM(input_tokens), 0), "
            "COALESCE(SUM(output_tokens), 0), COALESCE(SUM(saved_tokens), 0) "
            "FROM commands WHERE session_id = ?"
        )
        params: list[Any] = [session_id]

        if project:
            query += " AND project = ?"
            params.append(project)

        ops, total_input, total_output, total_saved = self._conn.execute(
            query,
            tuple(params),
        ).fetchone()

        return {
            "operations": int(ops or 0),
            "input_tokens": int(total_input or 0),
            "output_tokens": int(total_output or 0),
            "saved_tokens": int(total_saved or 0),
        }

    def _adopt_legacy_session_rows(
        self,
        session_id: str,
        start_ts: float,
        end_ts: float,
        project: str | None = None,
    ) -> int:
        """Relabel legacy numeric rows inside the active session window."""

        query = "SELECT DISTINCT session_id FROM commands WHERE timestamp >= ? AND timestamp <= ?"
        params: list[Any] = [start_ts, end_ts]
        if project:
            query += " AND project = ?"
            params.append(project)

        rows = self._conn.execute(query, tuple(params)).fetchall()
        legacy_ids = [row[0] for row in rows if row[0] != session_id]
        if not legacy_ids or any(not _is_legacy_session_id(value) for value in legacy_ids):
            return 0

        clauses: list[str] = []
        update_params: list[Any] = [session_id, start_ts, end_ts]
        if project:
            project_clause = " AND project = ?"
            update_params.append(project)
        else:
            project_clause = ""

        text_ids = [value for value in legacy_ids if value is not None]
        if text_ids:
            placeholders = ", ".join("?" for _ in text_ids)
            clauses.append(f"session_id IN ({placeholders})")
            update_params.extend(text_ids)
        if any(value is None for value in legacy_ids):
            clauses.append("session_id IS NULL")

        if not clauses:
            return 0

        cursor = self._conn.execute(
            "UPDATE commands SET session_id = ? "
            "WHERE timestamp >= ? AND timestamp <= ?"
            f"{project_clause} AND (" + " OR ".join(clauses) + ")",
            tuple(update_params),
        )
        self._conn.commit()
        return int(cursor.rowcount or 0)

    def gain_summary(
        self,
        days: int = 30,
        *,
        session_log_path: str | Path | None = None,
        all_projects: bool = False,
    ) -> dict[str, Any]:
        """Return aggregate statistics for the gain command."""
        cutoff = time.time() - (days * 86400)
        pricing = resolve_pricing_model()
        project = None if all_projects else _current_project_name()

        query = (
            "SELECT mode, "
            "COUNT(*) as ops, "
            "COALESCE(SUM(input_tokens), 0) as total_input, "
            "COALESCE(SUM(saved_tokens), 0) as total_saved "
            "FROM commands WHERE timestamp >= ?"
        )
        params: list[Any] = [cutoff]
        if project:
            query += " AND project = ?"
            params.append(project)
        query += " GROUP BY mode ORDER BY total_saved DESC"

        rows = self._conn.execute(query, tuple(params)).fetchall()

        modes: list[dict] = []
        grand_ops = 0
        grand_input = 0
        grand_saved = 0

        for mode, ops, total_input, total_saved in rows:
            total_output = total_input - total_saved
            pct = savings_pct(total_input, total_output)
            modes.append({
                "mode": mode or "unknown",
                "operations": ops,
                "input_tokens": total_input,
                "output_tokens": total_output,
                "tokens_saved": total_saved,
                "savings_pct": pct,
                "est_input_cost_saved": estimate_input_cost(max(total_saved, 0), pricing.key),
            })
            grand_ops += ops
            grand_input += total_input
            grand_saved += total_saved

        grand_output = grand_input - grand_saved
        grand_pct = savings_pct(grand_input, grand_output)
        est_cost_saved = estimate_input_cost(max(grand_saved, 0), pricing.key)
        latest_copilot_session = self._latest_copilot_session_for_project(
            project=project,
            session_log_path=session_log_path,
        )

        return {
            "days": days,
            "scope_project": project,
            "scope_label": f"project:{project}" if project else "all-projects",
            "modes": modes,
            "pricing_model": pricing.key,
            "pricing_display_name": pricing.display_name,
            "input_price_per_million": pricing.input_per_million,
            "total_operations": grand_ops,
            "total_input_tokens": grand_input,
            "total_output_tokens": grand_output,
            "total_tokens_saved": grand_saved,
            "total_savings_pct": grand_pct,
            "est_input_cost_saved": est_cost_saved,
            "est_input_cost_saved_monthly": est_cost_saved * (30 / max(days, 1)),
            "latest_copilot_session": latest_copilot_session,
        }

    def _latest_copilot_session_for_project(
        self,
        *,
        project: str | None,
        session_log_path: str | Path | None = None,
    ) -> dict[str, Any] | None:
        """Pick the most recent Copilot session that overlaps this project's skim usage."""

        fallback: dict[str, Any] | None = None
        for path in _candidate_copilot_session_logs(session_log_path):
            parsed = _parse_copilot_session_log(path)
            if parsed is None:
                continue

            session_totals = self._session_totals(
                parsed["session_id"],
                project=project,
            )
            if session_log_path is None:
                adopted = self._adopt_legacy_session_rows(
                    parsed["session_id"],
                    parsed["start_time"] - 5,
                    parsed["end_time"] + 5,
                    project=project,
                )
                if adopted > 0:
                    session_totals = self._session_totals(
                        parsed["session_id"],
                        project=project,
                    )
            enriched = {
                **parsed,
                **{
                    "skim_operations": session_totals["operations"],
                    "skim_input_tokens": session_totals["input_tokens"],
                    "skim_output_tokens": session_totals["output_tokens"],
                    "skim_saved_tokens": session_totals["saved_tokens"],
                    "skim_share_of_non_cached_input_pct": _pct_share(
                        session_totals["saved_tokens"],
                        parsed["non_cached_input_tokens"],
                    ),
                    "skim_compression_efficiency_pct": _pct_share(
                        session_totals["saved_tokens"],
                        session_totals["input_tokens"],
                    ),
                },
            }

            if session_log_path is not None:
                return enriched

            if session_totals["operations"] > 0 or session_totals["saved_tokens"] > 0:
                return enriched

        return None if session_log_path is None else fallback

    def print_summary(self, summary: dict[str, Any]) -> None:
        """Print a beautifully formatted gain summary."""
        from skim.style import (
            BOLD, DIM, RESET, GREEN, BRIGHT_GREEN, YELLOW, WHITE,
            BRIGHT_CYAN, hline, fmt_savings, SAVED,
        )

        scope_project = summary.get("scope_project")
        scope_suffix = f" · {scope_project}" if scope_project else " · all projects"

        print()
        print(
            f"  {BOLD}{BRIGHT_CYAN}skim{RESET}  "
            f"{DIM}Token Savings (last {summary['days']} days{scope_suffix}){RESET}"
        )
        print()

        # Table header
        print(
            f"  {DIM}{'Mode':<18} {'Ops':>6}   {'Input':>9}   {'Output':>9}   {'Saved':>9}   {'Savings':>7}{RESET}"
        )
        print(f"  {hline(74)}")

        # Rows
        for m in summary["modes"]:
            label = _mode_label(m["mode"])
            icon = _mode_icon(m["mode"])
            pct = m["savings_pct"]
            print(
                f"  {icon} {WHITE}{label:<16}{RESET} {m['operations']:>6,}   "
                f"{DIM}{m['input_tokens']:>9,}{RESET}   "
                f"{GREEN}{m['output_tokens']:>9,}{RESET}   "
                f"{YELLOW}{m['tokens_saved']:>9,}{RESET}   {fmt_savings(pct)}"
            )

        # Total
        print(f"  {hline(74)}")
        total_pct = summary["total_savings_pct"]
        print(
            f"  {SAVED} {BOLD}{'TOTAL':<16}{RESET} {BOLD}{summary['total_operations']:>6,}{RESET}   "
            f"{BOLD}{DIM}{summary['total_input_tokens']:>9,}{RESET}   "
            f"{BOLD}{GREEN}{summary['total_output_tokens']:>9,}{RESET}   "
            f"{BOLD}{YELLOW}{summary['total_tokens_saved']:>9,}{RESET}   "
            f"{BOLD}{fmt_savings(total_pct)}{RESET}"
        )

        total_compression_pct = _pct_share(
            summary["total_tokens_saved"],
            summary["total_input_tokens"],
        )
        print(
            f"  {DIM}  Skim compression on tracked input{RESET}"
            f" {GREEN}{total_compression_pct:.1f}%{RESET}"
            f" {DIM}({summary['total_tokens_saved']:,} / {summary['total_input_tokens']:,}){RESET}"
        )

        if summary["est_input_cost_saved_monthly"] > 0:
            cost = summary["est_input_cost_saved_monthly"]
            print(
                f"  {DIM}  Est. input cost saved{RESET}"
                f"{'':>12}{BRIGHT_GREEN}{format_usd(cost)}/month{RESET}"
            )

        print()

    def print_history(self, limit: int = 50, project: str | None = None) -> None:
        """Print recent command history."""
        from skim.style import BOLD, DIM, RESET, CYAN, YELLOW, GREEN, WHITE, hline

        query = (
            "SELECT timestamp, command, input_tokens, saved_tokens, mode "
            "FROM commands"
        )
        params: list[Any] = []
        if project:
            query += " WHERE project = ?"
            params.append(project)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(query, tuple(params)).fetchall()

        if not rows:
            print(f"  {DIM}No history recorded yet.{RESET}")
            return

        print()
        print(
            f"  {DIM}{'Time':<10} {'Command':<30} {'Input':>8} {'Saved':>8} {'Mode':<12}{RESET}"
        )
        print(f"  {hline(72)}")
        for ts, cmd, inp, saved, mode in reversed(rows):
            t = time.strftime("%H:%M:%S", time.localtime(ts))
            cmd_short = cmd[:28] + ".." if len(cmd) > 30 else cmd
            saved_color = GREEN if saved > 0 else DIM
            print(
                f"  {DIM}{t}{RESET}  {WHITE}{cmd_short:<30}{RESET}"
                f"{inp:>8,} {saved_color}{saved:>8,}{RESET} {DIM}{mode or '':<12}{RESET}"
            )
        print()

    def print_daily(self, days: int = 30, project: str | None = None) -> None:
        """Print day-by-day breakdown."""
        from skim.style import BOLD, DIM, RESET, YELLOW, WHITE, GREEN, hline

        cutoff = time.time() - (days * 86400)
        query = (
            "SELECT date(timestamp, 'unixepoch', 'localtime') as day, "
            "COUNT(*) as ops, SUM(saved_tokens) as saved "
            "FROM commands WHERE timestamp >= ?"
        )
        params: list[Any] = [cutoff]
        if project:
            query += " AND project = ?"
            params.append(project)
        query += " GROUP BY day ORDER BY day"
        rows = self._conn.execute(query, tuple(params)).fetchall()

        if not rows:
            print(f"  {DIM}No data for this period.{RESET}")
            return

        print()
        print(f"  {DIM}{'Date':<14} {'Operations':>10} {'Tokens Saved':>14}{RESET}")
        print(f"  {hline(42)}")
        for day, ops, saved in rows:
            bar_len = min(int(saved / max(1, max(r[2] for r in rows)) * 20), 20)
            bar = f"{GREEN}{'█' * bar_len}{DIM}{'░' * (20 - bar_len)}{RESET}"
            print(
                f"  {WHITE}{day}{RESET}  {ops:>10,} {YELLOW}{saved:>14,}{RESET}  {bar}"
            )
        print()

    def reset(self) -> None:
        """Delete all tracking data."""
        self._conn.execute("DELETE FROM commands")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------

_tracker: Tracker | None = None


def get_tracker() -> Tracker | None:
    """Get or create the global Tracker instance."""
    global _tracker
    if _tracker is None:
        try:
            _tracker = Tracker()
        except Exception:
            return None
    return _tracker


def _current_project_name() -> str | None:
    try:
        return Path.cwd().name
    except OSError:
        return None


def _current_tracker_session_id() -> str | None:
    for env_key in ("SKIM_COPILOT_SESSION_LOG", "VSCODE_TARGET_SESSION_LOG"):
        session_id = _session_id_from_log_path(os.environ.get(env_key))
        if session_id:
            return session_id
    return None


def _session_id_from_log_path(log_path: str | Path | None) -> str | None:
    if not log_path:
        return None

    path = Path(log_path).expanduser()
    candidate = path.parent if path.name == "main.jsonl" else path
    name = candidate.name.strip()
    return name or None


def _is_legacy_session_id(value: Any) -> bool:
    if value is None:
        return True
    return str(value).isdigit()


def _pct_share(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100, 1)


def _candidate_copilot_session_logs(session_log_path: str | Path | None = None) -> list[Path]:
    candidates: list[Path] = []

    if session_log_path:
        path = Path(session_log_path).expanduser()
        if path.is_dir():
            path = path / "main.jsonl"
        if path.exists():
            return [path]
        return []

    for env_key in ("SKIM_COPILOT_SESSION_LOG", "VSCODE_TARGET_SESSION_LOG"):
        env_value = os.environ.get(env_key)
        if not env_value:
            continue
        path = Path(env_value).expanduser()
        if path.is_dir():
            path = path / "main.jsonl"
        if path.exists():
            candidates.append(path)

    roots: list[Path] = []
    home = Path.home()
    appdata = os.environ.get("APPDATA")

    roots.extend(
        [
            home / "Library" / "Application Support" / "Code" / "User" / "workspaceStorage",
            home / "Library" / "Application Support" / "Code - Insiders" / "User" / "workspaceStorage",
            home / ".config" / "Code" / "User" / "workspaceStorage",
            home / ".config" / "Code - Insiders" / "User" / "workspaceStorage",
        ]
    )
    if appdata:
        roots.extend(
            [
                Path(appdata) / "Code" / "User" / "workspaceStorage",
                Path(appdata) / "Code - Insiders" / "User" / "workspaceStorage",
            ]
        )

    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in root.glob("*/GitHub.copilot-chat/debug-logs/*/main.jsonl"):
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                candidates.append(resolved)

    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)


def _load_latest_copilot_session(session_log_path: str | Path | None = None) -> dict[str, Any] | None:
    for path in _candidate_copilot_session_logs(session_log_path):
        parsed = _parse_copilot_session_log(path)
        if parsed is not None:
            return parsed
    return None


def _parse_copilot_session_log(path: Path) -> dict[str, Any] | None:
    total_input = 0
    total_output = 0
    total_cached = 0
    start_time: float | None = None
    end_time: float | None = None
    session_id = path.parent.name

    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for raw_line in handle:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    entry = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                ts_raw = entry.get("ts")
                dur_raw = entry.get("dur", 0)
                ts, dur = _normalize_log_times(ts_raw, dur_raw)
                if ts is not None:
                    start_time = ts if start_time is None else min(start_time, ts)
                    end_candidate = ts + dur
                    end_time = end_candidate if end_time is None else max(end_time, end_candidate)

                if entry.get("type") != "llm_request":
                    continue

                attrs = entry.get("attrs", {})
                total_input += _as_int(attrs.get("inputTokens"))
                total_output += _as_int(attrs.get("outputTokens"))
                total_cached += _as_int(
                    attrs.get("cachedTokens", attrs.get("cachedInputTokens", 0))
                )
    except OSError:
        return None

    if start_time is None or end_time is None:
        return None

    return {
        "session_id": session_id,
        "path": str(path),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cached_input_tokens": total_cached,
        "non_cached_input_tokens": max(total_input - total_cached, 0),
        "start_time": start_time,
        "end_time": end_time,
    }


def _normalize_log_times(ts_raw: Any, dur_raw: Any) -> tuple[float | None, float]:
    ts = _as_float(ts_raw)
    dur = _as_float(dur_raw)
    if ts is None:
        return None, 0.0

    if ts > 1_000_000_000_000:
        return ts / 1000.0, max(dur, 0.0) / 1000.0
    return ts, max(dur, 0.0)


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mode_label(mode: str) -> str:
    labels = {
        "structural": "AST structural",
        "dedup": "Session dedup",
        "compress": "Command compress",
        "full": "Full pass-through",
        "head_tail": "Head+tail",
        "symbol": "Symbol extract",
    }
    return labels.get(mode, mode)


def _mode_icon(mode: str) -> str:
    from skim.style import CYAN, GREEN, YELLOW, MAGENTA, BLUE, DIM, RESET

    icons = {
        "structural": f"{CYAN}◆{RESET}",
        "dedup": f"{GREEN}◆{RESET}",
        "compress": f"{YELLOW}◆{RESET}",
        "full": f"{DIM}◇{RESET}",
        "head_tail": f"{BLUE}◆{RESET}",
        "symbol": f"{MAGENTA}◆{RESET}",
    }
    return icons.get(mode, f"{DIM}◇{RESET}")

"""SQLite-based analytics for token savings tracking.

Records every skim operation with input/output token counts, enabling
``skim gain`` to show cumulative savings over time.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import Any

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
            session_id = str(os.getppid())

        self._conn.execute(
            """INSERT INTO commands
               (timestamp, command, project, input_tokens, output_tokens, saved_tokens, mode, session_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (time.time(), command, project, input_tokens, output_tokens, saved, mode, session_id),
        )
        self._conn.commit()

    def gain_summary(self, days: int = 30) -> dict[str, Any]:
        """Return aggregate statistics for the gain command."""
        cutoff = time.time() - (days * 86400)

        rows = self._conn.execute(
            """SELECT mode,
                      COUNT(*) as ops,
                      COALESCE(SUM(input_tokens), 0) as total_input,
                      COALESCE(SUM(saved_tokens), 0) as total_saved
               FROM commands
               WHERE timestamp >= ?
               GROUP BY mode
               ORDER BY total_saved DESC""",
            (cutoff,),
        ).fetchall()

        modes: list[dict] = []
        grand_ops = 0
        grand_input = 0
        grand_saved = 0

        for mode, ops, total_input, total_saved in rows:
            pct = round(total_saved / total_input * 100) if total_input > 0 else 0
            modes.append({
                "mode": mode or "unknown",
                "operations": ops,
                "tokens_saved": total_saved,
                "savings_pct": pct,
            })
            grand_ops += ops
            grand_input += total_input
            grand_saved += total_saved

        grand_pct = round(grand_saved / grand_input * 100) if grand_input > 0 else 0

        # Rough cost estimate: $3 per 1M input tokens (Claude Sonnet pricing)
        est_cost_saved = grand_saved / 1_000_000 * 3.0

        return {
            "days": days,
            "modes": modes,
            "total_operations": grand_ops,
            "total_tokens_saved": grand_saved,
            "total_savings_pct": grand_pct,
            "est_cost_saved_monthly": round(est_cost_saved * (30 / max(days, 1)), 2),
        }

    def print_summary(self, summary: dict[str, Any]) -> None:
        """Print a beautifully formatted gain summary."""
        from skim.style import (
            BOLD, DIM, RESET, CYAN, GREEN, BRIGHT_GREEN, YELLOW, WHITE,
            BRIGHT_CYAN, hline, fmt_savings, SAVED,
        )

        print()
        print(f"  {BOLD}{BRIGHT_CYAN}skim{RESET}  {DIM}Token Savings (last {summary['days']} days){RESET}")
        print()

        # Table header
        print(
            f"  {DIM}{'Mode':<22} {'Operations':>10}   {'Tokens Saved':>14}    {'Savings':>7}{RESET}"
        )
        print(f"  {hline(62)}")

        # Rows
        for m in summary["modes"]:
            label = _mode_label(m["mode"])
            icon = _mode_icon(m["mode"])
            pct = m["savings_pct"]
            print(
                f"  {icon} {WHITE}{label:<20}{RESET} {m['operations']:>10,}   "
                f"{YELLOW}{m['tokens_saved']:>14,}{RESET}    {fmt_savings(pct)}"
            )

        # Total
        print(f"  {hline(62)}")
        total_pct = summary["total_savings_pct"]
        print(
            f"  {SAVED} {BOLD}{'TOTAL':<20}{RESET} {BOLD}{summary['total_operations']:>10,}{RESET}   "
            f"{BOLD}{YELLOW}{summary['total_tokens_saved']:>14,}{RESET}    "
            f"{BOLD}{fmt_savings(total_pct)}{RESET}"
        )

        if summary["est_cost_saved_monthly"] > 0:
            cost = summary["est_cost_saved_monthly"]
            print(
                f"  {DIM}  Est. cost saved{RESET}"
                f"{'':>21}{BRIGHT_GREEN}${cost:.2f}/month{RESET}"
            )

        print()

    def print_history(self, limit: int = 50) -> None:
        """Print recent command history."""
        from skim.style import BOLD, DIM, RESET, CYAN, YELLOW, GREEN, WHITE, hline

        rows = self._conn.execute(
            """SELECT timestamp, command, input_tokens, saved_tokens, mode
               FROM commands ORDER BY timestamp DESC LIMIT ?""",
            (limit,),
        ).fetchall()

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

    def print_daily(self, days: int = 30) -> None:
        """Print day-by-day breakdown."""
        from skim.style import BOLD, DIM, RESET, YELLOW, WHITE, GREEN, hline

        cutoff = time.time() - (days * 86400)
        rows = self._conn.execute(
            """SELECT date(timestamp, 'unixepoch', 'localtime') as day,
                      COUNT(*) as ops,
                      SUM(saved_tokens) as saved
               FROM commands
               WHERE timestamp >= ?
               GROUP BY day ORDER BY day""",
            (cutoff,),
        ).fetchall()

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

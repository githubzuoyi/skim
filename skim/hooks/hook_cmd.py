"""Hook command handlers for AI agent PreToolUse hooks.

These are called by agent hooks (not by users directly):
- ``skim hook claude`` — reads JSON from stdin, rewrites command, outputs JSON
- ``skim hook cursor`` — similar protocol for Cursor
- ``skim hook copilot`` — similar protocol for GitHub Copilot
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from skim.hooks.rewrite import rewrite_command, _CODE_EXTENSIONS


def cmd_hook(args) -> None:
    """Dispatch to the appropriate hook handler."""
    if args.agent == "claude":
        run_claude_hook()
    elif args.agent == "cursor":
        run_cursor_hook()
    elif args.agent == "copilot":
        run_copilot_hook()


def run_claude_hook() -> None:
    """Called by Claude Code PreToolUse hook.

    Reads hook JSON from stdin, rewrites the command if applicable,
    and outputs the rewrite instruction as JSON.

    Protocol (matching rtk's implementation):
    - Input: ``{"tool_name": "Bash", "tool_input": {"command": "cat file.py"}}``
    - Output: JSON with ``hookSpecificOutput`` containing rewritten command
    - No output = allow original command unchanged
    """
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return

        hook_input = json.loads(raw)
    except (json.JSONDecodeError, IOError):
        return

    tool_name = hook_input.get("tool_name", "")
    if tool_name != "Bash":
        return

    command = hook_input.get("tool_input", {}).get("command", "")
    if not command:
        return

    rewritten = rewrite_command(command)
    if rewritten and rewritten != command:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedToolInput": {"command": rewritten},
            }
        }
        print(json.dumps(output))


def run_cursor_hook() -> None:
    """Called by Cursor preToolUse hook.

    Similar to Claude but Cursor uses a slightly different JSON structure.

    Protocol:
    - Input: ``{"tool_name": "Shell", "tool_input": {"command": "cat file.py"}}``
    - Output: JSON with updated tool input
    """
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return

        hook_input = json.loads(raw)
    except (json.JSONDecodeError, IOError):
        return

    tool_name = hook_input.get("tool_name", "")
    if tool_name != "Shell":
        return

    command = hook_input.get("tool_input", {}).get("command", "")
    if not command:
        return

    rewritten = rewrite_command(command)
    if rewritten and rewritten != command:
        output = {
            "permissionDecision": "allow",
            "updatedToolInput": {"command": rewritten},
        }
        print(json.dumps(output))


def run_copilot_hook() -> None:
    """Called by GitHub Copilot PreToolUse hook (.github/hooks/skim-rewrite.json).

    Handles two types of tool calls:
    1. Shell commands (Bash/terminal) — rewrites cat/head/tail → skim read
    2. read_file — transparently redirects large code files to a
       structural summary written to a temp file
    """
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return

        hook_input = json.loads(raw)
    except (json.JSONDecodeError, IOError):
        return

    tool_name = hook_input.get("tool_name", "")

    if tool_name in ("Bash", "terminal", "runCommand"):
        _handle_shell_command(hook_input)
    elif tool_name == "read_file":
        _handle_read_file(hook_input)


def _handle_shell_command(hook_input: dict) -> None:
    """Rewrite shell commands (cat/head/tail/git) to skim equivalents."""
    command = hook_input.get("tool_input", {}).get("command", "")
    if not command:
        return

    rewritten = rewrite_command(command)
    if rewritten and rewritten != command:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedToolInput": {"command": rewritten},
            }
        }
        print(json.dumps(output))


def _handle_read_file(hook_input: dict) -> None:
    """Intercept read_file on large code files → return structural summary.

    Runs ``skim read <file>`` in a subprocess, writes the output to a temp
    file, and returns updatedToolInput pointing to it. The AI sees the
    structural summary transparently — no behavior change needed.
    """
    tool_input = hook_input.get("tool_input", {})
    file_path = tool_input.get("path") or tool_input.get("filePath") or ""
    if not file_path:
        return

    path = Path(file_path)
    if not path.suffix or path.suffix not in _CODE_EXTENSIONS:
        return

    if not path.exists() or not path.is_file():
        return

    try:
        line_count = sum(1 for _ in open(path, "rb"))
    except OSError:
        return

    if line_count < 150:
        return

    try:
        result = subprocess.run(
            [sys.executable, "-m", "skim", "read", str(path)],
            capture_output=True, text=True, timeout=4,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return

    if result.returncode != 0 or not result.stdout.strip():
        return

    tmp_dir = Path("/tmp/skim-hook")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    safe_name = str(path.resolve()).replace("/", "__")
    tmp_file = tmp_dir / safe_name
    tmp_file.write_text(result.stdout)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedToolInput": {"path": str(tmp_file)},
        }
    }
    print(json.dumps(output))

"""Hook command handlers for AI agent PreToolUse hooks.

These are called by agent hooks (not by users directly):
- ``skim hook claude`` — reads JSON from stdin, rewrites command, outputs JSON
- ``skim hook cursor`` — similar protocol for Cursor
"""

from __future__ import annotations

import json
import sys

from skim.hooks.rewrite import rewrite_command


def cmd_hook(args) -> None:
    """Dispatch to the appropriate hook handler."""
    if args.agent == "claude":
        run_claude_hook()
    elif args.agent == "cursor":
        run_cursor_hook()


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

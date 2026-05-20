"""Hook command handlers for AI agent PreToolUse hooks.

These are called by agent hooks (not by users directly):
- ``skim hook claude`` — reads JSON from stdin, rewrites command, outputs JSON
- ``skim hook codex`` — compatible with Codex PreToolUse JSON
- ``skim hook cursor`` — similar protocol for Cursor
- ``skim hook copilot`` — similar protocol for GitHub Copilot
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


_HOOK_TMP_DIR = Path("/tmp/skim-hook")
_HOOK_SUMMARY_VERSION = 6


def cmd_hook(args) -> None:
    """Dispatch to the appropriate hook handler."""
    if args.agent == "claude":
        run_claude_hook()
    elif args.agent == "codex":
        run_codex_hook()
    elif args.agent == "cursor":
        run_cursor_hook()
    elif args.agent == "copilot":
        run_copilot_hook()


def run_codex_hook() -> None:
    """Called by Codex PreToolUse hook.

    Codex currently uses the same Bash-oriented hook payload as Claude Code,
    so it can reuse the same rewrite handler.
    """
    run_claude_hook()


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

    from skim.hooks.rewrite import rewrite_command

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

    from skim.hooks.rewrite import rewrite_command

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

    if tool_name in ("Bash", "terminal", "runCommand", "run_in_terminal"):
        _handle_shell_command(hook_input)
    elif tool_name == "read_file":
        _handle_read_file(hook_input)


def _handle_shell_command(hook_input: dict) -> None:
    """Rewrite shell commands (cat/head/tail/git) to skim equivalents."""
    tool_input = hook_input.get("tool_input", {})
    command = tool_input.get("command", "")
    if not command:
        return

    from skim.hooks.rewrite import rewrite_command

    rewritten = rewrite_command(command)
    if rewritten and rewritten != command:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedInput": {
                    **tool_input,
                    "command": rewritten,
                },
            }
        }
        print(json.dumps(output))


def _hook_cache_paths(path: Path) -> tuple[Path, Path, Path]:
    safe_name = str(path.resolve()).replace("/", "__")
    output_file = _HOOK_TMP_DIR / safe_name
    summary_file = _HOOK_TMP_DIR / f"{safe_name}.summary"
    meta_file = _HOOK_TMP_DIR / f"{safe_name}.meta.json"
    return output_file, summary_file, meta_file


def _load_cached_summary(path: Path, source_stat) -> tuple[str, str] | None:
    _, summary_file, meta_file = _hook_cache_paths(path)
    if not summary_file.exists() or not meta_file.exists():
        return None

    try:
        meta = json.loads(meta_file.read_text())
        summary = summary_file.read_text()
    except (json.JSONDecodeError, OSError):
        return None

    if meta.get("summary_version") != _HOOK_SUMMARY_VERSION:
        return None
    if meta.get("mtime_ns") != source_stat.st_mtime_ns:
        return None
    if meta.get("size") != source_stat.st_size:
        return None
    if not summary.strip():
        return None

    return summary, meta.get("mode", "structural")


def _store_cached_summary(path: Path, source_stat, summary: str, mode: str) -> None:
    _, summary_file, meta_file = _hook_cache_paths(path)
    _HOOK_TMP_DIR.mkdir(parents=True, exist_ok=True)

    summary_file.write_text(summary)
    meta_file.write_text(
        json.dumps(
            {
                "summary_version": _HOOK_SUMMARY_VERSION,
                "mtime_ns": source_stat.st_mtime_ns,
                "size": source_stat.st_size,
                "mode": mode,
            }
        )
    )


def _build_read_output(path: Path) -> tuple[str, str] | None:
    try:
        source_stat = path.stat()
    except OSError:
        return None

    cached = _load_cached_summary(path, source_stat)
    if cached is not None:
        return cached

    try:
        from skim.ast_engine import structural_read
    except Exception:
        return None

    try:
        result = structural_read(path)
    except Exception:
        return None

    if not result.content.strip():
        return None

    try:
        _store_cached_summary(path, source_stat, result.content, result.mode)
    except OSError:
        pass

    return result.content, result.mode


def _materialize_hook_output(path: Path, summary: str, summary_mode: str) -> str | None:
    from skim.commands import _report

    try:
        raw_content = path.read_text(encoding="utf-8", errors="replace")
        _report(f"read {path}", raw_content, summary, summary_mode)
    except OSError:
        return None

    return summary


def _handle_read_file(hook_input: dict) -> None:
    """Intercept read_file on large code files → return structural summary.

    Builds the structural summary in-process, writes the output to a temp
    file, and returns updatedInput pointing to it. The AI sees the
    structural summary transparently — no behavior change needed.
    """
    tool_input = hook_input.get("tool_input", {})
    file_path = tool_input.get("path") or tool_input.get("filePath") or ""
    if not file_path:
        return

    start_line = tool_input.get("startLine")
    end_line = tool_input.get("endLine")

    # Only redirect broad top-of-file reads. Targeted line reads should keep
    # using the native tool so the model can inspect exact surrounding code.
    if isinstance(start_line, int) and start_line > 1:
        return
    if isinstance(end_line, int) and isinstance(start_line, int):
        if (end_line - start_line + 1) < 100:
            return

    path = Path(file_path)
    from skim.hooks.rewrite import _CODE_EXTENSIONS

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

    built = _build_read_output(path)
    if built is None:
        return
    summary, summary_mode = built

    output_text = _materialize_hook_output(path, summary, summary_mode)
    if output_text is None or not output_text.strip():
        return

    tmp_file, _, _ = _hook_cache_paths(path)
    _HOOK_TMP_DIR.mkdir(parents=True, exist_ok=True)
    tmp_file.write_text(output_text)

    updated_input = dict(tool_input)
    if "filePath" in updated_input:
        updated_input["filePath"] = str(tmp_file)
    elif "path" in updated_input:
        updated_input["path"] = str(tmp_file)
    else:
        updated_input["filePath"] = str(tmp_file)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": updated_input,
        }
    }
    print(json.dumps(output))

"""Command rewriting logic for hook interception.

Rewrites shell commands into their skim equivalents. For example:
- ``cat file.py`` → ``skim read file.py``
- ``git status`` → ``skim git status``
- ``head -50 file.py`` → ``skim read file.py``

Handles compound commands (``&&``, ``||``, ``;``) by rewriting each part.
"""

from __future__ import annotations

import re
import shlex

# File extensions that skim can parse with tree-sitter
_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".rs", ".go", ".java", ".rb",
    ".c", ".cpp", ".h", ".hpp",
    ".cs", ".kt", ".scala", ".swift",
}

# Commands that should never be rewritten
_EXCLUDE_COMMANDS = {"curl", "wget", "ssh", "scp", "docker", "kubectl", "brew"}


# ---------------------------------------------------------------------------
# Rewrite rules
# ---------------------------------------------------------------------------

def _is_code_file(arg: str) -> bool:
    """Check if an argument looks like a code file path."""
    for ext in _CODE_EXTENSIONS:
        if arg.endswith(ext):
            return True
    return False


def _rewrite_cat(parts: list[str]) -> str | None:
    """Rewrite ``cat file.py`` → ``skim read file.py``."""
    if len(parts) < 2:
        return None
    # cat with flags like -n, -b → don't rewrite
    if any(p.startswith("-") for p in parts[1:]):
        return None
    file_arg = parts[1]
    if _is_code_file(file_arg):
        return f"skim read {file_arg}"
    return None


def _rewrite_head(parts: list[str]) -> str | None:
    """Rewrite ``head [-n N] file`` → ``skim read file``."""
    file_arg = None
    i = 1
    while i < len(parts):
        if parts[i] in ("-n", "-c"):
            i += 2
            continue
        if parts[i].startswith("-"):
            i += 1
            continue
        file_arg = parts[i]
        break

    if file_arg and _is_code_file(file_arg):
        return f"skim read {file_arg}"
    return None


def _rewrite_tail(parts: list[str]) -> str | None:
    """Rewrite ``tail file.py`` → ``skim read file.py``."""
    file_arg = None
    i = 1
    while i < len(parts):
        if parts[i] in ("-n", "-c"):
            i += 2
            continue
        if parts[i].startswith("-"):
            i += 1
            continue
        file_arg = parts[i]
        break

    if file_arg and _is_code_file(file_arg):
        return f"skim read {file_arg}"
    return None


def _rewrite_git(parts: list[str]) -> str | None:
    """Rewrite git commands to skim git equivalents."""
    if len(parts) < 2:
        return None
    subcmd = parts[1]
    if subcmd in ("status", "diff", "log"):
        rest = " ".join(parts[1:])
        return f"skim git {rest}"
    return None


# ---------------------------------------------------------------------------
# Rule table
# ---------------------------------------------------------------------------

_REWRITE_TABLE: dict[str, object] = {
    "cat": _rewrite_cat,
    "head": _rewrite_head,
    "tail": _rewrite_tail,
    "git": _rewrite_git,
}


# ---------------------------------------------------------------------------
# Compound command splitting
# ---------------------------------------------------------------------------

_COMPOUND_PATTERN = re.compile(r"\s*(&&|\|\||;)\s*")


def _split_compound(cmd: str) -> list[tuple[str, str]]:
    """Split a compound command into (part, separator) tuples.

    Returns list of (command_part, separator_after). The last item has
    an empty separator.
    """
    parts: list[tuple[str, str]] = []
    remaining = cmd
    while True:
        m = _COMPOUND_PATTERN.search(remaining)
        if m:
            parts.append((remaining[: m.start()].strip(), m.group(1)))
            remaining = remaining[m.end() :]
        else:
            parts.append((remaining.strip(), ""))
            break
    return parts


def _join_compound(parts: list[tuple[str, str]]) -> str:
    """Rejoin compound command parts."""
    result: list[str] = []
    for cmd_part, sep in parts:
        result.append(cmd_part)
        if sep:
            result.append(f" {sep} ")
    return "".join(result)


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def rewrite_command(cmd: str) -> str | None:
    """Rewrite a shell command to its skim equivalent.

    Returns the rewritten command, or None if no rewrite applies.
    Handles compound commands with ``&&``, ``||``, and ``;``.
    """
    cmd = cmd.strip()
    if not cmd:
        return None

    # Don't rewrite if already a skim command
    if cmd.startswith("skim "):
        return None

    compound_parts = _split_compound(cmd)
    any_rewritten = False
    new_parts: list[tuple[str, str]] = []

    for part, sep in compound_parts:
        rewritten = _rewrite_single(part)
        if rewritten:
            new_parts.append((rewritten, sep))
            any_rewritten = True
        else:
            new_parts.append((part, sep))

    if any_rewritten:
        return _join_compound(new_parts)
    return None


def _rewrite_single(cmd: str) -> str | None:
    """Rewrite a single (non-compound) command."""
    cmd = cmd.strip()
    if not cmd:
        return None

    # Pipe handling: only rewrite the first command in a pipe
    if "|" in cmd and "||" not in cmd:
        pipe_parts = cmd.split("|", 1)
        rewritten_first = _rewrite_single(pipe_parts[0].strip())
        if rewritten_first:
            return f"{rewritten_first} | {pipe_parts[1].strip()}"
        return None

    try:
        parts = shlex.split(cmd)
    except ValueError:
        parts = cmd.split()

    if not parts:
        return None

    base_cmd = parts[0]

    # Skip excluded commands
    if base_cmd in _EXCLUDE_COMMANDS:
        return None

    # Look up rewrite handler
    handler = _REWRITE_TABLE.get(base_cmd)
    if handler:
        return handler(parts)

    return None

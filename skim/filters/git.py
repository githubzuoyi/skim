"""Git command output compression filters.

Compresses git status/diff/log output to reduce tokens while preserving
all actionable information.
"""

from __future__ import annotations

import subprocess
import re


def run_git(args: list[str]) -> tuple[str, str]:
    """Run a git command and return (raw_output, compressed_output).

    Dispatches to specialized compressors for known subcommands,
    falls back to raw output for unknown ones.
    """
    if not args:
        return "", ""

    subcmd = args[0]
    rest = args[1:]

    if subcmd == "status":
        return _git_status(rest)
    elif subcmd == "diff":
        return _git_diff(rest)
    elif subcmd == "log":
        return _git_log(rest)
    elif subcmd in ("add", "commit", "push", "pull", "fetch", "checkout", "switch"):
        return _git_passthrough(args)
    else:
        return _git_passthrough(args)


# ---------------------------------------------------------------------------
# git status
# ---------------------------------------------------------------------------

def _git_status(args: list[str]) -> tuple[str, str]:
    """Compress git status using porcelain format.

    Converts verbose status output to a compact table:
      M  src/main.py
      A  src/new.py
      ?? untracked.txt
    """
    raw = _run(["git", "status"] + args)

    porcelain = _run(["git", "status", "--porcelain=v1"] + args)

    if not porcelain.strip():
        return raw, "working tree clean"

    lines = porcelain.strip().split("\n")

    # Group by status
    modified: list[str] = []
    added: list[str] = []
    deleted: list[str] = []
    renamed: list[str] = []
    untracked: list[str] = []
    other: list[str] = []

    for line in lines:
        if len(line) < 4:
            continue
        status = line[:2]
        filepath = line[3:]

        if "M" in status:
            modified.append(filepath)
        elif "A" in status:
            added.append(filepath)
        elif "D" in status:
            deleted.append(filepath)
        elif "R" in status:
            renamed.append(filepath)
        elif "?" in status:
            untracked.append(filepath)
        else:
            other.append(f"{status.strip()} {filepath}")

    # Get branch info
    branch_info = _run(["git", "branch", "--show-current"]).strip()
    ahead_behind = _get_ahead_behind()

    parts: list[str] = []
    parts.append(f"branch: {branch_info}{ahead_behind}")

    if modified:
        parts.append(f"modified ({len(modified)}): {', '.join(modified)}")
    if added:
        parts.append(f"added ({len(added)}): {', '.join(added)}")
    if deleted:
        parts.append(f"deleted ({len(deleted)}): {', '.join(deleted)}")
    if renamed:
        parts.append(f"renamed ({len(renamed)}): {', '.join(renamed)}")
    if untracked:
        if len(untracked) <= 10:
            parts.append(f"untracked ({len(untracked)}): {', '.join(untracked)}")
        else:
            parts.append(f"untracked ({len(untracked)}): {', '.join(untracked[:5])}, +{len(untracked)-5} more")
    if other:
        parts.append(f"other: {', '.join(other)}")

    return raw, "\n".join(parts)


def _get_ahead_behind() -> str:
    """Get ahead/behind count relative to upstream."""
    try:
        result = _run(["git", "rev-list", "--left-right", "--count", "HEAD...@{upstream}"])
        parts = result.strip().split("\t")
        if len(parts) == 2:
            ahead, behind = int(parts[0]), int(parts[1])
            markers: list[str] = []
            if ahead:
                markers.append(f"↑{ahead}")
            if behind:
                markers.append(f"↓{behind}")
            if markers:
                return " " + " ".join(markers)
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# git diff
# ---------------------------------------------------------------------------

def _git_diff(args: list[str]) -> tuple[str, str]:
    """Compress git diff output.

    Keeps file headers and hunk headers, strips context lines beyond
    a minimal window, and adds a summary line.
    """
    raw = _run(["git", "diff"] + args)

    if not raw.strip():
        return raw, "no changes"

    lines = raw.split("\n")
    compressed: list[str] = []
    files_changed = 0
    insertions = 0
    deletions = 0

    in_hunk = False
    context_count = 0
    max_context = 2

    for line in lines:
        if line.startswith("diff --git"):
            files_changed += 1
            in_hunk = False
            compressed.append(line)
        elif line.startswith("---") or line.startswith("+++"):
            compressed.append(line)
        elif line.startswith("@@"):
            in_hunk = True
            context_count = 0
            compressed.append(line)
        elif in_hunk:
            if line.startswith("+") and not line.startswith("+++"):
                insertions += 1
                context_count = 0
                compressed.append(line)
            elif line.startswith("-") and not line.startswith("---"):
                deletions += 1
                context_count = 0
                compressed.append(line)
            else:
                context_count += 1
                if context_count <= max_context:
                    compressed.append(line)

    summary = f"// {files_changed} files, +{insertions} -{deletions}"
    compressed.insert(0, summary)

    return raw, "\n".join(compressed)


# ---------------------------------------------------------------------------
# git log
# ---------------------------------------------------------------------------

def _git_log(args: list[str]) -> tuple[str, str]:
    """Compress git log to one-line format."""
    # If user already specified --oneline, just pass through
    if "--oneline" in args or "--format" in " ".join(args):
        raw = _run(["git", "log"] + args)
        return raw, raw

    # Use compact format
    compact_args = ["--oneline", "--no-decorate", "-20"]
    # Preserve any user-specified flags
    for arg in args:
        if arg.startswith("-") and arg not in ("--oneline", "--no-decorate"):
            compact_args.append(arg)
        elif not arg.startswith("-"):
            compact_args.append(arg)

    raw = _run(["git", "log"] + args)
    compact = _run(["git", "log"] + compact_args)

    return raw, compact.strip()


# ---------------------------------------------------------------------------
# Passthrough with summary
# ---------------------------------------------------------------------------

def _git_passthrough(args: list[str]) -> tuple[str, str]:
    """Run git command and return output with minimal compression."""
    raw = _run(["git"] + args)

    # For short output, return as-is
    lines = raw.split("\n")
    if len(lines) <= 20:
        return raw, raw.strip()

    # For long output, keep first and last lines
    parts = lines[:10]
    parts.append(f"// ... {len(lines) - 15} lines omitted ...")
    parts.extend(lines[-5:])
    return raw, "\n".join(parts)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run(cmd: list[str]) -> str:
    """Run a subprocess and return stdout."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout + result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""

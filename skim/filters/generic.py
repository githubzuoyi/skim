"""Generic output compression for miscellaneous commands.

Handles commands that don't have specialized filters by applying
general compression strategies.
"""

from __future__ import annotations

import subprocess


def run_command_filtered(cmd: list[str]) -> tuple[str, str]:
    """Run any command and apply generic compression.

    Returns (raw_output, compressed_output).
    """
    raw = _run(cmd)

    if not raw.strip():
        return raw, "no output"

    lines = raw.split("\n")

    # Short output: return as-is
    if len(lines) <= 30:
        return raw, raw.strip()

    # Group by file if output looks like file-grouped results (grep, rg, etc.)
    if _looks_like_file_grouped(lines):
        return raw, _compress_file_grouped(lines)

    # Generic: head + tail
    compressed: list[str] = []
    compressed.extend(lines[:15])
    compressed.append(f"// ... {len(lines) - 20} lines omitted ...")
    compressed.extend(lines[-5:])

    return raw, "\n".join(compressed)


def _looks_like_file_grouped(lines: list[str]) -> bool:
    """Detect if output looks like file-grouped search results."""
    colon_lines = sum(1 for l in lines[:20] if ":" in l and len(l.split(":")[0]) < 100)
    return colon_lines > len(lines[:20]) * 0.5


def _compress_file_grouped(lines: list[str]) -> str:
    """Compress file-grouped output (like grep/rg) by grouping matches."""
    files: dict[str, list[str]] = {}
    for line in lines:
        if not line.strip():
            continue
        if ":" in line:
            parts = line.split(":", 2)
            if len(parts) >= 2:
                filepath = parts[0]
                files.setdefault(filepath, []).append(line)
            else:
                files.setdefault("_other", []).append(line)
        else:
            files.setdefault("_other", []).append(line)

    compressed: list[str] = []
    for filepath, matches in files.items():
        if filepath == "_other":
            compressed.extend(matches[:5])
            continue
        if len(matches) <= 3:
            compressed.extend(matches)
        else:
            compressed.extend(matches[:2])
            compressed.append(f"  // ... +{len(matches) - 2} more matches in {filepath}")

    total_matches = sum(len(v) for v in files.values())
    compressed.append(f"// {len(files)} files, {total_matches} matches")

    return "\n".join(compressed)


def _run(cmd: list[str]) -> str:
    """Run a subprocess and return combined output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout + result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return f"Error: {e}"

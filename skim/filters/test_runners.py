"""Test runner output compression.

Compresses output from pytest, cargo test, npm test, etc. to show
only failures and a compact summary.
"""

from __future__ import annotations

import subprocess
import re


def run_test(args: list[str]) -> tuple[str, str]:
    """Run a test command and return (raw_output, compressed_output)."""
    if not args:
        return "", ""

    cmd = args[0]

    if cmd == "pytest" or (cmd == "python" and len(args) > 1 and args[1] == "-m" and len(args) > 2 and args[2] == "pytest"):
        return _run_pytest(args)
    elif cmd == "cargo" and len(args) > 1 and args[1] == "test":
        return _run_cargo_test(args)
    elif cmd == "npm" and len(args) > 1 and args[1] == "test":
        return _run_npm_test(args)
    elif cmd == "npx" and len(args) > 1 and ("jest" in args[1] or "vitest" in args[1]):
        return _run_npm_test(args)
    elif cmd == "go" and len(args) > 1 and args[1] == "test":
        return _run_go_test(args)
    else:
        return _run_generic_test(args)


# ---------------------------------------------------------------------------
# pytest
# ---------------------------------------------------------------------------

_PYTEST_FAIL_PATTERN = re.compile(r"^(FAILED|ERROR)\s+", re.MULTILINE)
_PYTEST_SUMMARY_PATTERN = re.compile(r"^=+\s*(.*(?:passed|failed|error|warning).*?)\s*=+$", re.MULTILINE)


def _run_pytest(args: list[str]) -> tuple[str, str]:
    """Compress pytest output: show failures and summary only."""
    raw = _run(args)

    if not raw.strip():
        return raw, "no output"

    lines = raw.split("\n")
    compressed: list[str] = []

    # Extract summary line
    summary_match = _PYTEST_SUMMARY_PATTERN.search(raw)
    summary = summary_match.group(1).strip() if summary_match else None

    # Check for all-pass
    if summary and "failed" not in summary.lower() and "error" not in summary.lower():
        compressed.append(f"✓ {summary}")
        return raw, "\n".join(compressed)

    # Extract failure sections
    in_failure = False
    failure_lines: list[str] = []

    for line in lines:
        if "FAILURES" in line and "=" in line:
            in_failure = True
            continue
        if in_failure:
            if line.startswith("=") and "short test summary" in line.lower():
                in_failure = False
                continue
            if line.startswith("=") and len(line) > 10:
                in_failure = False
                continue
            failure_lines.append(line)

    # Short test summary (most useful)
    in_short_summary = False
    short_summary: list[str] = []
    for line in lines:
        if "short test summary" in line.lower():
            in_short_summary = True
            continue
        if in_short_summary:
            if line.startswith("=") and len(line) > 10:
                break
            if line.strip():
                short_summary.append(line.strip())

    if short_summary:
        compressed.append("FAILURES:")
        compressed.extend(short_summary)
    elif failure_lines:
        # Keep first 30 lines of failure detail
        if len(failure_lines) > 30:
            compressed.append("FAILURES:")
            compressed.extend(failure_lines[:30])
            compressed.append(f"// ... {len(failure_lines) - 30} more failure lines")
        else:
            compressed.append("FAILURES:")
            compressed.extend(failure_lines)

    if summary:
        compressed.append("")
        compressed.append(summary)

    if not compressed:
        compressed.append(raw.strip()[:500])

    return raw, "\n".join(compressed)


# ---------------------------------------------------------------------------
# cargo test
# ---------------------------------------------------------------------------

def _run_cargo_test(args: list[str]) -> tuple[str, str]:
    """Compress cargo test output: show failures and summary."""
    raw = _run(args)

    if not raw.strip():
        return raw, "no output"

    lines = raw.split("\n")
    compressed: list[str] = []

    # Check for all-pass
    result_line = None
    for line in lines:
        if line.strip().startswith("test result:"):
            result_line = line.strip()

    if result_line and "FAILED" not in result_line.upper():
        compressed.append(f"✓ {result_line}")
        return raw, "\n".join(compressed)

    # Extract failures
    in_failure = False
    for line in lines:
        if "---- " in line and " ----" in line:
            in_failure = True
            compressed.append(line)
        elif in_failure:
            if line.strip().startswith("failures:") or line.strip().startswith("test result:"):
                in_failure = False
                compressed.append(line)
            elif line.strip():
                compressed.append(line)
        elif "FAILED" in line:
            compressed.append(line)

    if result_line:
        compressed.append(result_line)

    if not compressed:
        compressed.append(raw.strip()[:500])

    return raw, "\n".join(compressed)


# ---------------------------------------------------------------------------
# npm test / jest / vitest
# ---------------------------------------------------------------------------

def _run_npm_test(args: list[str]) -> tuple[str, str]:
    """Compress npm test/jest/vitest output."""
    raw = _run(args)

    if not raw.strip():
        return raw, "no output"

    lines = raw.split("\n")
    compressed: list[str] = []

    # Extract test summary lines (Tests:, Test Suites:, Time:)
    summary_lines: list[str] = []
    fail_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("Tests:", "Test Suites:", "Time:", "Ran all test suites")):
            summary_lines.append(stripped)
        elif "FAIL" in stripped and ("●" in stripped or "✕" in stripped or "FAIL " in stripped):
            fail_lines.append(stripped)
        elif stripped.startswith("FAIL "):
            fail_lines.append(stripped)

    # Check all-pass
    has_failures = any("fail" in s.lower() for s in summary_lines) or fail_lines

    if not has_failures and summary_lines:
        compressed.append("✓ " + " | ".join(summary_lines))
        return raw, "\n".join(compressed)

    if fail_lines:
        compressed.append("FAILURES:")
        compressed.extend(fail_lines[:20])

    if summary_lines:
        compressed.append("")
        compressed.extend(summary_lines)

    if not compressed:
        if len(lines) > 20:
            compressed = lines[:10] + [f"// ... {len(lines) - 15} lines ..."] + lines[-5:]
        else:
            compressed = lines

    return raw, "\n".join(compressed)


# ---------------------------------------------------------------------------
# go test
# ---------------------------------------------------------------------------

def _run_go_test(args: list[str]) -> tuple[str, str]:
    """Compress go test output."""
    raw = _run(args)

    if not raw.strip():
        return raw, "no output"

    lines = raw.split("\n")
    compressed: list[str] = []

    has_fail = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("--- FAIL"):
            has_fail = True
            compressed.append(stripped)
        elif stripped.startswith("FAIL"):
            has_fail = True
            compressed.append(stripped)
        elif stripped.startswith("ok"):
            compressed.append(stripped)

    if not has_fail:
        passed = [l for l in compressed if l.startswith("ok")]
        if passed:
            return raw, "✓ " + " | ".join(passed)

    if not compressed:
        compressed.append(raw.strip()[:500])

    return raw, "\n".join(compressed)


# ---------------------------------------------------------------------------
# Generic test runner
# ---------------------------------------------------------------------------

def _run_generic_test(args: list[str]) -> tuple[str, str]:
    """Generic test output compression."""
    raw = _run(args)

    if not raw.strip():
        return raw, "no output"

    lines = raw.split("\n")
    if len(lines) <= 20:
        return raw, raw.strip()

    compressed = lines[:10]
    compressed.append(f"// ... {len(lines) - 15} lines ...")
    compressed.extend(lines[-5:])
    return raw, "\n".join(compressed)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run(cmd: list[str]) -> str:
    """Run a subprocess and return combined output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.stdout + result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return f"Error running {' '.join(cmd)}: {e}"

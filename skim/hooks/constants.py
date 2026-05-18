"""Constants for hook installation and handling."""

from __future__ import annotations


COPILOT_LAUNCHER_FILENAME = "skim-launcher.sh"
COPILOT_LAUNCHER_COMMAND = f"/bin/sh ./.github/hooks/{COPILOT_LAUNCHER_FILENAME} copilot"

COPILOT_LAUNCHER_SH = """#!/bin/sh
set -eu

agent="${1:-copilot}"

if [ -n "${SKIM_BIN:-}" ] && [ -x "${SKIM_BIN}" ]; then
    exec "${SKIM_BIN}" hook "${agent}"
fi

if command -v skim >/dev/null 2>&1; then
    exec skim hook "${agent}"
fi

if [ -n "${SKIM_PYTHON:-}" ] && command -v "${SKIM_PYTHON}" >/dev/null 2>&1; then
    if "${SKIM_PYTHON}" -c 'import skim' >/dev/null 2>&1; then
        exec "${SKIM_PYTHON}" -m skim hook "${agent}"
    fi
fi

for python_cmd in python3 python; do
    if command -v "${python_cmd}" >/dev/null 2>&1; then
        if "${python_cmd}" -c 'import skim' >/dev/null 2>&1; then
            exec "${python_cmd}" -m skim hook "${agent}"
        fi
    fi
done

for candidate in \
    "${HOME}/.local/bin/skim" \
    "${HOME}/miniforge3/bin/skim" \
    "${HOME}/miniconda3/bin/skim" \
    "${HOME}/anaconda3/bin/skim" \
    "${HOME}/.pyenv/shims/skim"
do
    if [ -x "${candidate}" ]; then
        exec "${candidate}" hook "${agent}"
    fi
done

echo "skim hook launcher: unable to find skim. Install skim or set SKIM_BIN / SKIM_PYTHON." >&2
exit 127
"""

# Claude Code hook JSON structure (PreToolUse)
CLAUDE_HOOK = {
    "matcher": "Bash",
    "hooks": [
        {
            "type": "command",
            "command": "skim hook claude",
        }
    ],
}

# Cursor hook JSON structure (preToolUse)
CURSOR_HOOK_CONFIG = {
    "hooks": {
        "preToolUse": [
            {
                "command": "skim hook cursor",
                "matcher": "Shell",
            }
        ]
    }
}

# Copilot hook JSON structure (.github/hooks/skim-rewrite.json)
COPILOT_HOOK_JSON = {
    "hooks": {
        "PreToolUse": [
            {
                "type": "command",
                "command": COPILOT_LAUNCHER_COMMAND,
                "cwd": ".",
                "timeout": 5,
            }
        ]
    }
}

# Copilot instructions (.github/copilot-instructions.md)
COPILOT_INSTRUCTIONS = """\
---
description: skim is installed. Large code files are automatically summarized when read. Use skim read for drill-down.
applyTo: "**/*.{py,ts,tsx,js,jsx,rs,go,java,rb,c,cpp,h,hpp,swift,kt}"
---

# skim — Token-Efficient Code Reading

This project has `skim` installed. It **automatically intercepts** your
file reads on large code files (>150 lines) and returns a structural
summary (function/class signatures) instead of the full content.
This happens transparently — you don't need to change how you work.

## What you'll see

When you read a large code file, you'll get something like:

```
// src/auth/service.py  487 lines  4 exports  12 symbols
// imports: hashlib, secrets, datetime, ...

class AuthService
    def __init__(self, repo: UserRepository, secret: str)
    async def login(self, email: str, password: str) -> AuthResult
    async def logout(self, session_id: str) -> None
    def verify_token(self, token: str) -> dict

// [487 lines → 15 lines · 97% reduction]
// [skim tokens ~3,084 -> ~182, saved ~2,902 (94%)]
// [skim read src/auth/service.py:<symbol> for full function]
```

## Drill into specific functions

When you need the implementation of a specific function, run in terminal:

```bash
skim read src/auth/service.py:login          # specific function
skim read src/auth/service.py:AuthService    # entire class
```

## Get complete file content

When you need the full file (e.g., before editing), run in terminal:

```bash
skim read src/auth/service.py --full
```

## Git & test commands

```bash
skim git status    # compact status output
skim git diff      # compressed diff
skim test pytest   # failures-only summary
```

## Analytics

Run `skim gain` in terminal to see cumulative token savings.
"""

# SKIM.md content to add as agent instructions
SKILL_CONTENT = """\
## skim - Smart File Reading

skim reduces token consumption by providing structural summaries of files
instead of raw content. Use the following commands:

### File Reading
- `skim read <path>` — Structural summary (function/class signatures)
- `skim read <path>:<function_name>` — Read a specific function/class
- `skim read <path>:Class.method` — Read a specific method
- `skim read <path> --full` — Full file content (when you need everything)

### Git Operations
- `skim git status` — Compact git status
- `skim git diff` — Compressed diff output
- `skim git log` — Compact log format

### Tips
- Use structural summaries first, then request specific symbols
- Structural summaries now show approximate original/current/saved token counts inline
- Run `skim gain` to see cumulative token savings statistics
"""

# Content to patch into CLAUDE.md
CLAUDE_MD_PATCH = """\

# skim instructions
See SKIM.md for smart file reading commands that reduce token usage.
Use `skim read` instead of `cat` for code files.
"""

# Cursor rule file content (.cursor/rules/skim.mdc)
_CURSOR_RULE_CONTENT = """\
---
description: Use skim for token-efficient code exploration and git operations
globs:
alwaysApply: true
---

# skim — Token-Efficient Code Reading

This project has `skim` installed. Use it to reduce token consumption when exploring code.

## When to use `skim read` (via Shell tool)

Use `skim read` instead of the Read tool when:
- **Exploring unfamiliar files** — `skim read src/auth.py` returns function/class signatures only (80-97% fewer tokens)
- **Getting an overview** of a large file (>150 lines) before deciding what to edit
- **Reading a specific function** — `skim read src/auth.py:login` returns just that function's body
- **Re-reading a file** you already read — skim returns `[unchanged]` if nothing changed

```bash
skim read <file>              # structural summary (signatures only)
skim read <file>:<symbol>     # read specific function/class/method
skim read <file>:Class.method # read a specific method
skim read <file> --full       # full content when you need everything
```

## When to use the normal Read tool

Use the built-in Read tool (not skim) when:
- You are about to **edit** a file and need exact line content for StrReplace
- You need to see **exact indentation, whitespace, or formatting**
- The file is small (<150 lines) — skim returns it in full anyway
- You need to read a **non-code file** (JSON, YAML, TOML, Markdown, etc.)

## Git operations

Use `skim git` for compressed git output:

```bash
skim git status    # compact: "branch: main, modified (3): a.py, b.py, c.py"
skim git diff      # compressed diff (keeps hunks, strips noise)
skim git log       # one-line format
```

## Test output

```bash
skim test pytest           # failures only + summary line
skim test cargo test       # failures only
skim test npm test         # failures only
```

## Workflow pattern

1. **Explore first**: `skim read file.py` → see structure (16 functions, 3 classes)
2. **Drill in**: `skim read file.py:process_request` → see the function you need
3. **Edit**: use Read tool on just the lines you need, then StrReplace
4. **Verify**: `skim git diff` to check changes

## Analytics

Run `skim gain` to see cumulative token savings.
"""

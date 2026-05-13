"""Constants for hook installation and handling."""

from __future__ import annotations

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
- skim automatically deduplicates: re-reading unchanged files returns "[unchanged]"
- Run `skim gain` to see token savings statistics
"""

# Content to patch into CLAUDE.md
CLAUDE_MD_PATCH = """\

# skim instructions
See SKIM.md for smart file reading commands that reduce token usage.
Use `skim read` instead of `cat` for code files.
"""

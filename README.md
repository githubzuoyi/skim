# skim

**Stop reading every line. Start skimming. 80-97% fewer tokens on file reads.**

[![PyPI version](https://img.shields.io/pypi/v/skimcode.svg)](https://pypi.org/project/skimcode/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

skim is an AST-aware token optimizer for AI coding agents. It intercepts file reads and command output, returning **structural summaries** instead of raw content — saving 80-97% of tokens on every operation.

Works with **Claude Code**, **Cursor**, **Copilot**, **Codex**, **Gemini CLI**, **Windsurf**, and **Cline**.

---

## Before vs After

### Without skim — raw file dump (487 lines, ~4,000 tokens)

```python
$ cat src/auth/service.py

import hashlib
import secrets
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional

from .database import UserRepository
from .models import User, Session
from .exceptions import AuthError, TokenExpiredError


@dataclass
class AuthResult:
    success: bool
    token: Optional[str] = None
    error: Optional[str] = None


class AuthService:
    def __init__(self, repo: UserRepository, secret: str):
        self._repo = repo
        self._secret = secret

    async def login(self, email: str, password: str) -> AuthResult:
        user = await self._repo.find_by_email(email)
        if not user:
            return AuthResult(success=False, error="User not found")
        if not self._verify_password(password, user.password_hash):
            return AuthResult(success=False, error="Invalid password")
        token = self._generate_token(user.id)
        await self._repo.save_session(Session(user_id=user.id, token=token))
        return AuthResult(success=True, token=token)

    # ... 450 more lines: logout, verify_token, refresh, reset_password,
    #     _hash_password, _verify_password, _generate_token, validate_email,
    #     rate_limit, session_cleanup, admin_revoke_all, ...
```

The AI agent consumes **all 487 lines** just to understand what this file does.

### With skim — structural summary (15 lines, ~120 tokens)

```python
$ skim read src/auth/service.py

# src/auth/service.py  487 lines  4 exports  12 symbols
# imports: hashlib, secrets, datetime, dataclasses, typing, .database, .models, .exceptions

class AuthResult
    success: bool
    token: Optional[str]
    error: Optional[str]
class AuthService
    def __init__(self, repo: UserRepository, secret: str)
    async def login(self, email: str, password: str) -> AuthResult
    async def logout(self, session_id: str) -> None
    def verify_token(self, token: str) -> dict
    def refresh(self, token: str) -> AuthResult
    async def reset_password(self, email: str) -> None
    def _hash_password(self, password: str) -> str
    def _verify_password(self, password: str, hash: str) -> bool
    def _generate_token(self, user_id: int) -> str
    def validate_email(self, email: str) -> bool

# [487 lines → 15 lines · 97% reduction]
# [skim read src/auth/service.py:<symbol> for full function]
```

**97% fewer tokens.** The agent sees the full architecture — every function, every type, every import — without reading a single function body.

### Need the implementation? Drill in.

```python
$ skim read src/auth/service.py:AuthService.login

    async def login(self, email: str, password: str) -> AuthResult:
        user = await self._repo.find_by_email(email)
        if not user:
            return AuthResult(success=False, error="User not found")
        if not self._verify_password(password, user.password_hash):
            return AuthResult(success=False, error="Invalid password")
        token = self._generate_token(user.id)
        await self._repo.save_session(Session(user_id=user.id, token=token))
        return AuthResult(success=True, token=token)
```

### Read the same file again? Zero cost.

```
$ skim read src/auth/service.py
[unchanged since 3m ago]             → 4 tokens (99.9% savings)
```

---

## Token Savings

| Operation | Standard | skim | Savings |
|-----------|----------|------|---------|
| Read 500-line TS file | ~4,000 tokens | ~120 tokens | **-97%** |
| Re-read unchanged file | ~4,000 tokens | ~4 tokens | **-99%** |
| `git status` (20 files) | ~800 tokens | ~100 tokens | **-87%** |
| `git diff` (3 files) | ~2,000 tokens | ~400 tokens | **-80%** |
| `pytest` (all pass) | ~1,500 tokens | ~20 tokens | **-99%** |
| Read specific function | ~4,000 tokens | ~80 tokens | **-98%** |

---

## Quick Install

```bash
pip install skimcode
skim init -g
```

That's it. Restart your AI tool. skim hooks into your agent's tool calls automatically.

### Other install methods

```bash
# uv (recommended)
uv tool install skimcode && skim init -g

# pipx
pipx install skimcode && skim init -g

# With all language support (Rust, Go, Java, Ruby)
pip install "skimcode[all]"
```

### One-line install

```bash
curl -fsSL https://raw.githubusercontent.com/skim-ai/skim/main/install.sh | sh
```

---

## How It Works

```
AI Agent (Claude/Cursor/etc)
    │  "cat auth.ts"
    ▼
PreToolUse Hook
    │  rewrites to: "skim read auth.ts"
    ▼
skim CLI
    ├── Session Manager ──→ Cache hit? Return "[unchanged]"
    │                        Cache miss ▼
    ├── AST Engine (tree-sitter) ──→ Structural summary
    │
    └── Analytics Tracker ──→ SQLite (~/.local/share/skim/history.db)
```

1. **Hook intercepts** — `cat`, `head`, `git status` etc. get rewritten to `skim` equivalents
2. **Session dedup** — If the file hasn't changed since last read, returns `[unchanged]`
3. **AST parsing** — tree-sitter extracts function/class signatures without bodies
4. **Savings tracked** — Every operation records tokens saved for `skim gain`

---

## Commands

### File Reading

```bash
skim read <file>              # Structural summary (signatures only)
skim read <file>:<symbol>     # Read specific function/class
skim read <file>:Class.method # Read specific method
skim read <file> --full       # Full file content
```

### Git Operations

```bash
skim git status    # Compact: "branch: main, modified (3): file1, file2, file3"
skim git diff      # Compressed: keeps hunks, strips noise
skim git log       # One-line format, last 20 commits
```

### Test Runners

```bash
skim test pytest           # Failures only + summary
skim test cargo test       # Failures only + summary
skim test npm test         # Failures only + summary
```

### Analytics

```bash
skim gain              # Token savings summary
skim gain --daily      # Day-by-day breakdown
skim gain --history    # Recent command history
skim gain --json       # JSON output
```

### Session Management

```bash
skim session info      # Current session stats
skim session clear     # Clear session cache
```

### Hook Management

```bash
skim init -g                    # Install hooks (default: Claude Code)
skim init -g --agent cursor     # Install for Cursor
skim init -g --show             # Show hook status
skim init -g --uninstall        # Remove hooks
```

---

## Supported Languages

| Language | Extension | tree-sitter Module | Status |
|----------|-----------|-------------------|--------|
| Python | `.py` | `tree-sitter-python` | ✓ Built-in |
| TypeScript | `.ts`, `.tsx` | `tree-sitter-typescript` | ✓ Built-in |
| JavaScript | `.js`, `.jsx` | `tree-sitter-javascript` | ✓ Built-in |
| Rust | `.rs` | `tree-sitter-rust` | ✓ Optional (`[all]`) |
| Go | `.go` | `tree-sitter-go` | ✓ Optional (`[all]`) |
| Java | `.java` | `tree-sitter-java` | ✓ Optional (`[all]`) |
| Ruby | `.rb` | `tree-sitter-ruby` | ✓ Optional (`[all]`) |
| C/C++ | `.c`, `.cpp`, `.h` | `tree-sitter-c/cpp` | ✓ Optional |
| Swift | `.swift` | `tree-sitter-swift` | ✓ Optional |
| Kotlin | `.kt` | `tree-sitter-kotlin` | ✓ Optional |
| Other | `*` | — | Head+tail fallback |

---

## Supported AI Agents

| Agent | Hook Type | Install Command |
|-------|-----------|-----------------|
| Claude Code | `PreToolUse` (settings.json) | `skim init -g --agent claude` |
| Cursor | `preToolUse` (hooks.json) | `skim init -g --agent cursor` |
| Copilot | Coming soon | — |
| Codex | Coming soon | — |
| Gemini CLI | Coming soon | — |
| Windsurf | Coming soon | — |
| Cline | Coming soon | — |

---

## Ecosystem: skim + rtk + graphify

skim is part of a complementary ecosystem of AI coding optimization tools. Each operates at a different layer — **use them together** for maximum savings.

```
                        AI Coding Agent
                    (Claude / Cursor / Codex)
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
     ┌─────────────┐  ┌─────────────┐  ┌──────────────┐
     │  graphify   │  │    skim     │  │     rtk      │
     │  ─────────  │  │  ─────────  │  │  ─────────   │
     │  Understand │  │    Read     │  │   Execute    │
     │  ─────────  │  │  ─────────  │  │  ─────────   │
     │  Knowledge  │  │  AST-aware  │  │  Command     │
     │  graph of   │  │  structural │  │  output      │
     │  codebase   │  │  summaries  │  │  filtering   │
     │  structure  │  │  + session  │  │              │
     │             │  │  dedup      │  │              │
     └──────┬──────┘  └──────┬──────┘  └──────┬───────┘
            │                │                │
     "What calls     "Show me the      "git status in
      what? How       signatures,       3 lines, not
      does auth       not 500 lines     50"
      connect to      of code"
      the DB?"
```

### How they compare

|  | [**graphify**](https://github.com/safishamsi/graphify) | **skim** | [**rtk**](https://github.com/rtk-ai/rtk) |
|--|---------|------|-----|
| **Layer** | Understanding | Reading | Executing |
| **What it does** | Builds a knowledge graph of codebase relationships (calls, imports, inheritance) | Returns function/class signatures instead of raw file content, deduplicates across session | Filters and compresses stdout of shell commands |
| **Language** | Python + tree-sitter | Python + tree-sitter | Rust |
| **Stateful?** | Yes (graph DB) | Yes (session cache) | No (stateless) |
| **Best at** | "How does module X connect to Y?" | "Show me what's in this file" (80-97% fewer tokens) | "Run git status" (60-90% fewer tokens) |
| **File read savings** | N/A (different purpose) | **80-97%** | 10-30% |
| **Command savings** | N/A | 50-80% | **60-90%** |
| **Hook mechanism** | MCP server | PreToolUse hook | PreToolUse hook |

### Using them together

```bash
# graphify — understand architecture (once, at project start)
graphify analyze .                     # builds knowledge graph
graphify query "what calls login()"   # semantic queries

# skim — efficient daily reading (every file read, every session)
skim read src/auth.py                  # structural summary
skim read src/auth.py:login            # just one function
skim git status                        # compact status

# rtk — compress everything else (every command)
rtk cargo test                         # failures only
rtk brew install node                  # skip noise
```

The ideal setup: **graphify** to map your codebase once, **skim** to read files efficiently, **rtk** to compress command output. Together they can reduce total agent token consumption by **70-90%**.

---

## Configuration

`~/.config/skim/config.toml`:

```toml
[hooks]
exclude_commands = ["curl", "wget"]

[read]
small_file_threshold = 150    # Lines; below this, return full content
structural_summary = true

[session]
enabled = true
expiry_minutes = 30

[tracking]
enabled = true
history_days = 90

[display]
show_savings_hint = true
```

---

## License

MIT

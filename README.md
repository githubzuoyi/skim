# skim

**Stop dumping files into the model. Start routing context intentionally.**

[![PyPI version](https://img.shields.io/pypi/v/skimcode.svg)](https://pypi.org/project/skimcode/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

skim is a token-optimization layer for AI coding agents. It rewrites expensive file reads into structural summaries, compresses noisy command output, and records how much prompt budget was actually saved.

The current first-class hook targets are **GitHub Copilot**, **Claude Code**, and **Cursor**. **Codex** is still experimental; **Gemini CLI**, **Windsurf**, and **Cline** use shell alias integrations.

---

## What skim Actually Does

skim is not just an AST reader. It has four separate layers:

1. **Read routing** — large source files become structural summaries instead of raw dumps.
2. **Command compression** — `git`, `grep`, and test output get filtered into compact task-oriented views.
3. **Hook integration** — agent tool calls can be transparently rewritten before they hit the model.
4. **Telemetry** — `skim gain` tracks input, output, saved tokens, and Copilot session share.

---

## Before vs After

### Without skim

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
        ...
```

The model pays for the whole file just to discover the names of a few classes and methods.

### With skim

```python
$ skim read src/auth/service.py

// src/auth/service.py  487 lines  12 symbols
// imports: hashlib, secrets, datetime, dataclasses, typing, .database, .models, .exceptions

class AuthResult  [L12-L16]
    success: bool
    token: Optional[str]
    error: Optional[str]
class AuthService  [L19-L143]
    def __init__(self, repo: UserRepository, secret: str)  [L20-L22]
    async def login(self, email: str, password: str) -> AuthResult  [L24-L32]
    async def logout(self, session_id: str) -> None  [L34-L41]
    def verify_token(self, token: str) -> dict  [L43-L57]
```

skim keeps the architectural signal, line spans, and drill-down path, while dropping bodies that the model does not need yet.

### Drill into a single symbol

```python
$ skim read src/auth/service.py:AuthService.login

    async def login(self, email: str, password: str) -> AuthResult:
        user = await self._repo.find_by_email(email)
        if not user:
            return AuthResult(success=False, error="User not found")
        ...
```

---

## Installation

### One-line install

```bash
curl -fsSL https://raw.githubusercontent.com/ericzuo-ai/skim/main/install.sh | bash
```

Then, for Copilot, run:

```bash
skim init --agent copilot
```

The installer sets up a managed user install automatically and tries to expose `skim` on your existing `PATH` without asking you to edit shell config by hand. If your current terminal still does not see `skim`, open a new terminal and run the init step there.

### Option 1: user-level install

```bash
git clone https://github.com/ericzuo-ai/skim.git
cd skim
python3 -m pip install --user .
skim --version
```

If `skim` is not on your `PATH`, use the Python entry point instead:

```bash
python3 -m skim --version
```

### Option 2: project-local venv

This is the safest setup for teams that do not want a global install.

```bash
git clone https://github.com/ericzuo-ai/skim.git
cd skim
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
python -m skim --version
```

### Option 3: repo-local dedicated skim checkout

This layout is useful when you want skim to live alongside the target repo:

```bash
cd /path/to/your/code-repo
git clone https://github.com/ericzuo-ai/skim.git skim
cd skim
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
python -m skim --version
```

The generated skim launchers now auto-detect all of these layouts:

- the active `VIRTUAL_ENV`
- the target repo's `.venv` / `venv` / `env`
- a repo-local dedicated skim checkout at `./skim/.venv`

Copilot uses a project-scoped launcher under `.github/hooks`. Claude Code and Cursor use a global launcher under `~/.config/skim/launchers`, but the environment probing is the same.

---

## Copilot Quick Start

### Global or user install

```bash
cd /path/to/your/code-repo
skim init --agent copilot
skim init --show --agent copilot
```

### Venv install

```bash
cd /path/to/your/code-repo
/path/to/skim/.venv/bin/python -m skim init --agent copilot
/path/to/skim/.venv/bin/python -m skim init --show --agent copilot
```

Then:

1. Start a new Copilot chat.
2. Let Copilot use `read_file` normally.
3. Run `skim gain` whenever you want to see savings.

If `skim` is not on your `PATH`, prefer `python -m skim ...` from the environment that installed it.

### Platform note

Copilot hook installation currently targets **macOS, Linux, and WSL**. The generated launcher uses `/bin/sh`, so on native Windows PowerShell/CMD you can install and run skim manually, but Copilot hook support is not yet first-class there.

---

## Agent Support

| Agent | Status | Integration type | Install command |
|-------|--------|------------------|-----------------|
| GitHub Copilot | validated | project hook in `.github/hooks` | `skim init --agent copilot` |
| Claude Code | validated | global hook in `~/.claude/settings.json` | `skim init -g --agent claude` |
| Cursor | validated | global hook in `~/.cursor/hooks.json` | `skim init -g --agent cursor` |
| Codex | experimental | global hook in `~/.codex/settings.json` | `skim init -g --agent codex` |
| Gemini CLI | available via shell alias | shell alias install | `skim init -g --agent gemini` |
| Windsurf | available via shell alias | shell alias install | `skim init -g --agent windsurf` |
| Cline | available via shell alias | shell alias install | `skim init -g --agent cline` |

Use `skim init --show --agent <agent>` to inspect the installed hook state.

For Claude Code and Cursor, `skim init -g` installs a small launcher that can still find skim when the editor process does not inherit your shell `PATH`, as long as skim is available through `VIRTUAL_ENV`, the repo's `.venv` / `venv` / `env`, or a repo-local `./skim/.venv` layout.

For this release, the recommended rollout target is Copilot first, then Claude Code and Cursor. Codex should stay out of the release promise until it has matching runtime validation.

---

## Commands

### File reading

```bash
skim read <file>              # structural summary
skim read <file>:<symbol>     # specific function/class
skim read <file>:Class.method # specific method
skim read <file> --full       # full file content
```

### Command compression

```bash
skim git status
skim git diff
skim git log

skim grep -R "TODO" src

skim test pytest
skim test cargo test
skim test npm test
```

skim has specialized compressors for:

- git status / diff / log
- pytest / cargo test / npm test / go test
- generic file-grouped command output such as grep or rg-like results

If the filtered output is not actually smaller than the original, skim falls back to the raw output instead of pretending a compression win.

### Analytics and session inspection

```bash
skim gain
skim gain --daily
skim gain --history
skim gain --json
skim gain --all-projects
skim gain --session-log /path/to/main.jsonl

skim session info
skim session clear
```

`skim gain` currently shows:

- per-mode input / output / saved tokens
- total compression on tracked input
- estimated input cost saved

### Dashboard

```bash
skim server --host 0.0.0.0 --port 7745
```

This serves a local stats dashboard backed by skim's SQLite history.

---

## How It Works

```
AI agent
    │
    ├── read_file / shell command
    ▼
Hook layer
    │  rewrites expensive reads or command calls
    ▼
skim CLI
    ├── AST engine         -> structural summary with line spans
    ├── command filters    -> git / grep / test output compression
    ├── hook cache         -> reuse file summaries by stat/version
    ├── tracker            -> record input/output/saved tokens
    └── dashboard server   -> query and render local analytics
```

In practice, skim does three distinct kinds of work:

1. **Summarize code** before the model sees it.
2. **Compress noisy execution output** into task-relevant views.
3. **Measure what actually happened** so savings claims are inspectable later.

---

## Supported Languages

| Language | Extension | tree-sitter Module | Status |
|----------|-----------|-------------------|--------|
| Python | `.py` | `tree-sitter-python` | built-in |
| TypeScript | `.ts`, `.tsx` | `tree-sitter-typescript` | built-in |
| JavaScript | `.js`, `.jsx` | `tree-sitter-javascript` | built-in |
| Rust | `.rs` | `tree-sitter-rust` | optional via `[all]` |
| Go | `.go` | `tree-sitter-go` | optional via `[all]` |
| Java | `.java` | `tree-sitter-java` | optional via `[all]` |
| Ruby | `.rb` | `tree-sitter-ruby` | optional via `[all]` |
| Other | `*` | — | fallback summary |

---

## Configuration

skim reads `~/.config/skim/config.toml`.

```toml
[hooks]
exclude_commands = ["curl", "wget"]

[read]
small_file_threshold = 150
structural_summary = true

[tracking]
enabled = true
history_days = 90

[display]
show_savings_hint = true

[server]
host = "0.0.0.0"
port = 7745
```

---

## License

MIT

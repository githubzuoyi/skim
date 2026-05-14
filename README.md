# skim

**Stop reading every line. Start skimming. 80-97% fewer tokens on file reads.**

[![PyPI version](https://img.shields.io/pypi/v/skimcode.svg)](https://pypi.org/project/skimcode/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

skim is an AST-aware token optimizer for AI coding agents. It intercepts file reads and command output, returning **structural summaries** instead of raw content — saving 80-97% of tokens on every operation.

Works with **Claude Code**, **Cursor**, **Copilot**, **Codex**, **Gemini CLI**, **Windsurf**, and **Cline**.

---

## Before vs After

```
# WITHOUT skim — agent reads 487 lines of raw code
$ cat src/auth/login.ts
import { createHash } from 'crypto';
import { readFileSync, writeFileSync } from 'fs';
... (487 lines of code) ...
→ ~4,000 tokens consumed

# WITH skim — agent gets structural summary
$ skim read src/auth/login.ts
// src/auth/login.ts  487 lines  12 exports  23 symbols
// imports: crypto, fs, path

export async function login(email: string, password: string): Promise<Session>
export async function logout(sessionId: string): Promise<void>
export function validateToken(token: string): boolean
export class AuthService
  constructor(private repo: UserRepository)
  async login(email: string, password: string): Promise<AuthResult>
  verifyToken(token: string): { valid: boolean; userId?: string }
export type Session = { id: string; userId: string; expiresAt: Date }

// [487 lines → 15 lines (97% reduction)]
// [skim read src/auth/login.ts:<symbol> for full function]
→ ~120 tokens consumed
```

**Then drill into what you need:**

```
$ skim read src/auth/login.ts:AuthService.login
  async login(email: string, password: string): Promise<AuthResult> {
    const user = await this.repo.findByEmail(email);
    if (!user) {
      return { success: false, error: 'User not found' };
    }
    const hash = this.hashPassword(password);
    const token = this.generateToken(user.id);
    return { success: true, token };
  }
```

**Session dedup — re-reading unchanged files:**

```
$ skim read src/auth/login.ts
[unchanged since 3m ago]
→ 4 tokens (99.9% savings)
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

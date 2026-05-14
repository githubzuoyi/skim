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

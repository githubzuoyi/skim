---
description: Use skim for token-efficient code reading. Always prefer skim read over read_file for exploring code files.
applyTo: "**/*.{py,ts,tsx,js,jsx,rs,go,java,rb,c,cpp,h,hpp,swift,kt}"
---

# skim — Token-Efficient Code Reading

This project has `skim` installed. You MUST use `skim read` via terminal
instead of `read_file` when exploring code. This saves 80-97% tokens.

## Rule: Use `skim read` for code exploration

When you want to understand what a code file contains, **always run
`skim read` in the terminal** instead of using `read_file`:

```bash
# See all functions, classes, types in a file (use this FIRST)
skim read src/auth/service.py

# Read a specific function body
skim read src/auth/service.py:login

# Read a specific method
skim read src/auth/service.py:AuthService.verify
```

This returns a structural summary (function/class signatures only),
saving 80-97% of tokens compared to reading the full file.

## When to use `read_file` (built-in)

Only use `read_file` when:
- You are about to **edit** a file and need exact line numbers
- You need **exact indentation or whitespace** for a code change
- The file is a **non-code file** (JSON, YAML, Markdown, config, etc.)
- You already used `skim read` and now need the full implementation

If you need the complete content of a code file:
```bash
skim read src/auth/service.py --full
```

## Git & test commands

```bash
skim git status    # compact status output
skim git diff      # compressed diff
skim git log       # one-line format
skim test pytest   # failures-only summary
```

## Workflow

1. **Explore**: `skim read file.py` → see structure
2. **Drill in**: `skim read file.py:function_name` → see implementation
3. **Edit**: use `read_file` for exact lines, then make changes
4. **Verify**: `skim git diff` to check changes

## Key point

Re-reading unchanged files returns `[unchanged]` (near-zero tokens).
Run `skim gain` in terminal to see cumulative token savings.

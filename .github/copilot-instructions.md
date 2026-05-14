# skim — Token-Efficient Code Reading

This project uses **skim** to reduce token consumption when reading code files.
skim is hooked into your tool calls automatically via PreToolUse.

## How it works

When you run `cat file.py` or similar commands, skim intercepts and returns a
**structural summary** (function/class signatures) instead of the full file.
This saves 80-97% of tokens on every file read.

## Reading code efficiently

```bash
# Structural summary — see all functions, classes, types (default)
cat src/auth.py                  # auto-intercepted → structural summary

# Read a specific function body when you need implementation details
skim read src/auth.py:login      # returns just the login() function body
skim read src/auth.py:AuthService.verify  # a specific method

# Full file content — use when you need the complete file
skim read src/auth.py --full     # returns the entire file, unmodified
```

## When you need full file content

If a structural summary is not enough (e.g., you need to make edits,
check exact syntax, or see full implementation), use one of:

1. **`skim read <file> --full`** — always returns complete content
2. **VS Code's built-in file reading** — not intercepted by skim

## Git & test commands

```bash
skim git status    # compact status
skim git diff      # compressed diff
skim test pytest   # failures-only summary
```

## Tips

- Start with the structural summary to understand a file's architecture
- Drill into specific functions with `skim read file.py:function_name`
- Use `--full` only when you truly need every line
- Re-reading unchanged files returns `[unchanged]` (near-zero tokens)

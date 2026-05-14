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

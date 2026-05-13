"""Command implementations for skim CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def cmd_read(args) -> None:
    """Smart file read with AST structural summary + session dedup."""
    from skim.ast_engine import structural_read, read_symbol
    from skim.session import SessionManager
    from skim.tracking import get_tracker

    raw_path = args.path
    symbol_name = None

    if ":" in raw_path and not Path(raw_path).exists():
        raw_path, symbol_name = raw_path.rsplit(":", 1)

    path = Path(raw_path)
    if not path.exists():
        print(f"skim: file not found: {raw_path}", file=sys.stderr)
        sys.exit(1)
    if path.is_dir():
        print(f"skim: is a directory: {raw_path}", file=sys.stderr)
        sys.exit(1)

    if symbol_name:
        result = read_symbol(path, symbol_name)
    elif args.full or args.level == "full":
        content = path.read_text(encoding="utf-8", errors="replace")
        from skim.ast_engine import SkimResult

        result = SkimResult(content=content, mode="full", original_lines=content.count("\n") + 1)
    else:
        result = structural_read(path)

    session = SessionManager()
    cache_key = f"read:{path.resolve()}"

    if symbol_name:
        cache_key += f":{symbol_name}"

    output, tokens_saved = session.check(cache_key, result.content)

    mode = "dedup" if tokens_saved > 0 else result.mode
    raw_content = path.read_text(encoding="utf-8", errors="replace")
    tracker = get_tracker()
    if tracker:
        tracker.record(
            command=f"read {raw_path}",
            raw_output=raw_content,
            skim_output=output,
            mode=mode,
        )

    print(output)


def cmd_gain(args) -> None:
    """Show token savings analytics."""
    from skim.tracking import get_tracker

    tracker = get_tracker()
    if not tracker:
        print("skim: no tracking data found")
        return

    if args.reset:
        tracker.reset()
        print("skim: analytics data reset")
        return

    summary = tracker.gain_summary(days=args.days)

    if args.json:
        import json

        print(json.dumps(summary, indent=2))
        return

    if args.history:
        tracker.print_history()
        return

    if args.daily:
        tracker.print_daily(days=args.days)
        return

    tracker.print_summary(summary)


def cmd_session(args) -> None:
    """Show or manage current session."""
    from skim.session import SessionManager

    session = SessionManager()

    if args.action == "clear":
        session.clear()
        print("skim: session cache cleared")
    else:
        info = session.info()
        print(f"skim session")
        print(f"  entries:      {info['entries']}")
        print(f"  total saved:  {info['total_saved_tokens']:,} tokens")
        print(f"  session file: {info['state_path']}")
        if info["started_at"]:
            print(f"  started:      {info['started_at']}")


def cmd_git(args) -> None:
    """Compressed git commands with session dedup."""
    from skim.filters.git import run_git
    from skim.session import SessionManager
    from skim.tracking import get_tracker

    if not args.git_args:
        subprocess.run(["git"], check=False)
        return

    raw_output, filtered_output = run_git(args.git_args)

    session = SessionManager()
    cache_key = f"git:{' '.join(args.git_args)}"
    output, tokens_saved = session.check(cache_key, filtered_output)

    mode = "dedup" if tokens_saved > 0 else "compress"
    tracker = get_tracker()
    if tracker:
        tracker.record(
            command=f"git {' '.join(args.git_args)}",
            raw_output=raw_output,
            skim_output=output,
            mode=mode,
        )

    print(output)


def cmd_grep(args) -> None:
    """Compressed grep output."""
    from skim.filters.generic import run_command_filtered
    from skim.tracking import get_tracker

    if not args.grep_args:
        return

    raw_output, filtered = run_command_filtered(["grep"] + list(args.grep_args))

    tracker = get_tracker()
    if tracker:
        tracker.record(
            command=f"grep {' '.join(args.grep_args)}",
            raw_output=raw_output,
            skim_output=filtered,
            mode="compress",
        )

    print(filtered)


def cmd_test(args) -> None:
    """Compressed test runner output."""
    from skim.filters.test_runners import run_test
    from skim.session import SessionManager
    from skim.tracking import get_tracker

    if not args.test_args:
        return

    raw_output, filtered = run_test(args.test_args)

    session = SessionManager()
    cache_key = f"test:{' '.join(args.test_args)}"
    output, tokens_saved = session.check(cache_key, filtered)

    mode = "dedup" if tokens_saved > 0 else "compress"
    tracker = get_tracker()
    if tracker:
        tracker.record(
            command=f"test {' '.join(args.test_args)}",
            raw_output=raw_output,
            skim_output=output,
            mode=mode,
        )

    print(output)

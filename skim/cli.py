"""CLI dispatcher for skim commands."""

from __future__ import annotations

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skim",
        description="AST-aware token optimizer for AI coding agents",
    )
    parser.add_argument(
        "-V", "--version", action="store_true", help="Show version and exit"
    )
    sub = parser.add_subparsers(dest="command")

    # skim read <path> [--full] [-l aggressive]
    read_p = sub.add_parser("read", help="Smart file read with AST structural summary")
    read_p.add_argument("path", help="File path, optionally with :symbol suffix")
    read_p.add_argument("--full", action="store_true", help="Return full file content")
    read_p.add_argument(
        "-l",
        "--level",
        choices=["structural", "aggressive", "full"],
        default="structural",
        help="Compression level (default: structural)",
    )

    # skim init [-g] [--agent <name>] [--uninstall] [--show]
    init_p = sub.add_parser("init", help="Install skim hooks for your AI tool")
    init_p.add_argument("-g", "--global", dest="global_install", action="store_true",
                        help="Install globally (recommended)")
    init_p.add_argument("--agent", default="claude",
                        choices=["claude", "cursor", "copilot", "codex", "gemini",
                                 "windsurf", "cline"],
                        help="Target AI agent (default: claude)")
    init_p.add_argument("--uninstall", action="store_true", help="Remove skim hooks")
    init_p.add_argument("--show", action="store_true", help="Show current hook status")

    # skim hook <agent>  (called by PreToolUse hooks, not by users)
    hook_p = sub.add_parser("hook", help=argparse.SUPPRESS)
    hook_p.add_argument("agent", choices=["claude", "cursor", "copilot"])

    # skim gain [--history] [--daily] [--json]
    gain_p = sub.add_parser("gain", help="Show token savings analytics")
    gain_p.add_argument("--history", action="store_true", help="Show recent command history")
    gain_p.add_argument("--daily", action="store_true", help="Day-by-day breakdown")
    gain_p.add_argument("--json", action="store_true", help="JSON output")
    gain_p.add_argument(
        "--all-projects",
        action="store_true",
        help="Aggregate across all tracked projects instead of the current working directory",
    )
    gain_p.add_argument("--days", type=int, default=30, help="Number of days (default: 30)")
    gain_p.add_argument("--reset", action="store_true", help="Reset analytics data")
    gain_p.add_argument(
        "--session-log",
        help="Copilot session main.jsonl or session directory for latest-session comparison",
    )

    # skim session [clear]
    sess_p = sub.add_parser("session", help="Show or manage current session")
    sess_p.add_argument("action", nargs="?", choices=["clear", "info"], default="info")

    # skim git <subcommand> [args...]
    git_p = sub.add_parser("git", help="Compressed git commands")
    git_p.add_argument("git_args", nargs=argparse.REMAINDER)

    # skim grep <args...>
    grep_p = sub.add_parser("grep", help="Compressed grep output")
    grep_p.add_argument("grep_args", nargs=argparse.REMAINDER)

    # skim test <command...>
    test_p = sub.add_parser("test", help="Compressed test runner output")
    test_p.add_argument("test_args", nargs=argparse.REMAINDER)

    # skim server [--port PORT] [--host HOST]
    server_p = sub.add_parser("server", help="Start the skim stats dashboard server")
    server_p.add_argument("--port", type=int, default=7745, help="Port (default: 7745)")
    server_p.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.version:
        from skim import __version__
        from skim.style import BOLD, CYAN, DIM, RESET

        print(f"{BOLD}{CYAN}skim{RESET} {DIM}v{__version__}{RESET}  {DIM}AST-aware token optimizer{RESET}")
        return

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "read":
        from skim.commands import cmd_read

        cmd_read(args)

    elif args.command == "init":
        from skim.hooks.init import cmd_init

        cmd_init(args)

    elif args.command == "hook":
        from skim.hooks.hook_cmd import cmd_hook

        cmd_hook(args)

    elif args.command == "gain":
        from skim.commands import cmd_gain

        cmd_gain(args)

    elif args.command == "session":
        from skim.commands import cmd_session

        cmd_session(args)

    elif args.command == "git":
        from skim.commands import cmd_git

        cmd_git(args)

    elif args.command == "grep":
        from skim.commands import cmd_grep

        cmd_grep(args)

    elif args.command == "test":
        from skim.commands import cmd_test

        cmd_test(args)

    elif args.command == "server":
        from skim.server import run_server

        run_server(host=args.host, port=args.port)

    else:
        parser.print_help()
        sys.exit(1)

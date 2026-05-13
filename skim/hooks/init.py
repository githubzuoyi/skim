"""Hook installation for AI coding agents.

Implements ``skim init -g`` which patches agent configuration files
to intercept commands via PreToolUse hooks.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from skim.hooks.constants import (
    CLAUDE_HOOK,
    CLAUDE_MD_PATCH,
    CURSOR_HOOK_CONFIG,
    SKILL_CONTENT,
)


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

def cmd_init(args) -> None:
    """Handle ``skim init`` command."""
    agent = args.agent

    if args.show:
        _show_status(agent)
        return

    if args.uninstall:
        _uninstall(agent)
        return

    if agent == "claude":
        init_claude_global()
    elif agent == "cursor":
        init_cursor()
    else:
        print(f"skim: agent '{agent}' hook installation not yet supported", file=sys.stderr)
        print("Supported agents: claude, cursor", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Claude Code
# ---------------------------------------------------------------------------

def init_claude_global() -> None:
    """Install skim hook for Claude Code globally."""
    settings_path = Path.home() / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            settings = {}
    else:
        settings = {}

    hooks = settings.setdefault("hooks", {})
    pre_tool: list = hooks.setdefault("PreToolUse", [])

    # Remove any existing skim hooks
    pre_tool[:] = [
        h for h in pre_tool
        if "skim" not in str(h.get("hooks", [{}])[0].get("command", ""))
    ]
    pre_tool.append(CLAUDE_HOOK)

    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    print(f"  ✓ Installed Claude Code hook → {settings_path}")

    # Write SKIM.md
    _write_skill_file()

    # Patch CLAUDE.md to reference SKIM.md
    _patch_claude_md()

    print()
    print("  Done! Restart Claude Code to activate.")
    print("  Run `skim gain` anytime to see token savings.")


def _uninstall_claude() -> None:
    """Remove skim hook from Claude Code."""
    settings_path = Path.home() / ".claude" / "settings.json"
    if not settings_path.exists():
        print("  No Claude Code settings found.")
        return

    settings = json.loads(settings_path.read_text())
    hooks = settings.get("hooks", {})
    pre_tool = hooks.get("PreToolUse", [])

    original_len = len(pre_tool)
    pre_tool[:] = [
        h for h in pre_tool
        if "skim" not in str(h.get("hooks", [{}])[0].get("command", ""))
    ]

    if len(pre_tool) < original_len:
        settings_path.write_text(json.dumps(settings, indent=2) + "\n")
        print(f"  ✓ Removed Claude Code hook from {settings_path}")
    else:
        print("  No skim hook found in Claude Code settings.")


# ---------------------------------------------------------------------------
# Cursor
# ---------------------------------------------------------------------------

def init_cursor() -> None:
    """Install skim hook for Cursor."""
    hooks_path = Path.home() / ".cursor" / "hooks.json"
    hooks_path.parent.mkdir(parents=True, exist_ok=True)

    if hooks_path.exists():
        try:
            existing = json.loads(hooks_path.read_text())
        except json.JSONDecodeError:
            existing = {}
    else:
        existing = {}

    hooks = existing.setdefault("hooks", {})
    pre_tool: list = hooks.setdefault("preToolUse", [])

    # Remove existing skim hooks
    pre_tool[:] = [
        h for h in pre_tool
        if "skim" not in str(h.get("command", ""))
    ]
    pre_tool.append(CURSOR_HOOK_CONFIG["hooks"]["preToolUse"][0])

    hooks_path.write_text(json.dumps(existing, indent=2) + "\n")
    print(f"  ✓ Installed Cursor hook → {hooks_path}")

    _write_skill_file()

    print()
    print("  Done! Restart Cursor to activate.")
    print("  Run `skim gain` anytime to see token savings.")


def _uninstall_cursor() -> None:
    """Remove skim hook from Cursor."""
    hooks_path = Path.home() / ".cursor" / "hooks.json"
    if not hooks_path.exists():
        print("  No Cursor hooks.json found.")
        return

    existing = json.loads(hooks_path.read_text())
    hooks = existing.get("hooks", {})
    pre_tool = hooks.get("preToolUse", [])

    original_len = len(pre_tool)
    pre_tool[:] = [
        h for h in pre_tool
        if "skim" not in str(h.get("command", ""))
    ]

    if len(pre_tool) < original_len:
        hooks_path.write_text(json.dumps(existing, indent=2) + "\n")
        print(f"  ✓ Removed Cursor hook from {hooks_path}")
    else:
        print("  No skim hook found in Cursor hooks.json.")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _write_skill_file() -> None:
    """Write SKIM.md to the current project root."""
    skill_path = Path.cwd() / "SKIM.md"
    if not skill_path.exists():
        skill_path.write_text(SKILL_CONTENT)
        print(f"  ✓ Created {skill_path}")
    else:
        print(f"  ✓ SKIM.md already exists at {skill_path}")


def _patch_claude_md() -> None:
    """Add skim reference to CLAUDE.md if it exists."""
    claude_md = Path.cwd() / "CLAUDE.md"
    if claude_md.exists():
        content = claude_md.read_text()
        if "skim" not in content.lower():
            claude_md.write_text(content + CLAUDE_MD_PATCH)
            print(f"  ✓ Patched {claude_md} with skim instructions")
    # Don't create CLAUDE.md if it doesn't exist


def _show_status(agent: str) -> None:
    """Show current hook installation status."""
    print(f"skim hook status for {agent}:")
    print()

    if agent == "claude":
        settings_path = Path.home() / ".claude" / "settings.json"
        if settings_path.exists():
            settings = json.loads(settings_path.read_text())
            hooks = settings.get("hooks", {}).get("PreToolUse", [])
            skim_hooks = [h for h in hooks if "skim" in str(h)]
            if skim_hooks:
                print(f"  ✓ Installed in {settings_path}")
                print(f"    Hook: {json.dumps(skim_hooks[0], indent=6)}")
            else:
                print(f"  ✗ Not installed (checked {settings_path})")
        else:
            print(f"  ✗ No settings.json found at {settings_path}")

    elif agent == "cursor":
        hooks_path = Path.home() / ".cursor" / "hooks.json"
        if hooks_path.exists():
            existing = json.loads(hooks_path.read_text())
            hooks = existing.get("hooks", {}).get("preToolUse", [])
            skim_hooks = [h for h in hooks if "skim" in str(h)]
            if skim_hooks:
                print(f"  ✓ Installed in {hooks_path}")
                print(f"    Hook: {json.dumps(skim_hooks[0], indent=6)}")
            else:
                print(f"  ✗ Not installed (checked {hooks_path})")
        else:
            print(f"  ✗ No hooks.json found at {hooks_path}")

    # Check for skim binary
    skim_path = shutil.which("skim")
    if skim_path:
        print(f"  ✓ skim binary found at {skim_path}")
    else:
        print("  ⚠ skim not in PATH (hooks may not work)")


def _uninstall(agent: str) -> None:
    """Uninstall skim hooks for an agent."""
    if agent == "claude":
        _uninstall_claude()
    elif agent == "cursor":
        _uninstall_cursor()
    else:
        print(f"skim: uninstall not supported for '{agent}'")

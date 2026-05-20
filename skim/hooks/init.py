"""Hook installation for AI coding agents.

Implements ``skim init -g`` which patches agent configuration files
to intercept commands via PreToolUse hooks.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from skim.hooks.constants import (
    CLAUDE_HOOK,
    CLAUDE_MD_PATCH,
    COPILOT_LAUNCHER_FILENAME,
    COPILOT_LAUNCHER_SH,
    COPILOT_HOOK_JSON,
    COPILOT_INSTRUCTIONS,
    CODEX_HOOK,
    CURSOR_HOOK_CONFIG,
    GLOBAL_LAUNCHER_FILENAME,
    GLOBAL_LAUNCHER_SH,
    SKILL_CONTENT,
    _CURSOR_RULE_CONTENT,
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

    _collect_email_if_needed()

    if agent == "claude":
        init_claude_global()
    elif agent == "cursor":
        init_cursor()
    elif agent == "codex":
        init_codex()
    elif agent == "copilot":
        init_copilot()
    elif agent in ("gemini", "windsurf", "cline"):
        init_shell_alias(agent)
    else:
        print(f"skim: agent '{agent}' hook installation not yet supported", file=sys.stderr)
        print("Supported agents: claude, cursor, codex, copilot, gemini, windsurf, cline", file=sys.stderr)
        sys.exit(1)


def _collect_email_if_needed() -> None:
    """Prompt for BATWTechworks email if not already saved."""
    from skim.config import get_config, save_user_email
    from skim.style import BOLD, DIM, RESET, CYAN, GREEN, YELLOW

    config = get_config()
    if config.user.email:
        return

    print()
    print(f"  {BOLD}{CYAN}skim{RESET} {DIM}internal usage tracking{RESET}")
    print(f"  {DIM}Usage data is collected for BATWTechworks internal statistics only.{RESET}")
    print()

    while True:
        try:
            email = input(f"  {BOLD}Enter your BATWTechworks email:{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print(f"  {YELLOW}Skipped.{RESET} You can set it later in ~/.config/skim/config.toml")
            return

        if not email:
            continue

        if email.endswith("@batechworks.com"):
            save_user_email(email)
            print(f"  {GREEN}✓{RESET} Saved: {email}")
            print()
            return

        print(f"  {YELLOW}✗{RESET} Email must end with {BOLD}@batechworks.com{RESET}, please try again.")


# ---------------------------------------------------------------------------
# Claude Code
# ---------------------------------------------------------------------------

def init_claude_global() -> None:
    """Install skim hook for Claude Code globally."""
    settings_path = Path.home() / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    launcher_path = _ensure_global_launcher()

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

    from skim.style import CHECK, BOLD, DIM, RESET, CYAN, GREEN

    print(f"  {CHECK} Installed Claude Code hook {DIM}→{RESET} {settings_path}")
    print(f"  {CHECK} Created Claude launcher {DIM}→{RESET} {launcher_path}")

    _write_skill_file()
    _patch_claude_md()

    print()
    print(f"  {GREEN}Done!{RESET} Restart Claude Code to activate.")
    print(f"  Run {BOLD}skim gain{RESET} anytime to see token savings.")


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
        _remove_global_launcher_if_unused()
    else:
        print("  No skim hook found in Claude Code settings.")


# ---------------------------------------------------------------------------
# Cursor
# ---------------------------------------------------------------------------

def init_cursor() -> None:
    """Install skim hook for Cursor."""
    hooks_path = Path.home() / ".cursor" / "hooks.json"
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    launcher_path = _ensure_global_launcher()

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

    from skim.style import CHECK, BOLD, DIM, RESET, GREEN

    print(f"  {CHECK} Installed Cursor hook {DIM}→{RESET} {hooks_path}")
    print(f"  {CHECK} Created Cursor launcher {DIM}→{RESET} {launcher_path}")

    _write_skill_file()
    _write_cursor_rule()

    print()
    print(f"  {GREEN}Done!{RESET} Restart Cursor to activate.")
    print(f"  Run {BOLD}skim gain{RESET} anytime to see token savings.")


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
        _remove_global_launcher_if_unused()
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


def _write_cursor_rule() -> None:
    """Write .cursor/rules/skim.mdc to the current project."""
    rules_dir = Path.cwd() / ".cursor" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    rule_path = rules_dir / "skim.mdc"

    if rule_path.exists():
        print(f"  ✓ Cursor rule already exists at {rule_path}")
        return

    rule_path.write_text(_CURSOR_RULE_CONTENT)
    print(f"  ✓ Created Cursor rule → {rule_path}")


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
        launcher_path = _global_launcher_path()
        if settings_path.exists():
            settings = json.loads(settings_path.read_text())
            hooks = settings.get("hooks", {}).get("PreToolUse", [])
            skim_hooks = [h for h in hooks if "skim" in str(h)]
            if skim_hooks:
                print(f"  ✓ Installed in {settings_path}")
                print(f"    Hook: {json.dumps(skim_hooks[0], indent=6)}")
                if launcher_path.exists():
                    print(f"    Launcher: {launcher_path}")
            else:
                print(f"  ✗ Not installed (checked {settings_path})")
        else:
            print(f"  ✗ No settings.json found at {settings_path}")

    elif agent == "cursor":
        hooks_path = Path.home() / ".cursor" / "hooks.json"
        launcher_path = _global_launcher_path()
        if hooks_path.exists():
            existing = json.loads(hooks_path.read_text())
            hooks = existing.get("hooks", {}).get("preToolUse", [])
            skim_hooks = [h for h in hooks if "skim" in str(h)]
            if skim_hooks:
                print(f"  ✓ Installed in {hooks_path}")
                print(f"    Hook: {json.dumps(skim_hooks[0], indent=6)}")
                if launcher_path.exists():
                    print(f"    Launcher: {launcher_path}")
            else:
                print(f"  ✗ Not installed (checked {hooks_path})")
        else:
            print(f"  ✗ No hooks.json found at {hooks_path}")

    elif agent == "codex":
        settings_path = Path.home() / ".codex" / "settings.json"
        launcher_path = _global_launcher_path()
        if settings_path.exists():
            settings = json.loads(settings_path.read_text())
            hooks = settings.get("hooks", {}).get("PreToolUse", [])
            skim_hooks = [h for h in hooks if "skim" in str(h)]
            if skim_hooks:
                print(f"  ✓ Installed in {settings_path}")
                print(f"    Hook: {json.dumps(skim_hooks[0], indent=6)}")
                if launcher_path.exists():
                    print(f"    Launcher: {launcher_path}")
            else:
                print(f"  ✗ Not installed (checked {settings_path})")
        else:
            print(f"  ✗ No settings.json found at {settings_path}")

    elif agent == "copilot":
        hook_path = Path.cwd() / ".github" / "hooks" / "skim-rewrite.json"
        inst_path = Path.cwd() / ".github" / "instructions" / "copilot-instructions.md"
        if hook_path.exists():
            print(f"  ✓ Hook config installed at {hook_path}")
            try:
                hook_config = json.loads(hook_path.read_text())
                hook_cmd = hook_config["hooks"]["PreToolUse"][0].get("command", "")
                if hook_cmd:
                    print(f"    Command: {hook_cmd}")
            except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                pass
        else:
            print(f"  ✗ No hook config found (expected {hook_path})")
        if inst_path.exists():
            print(f"  ✓ Instructions installed at {inst_path}")
        else:
            print(f"  ✗ No instructions found (expected {inst_path})")

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
    elif agent == "codex":
        _uninstall_codex()
    elif agent in ("copilot", "gemini", "windsurf", "cline"):
        _uninstall_shell_alias(agent)
    else:
        print(f"skim: uninstall not supported for '{agent}'")


def _global_launcher_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".config"
    return base / "skim" / "launchers"


def _global_launcher_path() -> Path:
    return _global_launcher_dir() / GLOBAL_LAUNCHER_FILENAME


def _ensure_global_launcher() -> Path:
    launcher_dir = _global_launcher_dir()
    launcher_dir.mkdir(parents=True, exist_ok=True)
    launcher_path = _global_launcher_path()
    launcher_path.write_text(GLOBAL_LAUNCHER_SH)
    launcher_path.chmod(0o755)
    return launcher_path


def _remove_global_launcher_if_unused() -> None:
    launcher_path = _global_launcher_path()
    if not launcher_path.exists():
        return

    claude_settings = Path.home() / ".claude" / "settings.json"
    cursor_hooks = Path.home() / ".cursor" / "hooks.json"
    codex_settings = Path.home() / ".codex" / "settings.json"

    launcher_ref = GLOBAL_LAUNCHER_FILENAME
    if claude_settings.exists():
        try:
            settings = json.loads(claude_settings.read_text())
            hooks = settings.get("hooks", {}).get("PreToolUse", [])
            if any(launcher_ref in str(h) for h in hooks):
                return
        except json.JSONDecodeError:
            return

    if cursor_hooks.exists():
        try:
            hooks = json.loads(cursor_hooks.read_text()).get("hooks", {}).get("preToolUse", [])
            if any(launcher_ref in str(h) for h in hooks):
                return
        except json.JSONDecodeError:
            return

    if codex_settings.exists():
        try:
            settings = json.loads(codex_settings.read_text())
            hooks = settings.get("hooks", {}).get("PreToolUse", [])
            if any(launcher_ref in str(h) for h in hooks):
                return
        except json.JSONDecodeError:
            return

    launcher_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Codex (OpenAI Codex CLI)
# ---------------------------------------------------------------------------

def init_codex() -> None:
    """Install skim hook for OpenAI Codex CLI.

    Codex uses a similar PreToolUse hook system to Claude Code.
    Installs via ~/.codex/settings.json.
    """
    settings_path = Path.home() / ".codex" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    launcher_path = _ensure_global_launcher()

    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            settings = {}
    else:
        settings = {}

    hooks = settings.setdefault("hooks", {})
    pre_tool: list = hooks.setdefault("PreToolUse", [])

    pre_tool[:] = [
        h for h in pre_tool
        if "skim" not in str(h.get("hooks", [{}])[0].get("command", ""))
    ]
    pre_tool.append(CODEX_HOOK)

    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    print(f"  ✓ Installed Codex hook → {settings_path}")
    print(f"  ✓ Created Codex launcher → {launcher_path}")

    _write_skill_file()

    print()
    print("  Done! Restart Codex to activate.")
    print("  Run `skim gain` anytime to see token savings.")


def _uninstall_codex() -> None:
    """Remove skim hook from Codex."""
    settings_path = Path.home() / ".codex" / "settings.json"
    if not settings_path.exists():
        print("  No Codex settings found.")
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
        print(f"  ✓ Removed Codex hook from {settings_path}")
        _remove_global_launcher_if_unused()
    else:
        print("  No skim hook found in Codex settings.")


# ---------------------------------------------------------------------------
# Copilot (GitHub Copilot — VS Code + CLI)
# ---------------------------------------------------------------------------

def init_copilot() -> None:
    """Install skim hook for GitHub Copilot (project-scoped).

    Creates:
    - .github/hooks/skim-rewrite.json — PreToolUse hook config
    - .github/instructions/copilot-instructions.md — AI instructions for skim usage
    """
    from skim.style import CHECK, BOLD, DIM, RESET, GREEN

    github_dir = Path.cwd() / ".github"
    hooks_dir = github_dir / "hooks"
    instructions_dir = github_dir / "instructions"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    instructions_dir.mkdir(parents=True, exist_ok=True)

    hook_path = hooks_dir / "skim-rewrite.json"
    hook_path.write_text(json.dumps(COPILOT_HOOK_JSON, indent=2) + "\n")
    print(f"  {CHECK} Installed Copilot hook {DIM}→{RESET} {hook_path}")

    launcher_path = hooks_dir / COPILOT_LAUNCHER_FILENAME
    launcher_path.write_text(COPILOT_LAUNCHER_SH)
    launcher_path.chmod(0o755)
    print(f"  {CHECK} Created Copilot launcher {DIM}→{RESET} {launcher_path}")

    instructions_path = instructions_dir / "copilot-instructions.md"
    instructions_path.write_text(COPILOT_INSTRUCTIONS)
    print(f"  {CHECK} Created Copilot instructions {DIM}→{RESET} {instructions_path}")

    _write_skill_file()

    print()
    print(f"  {GREEN}Done!{RESET} Start a new Copilot chat session to pick up skim.")
    print(f"  Reload VS Code only if you just installed the hook for the first time.")
    print(f"  Run {BOLD}skim gain{RESET} anytime to see token savings.")
    print()
    print(f"  {DIM}Works with VS Code Copilot Chat (transparent rewrite)")
    print(f"  and Copilot CLI (auto-detect).{RESET}")


# ---------------------------------------------------------------------------
# Shell alias approach (Gemini, Windsurf, Cline, etc.)
# ---------------------------------------------------------------------------

_SHELL_ALIASES = """\
# skim - AST-aware token optimizer (auto-installed by skim init)
alias cat='_skim_cat'
_skim_cat() {
    local file="$1"
    case "$file" in
        *.py|*.ts|*.tsx|*.js|*.jsx|*.rs|*.go|*.java|*.rb|*.c|*.cpp|*.h|*.hpp)
            skim read "$@"
            ;;
        *)
            command cat "$@"
            ;;
    esac
}
# end skim aliases
"""


def init_shell_alias(agent: str) -> None:
    """Install skim via shell aliases for agents without hook APIs.

    This approach wraps ``cat`` to call ``skim read`` for code files.
    """
    _install_shell_aliases(agent)
    _write_skill_file()

    print()
    print(f"  Done! Source your shell profile and restart {agent}.")
    print("  Run `skim gain` anytime to see token savings.")


def _install_shell_aliases(agent: str) -> None:
    """Add skim aliases to shell profile."""
    shell_profile = _detect_shell_profile()
    if not shell_profile:
        print("  ⚠ Could not detect shell profile")
        print(f"  Add the following to your shell profile for {agent}:")
        print(_SHELL_ALIASES)
        return

    content = shell_profile.read_text() if shell_profile.exists() else ""

    if "skim" in content and "_skim_cat" in content:
        print(f"  ✓ Shell aliases already in {shell_profile}")
        return

    with open(shell_profile, "a") as f:
        f.write("\n" + _SHELL_ALIASES)

    print(f"  ✓ Added shell aliases to {shell_profile}")


def _uninstall_shell_alias(agent: str) -> None:
    """Remove skim shell aliases."""
    shell_profile = _detect_shell_profile()
    if not shell_profile or not shell_profile.exists():
        print(f"  No shell profile found for {agent}.")
        return

    content = shell_profile.read_text()
    if "# skim - AST-aware token optimizer" not in content:
        print(f"  No skim aliases found in {shell_profile}.")
        return

    # Remove the skim alias block
    lines = content.split("\n")
    new_lines: list[str] = []
    in_skim_block = False
    for line in lines:
        if "# skim - AST-aware token optimizer" in line:
            in_skim_block = True
            continue
        if in_skim_block and "# end skim aliases" in line:
            in_skim_block = False
            continue
        if not in_skim_block:
            new_lines.append(line)

    shell_profile.write_text("\n".join(new_lines))
    print(f"  ✓ Removed skim aliases from {shell_profile}")


def _detect_shell_profile() -> Path | None:
    """Detect the user's shell profile file."""
    import os

    shell = os.environ.get("SHELL", "/bin/bash")

    if "zsh" in shell:
        return Path.home() / ".zshrc"
    elif "bash" in shell:
        bashrc = Path.home() / ".bashrc"
        bash_profile = Path.home() / ".bash_profile"
        if bashrc.exists():
            return bashrc
        return bash_profile
    elif "fish" in shell:
        return Path.home() / ".config" / "fish" / "config.fish"

    return Path.home() / ".bashrc"

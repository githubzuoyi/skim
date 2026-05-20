"""Tests for skim.hooks.init."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from skim.hooks import init
from skim.hooks.constants import (
    CLAUDE_HOOK,
    COPILOT_LAUNCHER_COMMAND,
    COPILOT_LAUNCHER_FILENAME,
    COPILOT_LAUNCHER_SH,
    COPILOT_HOOK_JSON,
    COPILOT_INSTRUCTIONS,
    CODEX_HOOK,
    CURSOR_HOOK_CONFIG,
    GLOBAL_LAUNCHER_FILENAME,
    GLOBAL_LAUNCHER_SH,
)


class TestInitCopilot:
    def test_writes_instructions_under_github_instructions(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(init, "_write_skill_file", lambda: None)

        init.init_copilot()

        hook_path = tmp_path / ".github" / "hooks" / "skim-rewrite.json"
        launcher_path = tmp_path / ".github" / "hooks" / COPILOT_LAUNCHER_FILENAME
        instructions_path = (
            tmp_path / ".github" / "instructions" / "copilot-instructions.md"
        )
        legacy_path = tmp_path / ".github" / "copilot-instructions.md"

        hook_json = json.loads(hook_path.read_text())

        assert hook_json == COPILOT_HOOK_JSON
        assert hook_json["hooks"]["PreToolUse"][0]["command"] == COPILOT_LAUNCHER_COMMAND
        assert launcher_path.read_text() == COPILOT_LAUNCHER_SH
        assert 'repo_root=$(CDPATH= cd -- "${script_dir}/../.." && pwd)' in COPILOT_LAUNCHER_SH
        assert "${VIRTUAL_ENV}/bin/skim" in COPILOT_LAUNCHER_SH
        assert "${repo_root}/skim/.venv/bin/skim" in COPILOT_LAUNCHER_SH
        assert 'find_spec("skim.__main__")' in COPILOT_LAUNCHER_SH
        assert COPILOT_LAUNCHER_SH.index('run_skim_python "${SKIM_PYTHON}"') < COPILOT_LAUNCHER_SH.index('if command -v skim >/dev/null 2>&1; then')
        assert COPILOT_LAUNCHER_SH.index('${repo_root}/.venv/bin/skim') < COPILOT_LAUNCHER_SH.index('if command -v skim >/dev/null 2>&1; then')
        assert launcher_path.stat().st_mode & 0o111
        syntax_check = subprocess.run(
            ["/bin/sh", "-n", str(launcher_path)],
            capture_output=True,
            text=True,
        )
        assert syntax_check.returncode == 0, syntax_check.stderr
        assert instructions_path.read_text() == COPILOT_INSTRUCTIONS
        assert not legacy_path.exists()


class TestInitClaudeAndCursor:
    def test_init_claude_writes_global_launcher(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(init, "_write_skill_file", lambda: None)
        monkeypatch.setattr(init, "_patch_claude_md", lambda: None)

        init.init_claude_global()

        settings_path = home / ".claude" / "settings.json"
        launcher_path = home / ".config" / "skim" / "launchers" / GLOBAL_LAUNCHER_FILENAME
        settings = json.loads(settings_path.read_text())
        hooks = settings["hooks"]["PreToolUse"]

        assert hooks == [CLAUDE_HOOK]
        assert launcher_path.read_text() == GLOBAL_LAUNCHER_SH
        assert "${VIRTUAL_ENV}/bin/skim" in GLOBAL_LAUNCHER_SH
        assert "$PWD/skim/.venv/bin/skim" in GLOBAL_LAUNCHER_SH
        assert 'find_spec("skim.__main__")' in GLOBAL_LAUNCHER_SH
        assert GLOBAL_LAUNCHER_SH.index('run_skim_python "${SKIM_PYTHON}"') < GLOBAL_LAUNCHER_SH.index('if command -v skim >/dev/null 2>&1; then')
        assert GLOBAL_LAUNCHER_SH.index('$PWD/.venv/bin/skim') < GLOBAL_LAUNCHER_SH.index('if command -v skim >/dev/null 2>&1; then')
        assert launcher_path.stat().st_mode & 0o111
        syntax_check = subprocess.run(
            ["/bin/sh", "-n", str(launcher_path)],
            capture_output=True,
            text=True,
        )
        assert syntax_check.returncode == 0, syntax_check.stderr

    def test_init_cursor_writes_global_launcher(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(init, "_write_skill_file", lambda: None)
        monkeypatch.setattr(init, "_write_cursor_rule", lambda: None)

        init.init_cursor()

        hooks_path = home / ".cursor" / "hooks.json"
        launcher_path = home / ".config" / "skim" / "launchers" / GLOBAL_LAUNCHER_FILENAME
        hooks = json.loads(hooks_path.read_text())["hooks"]["preToolUse"]

        assert hooks == [CURSOR_HOOK_CONFIG["hooks"]["preToolUse"][0]]
        assert launcher_path.read_text() == GLOBAL_LAUNCHER_SH
        assert launcher_path.stat().st_mode & 0o111

    def test_uninstall_cursor_removes_launcher_when_unused(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(init, "_write_skill_file", lambda: None)
        monkeypatch.setattr(init, "_write_cursor_rule", lambda: None)

        init.init_cursor()
        launcher_path = home / ".config" / "skim" / "launchers" / GLOBAL_LAUNCHER_FILENAME
        assert launcher_path.exists()

        init._uninstall_cursor()

        assert not launcher_path.exists()

    def test_uninstall_claude_keeps_launcher_if_cursor_still_uses_it(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(init, "_write_skill_file", lambda: None)
        monkeypatch.setattr(init, "_patch_claude_md", lambda: None)
        monkeypatch.setattr(init, "_write_cursor_rule", lambda: None)

        init.init_claude_global()
        init.init_cursor()
        launcher_path = home / ".config" / "skim" / "launchers" / GLOBAL_LAUNCHER_FILENAME
        assert launcher_path.exists()

        init._uninstall_claude()

        assert launcher_path.exists()


class TestInitCodex:
    def test_init_codex_writes_global_launcher(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(init, "_write_skill_file", lambda: None)

        init.init_codex()

        settings_path = home / ".codex" / "settings.json"
        launcher_path = home / ".config" / "skim" / "launchers" / GLOBAL_LAUNCHER_FILENAME
        settings = json.loads(settings_path.read_text())
        hooks = settings["hooks"]["PreToolUse"]

        assert hooks == [CODEX_HOOK]
        assert launcher_path.read_text() == GLOBAL_LAUNCHER_SH
        assert launcher_path.stat().st_mode & 0o111

    def test_uninstall_codex_removes_launcher_when_unused(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(init, "_write_skill_file", lambda: None)

        init.init_codex()
        launcher_path = home / ".config" / "skim" / "launchers" / GLOBAL_LAUNCHER_FILENAME
        assert launcher_path.exists()

        init._uninstall_codex()

        assert not launcher_path.exists()

    def test_uninstall_codex_keeps_launcher_if_claude_still_uses_it(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(init, "_write_skill_file", lambda: None)
        monkeypatch.setattr(init, "_patch_claude_md", lambda: None)

        init.init_codex()
        init.init_claude_global()
        launcher_path = home / ".config" / "skim" / "launchers" / GLOBAL_LAUNCHER_FILENAME
        assert launcher_path.exists()

        init._uninstall_codex()

        assert launcher_path.exists()
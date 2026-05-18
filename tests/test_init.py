"""Tests for skim.hooks.init."""

from __future__ import annotations

import json

from skim.hooks import init
from skim.hooks.constants import (
    COPILOT_LAUNCHER_COMMAND,
    COPILOT_LAUNCHER_FILENAME,
    COPILOT_LAUNCHER_SH,
    COPILOT_HOOK_JSON,
    COPILOT_INSTRUCTIONS,
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
        assert launcher_path.stat().st_mode & 0o111
        assert instructions_path.read_text() == COPILOT_INSTRUCTIONS
        assert not legacy_path.exists()
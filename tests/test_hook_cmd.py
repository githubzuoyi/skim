"""Tests for skim.hooks.hook_cmd."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from skim.hooks import hook_cmd


class TestHookDispatch:
    def test_cmd_hook_dispatches_codex(self, monkeypatch):
        calls: list[str] = []

        monkeypatch.setattr(hook_cmd, "run_codex_hook", lambda: calls.append("codex"))

        hook_cmd.cmd_hook(SimpleNamespace(agent="codex"))

        assert calls == ["codex"]


class TestCopilotShellHook:
    def test_run_in_terminal_preserves_required_fields(self, capsys):
        hook_cmd._handle_shell_command(
            {
                "tool_name": "run_in_terminal",
                "tool_input": {
                    "command": "cat skim/cli.py",
                    "explanation": "Read the file",
                    "goal": "Inspect code",
                    "mode": "sync",
                },
            }
        )

        output = json.loads(capsys.readouterr().out)
        updated = output["hookSpecificOutput"]["updatedInput"]

        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert updated["command"] == "skim read skim/cli.py"
        assert updated["explanation"] == "Read the file"
        assert updated["goal"] == "Inspect code"
        assert updated["mode"] == "sync"


class TestCopilotReadFileHook:
    def test_large_top_level_read_rewrites_to_temp_file(self, tmp_path, monkeypatch, capsys):
        source = tmp_path / "sample.py"
        source.write_text("\n".join(f"line {idx}" for idx in range(220)))

        def fake_build_read_output(path):
            assert path == source
            return "// structural summary\nclass Sample\n", "structural"

        def fake_materialize_hook_output(path, summary, summary_mode):
            assert path == source
            assert summary == "// structural summary\nclass Sample\n"
            assert summary_mode == "structural"
            return summary

        monkeypatch.setattr(hook_cmd, "_build_read_output", fake_build_read_output)
        monkeypatch.setattr(
            hook_cmd,
            "_materialize_hook_output",
            fake_materialize_hook_output,
        )

        hook_cmd._handle_read_file(
            {
                "tool_name": "read_file",
                "tool_input": {
                    "filePath": str(source),
                    "startLine": 1,
                    "endLine": 200,
                },
            }
        )

        output = json.loads(capsys.readouterr().out)
        updated = output["hookSpecificOutput"]["updatedInput"]

        assert updated["filePath"].startswith("/tmp/skim-hook/")
        assert updated["startLine"] == 1
        assert updated["endLine"] == 200
        assert Path(updated["filePath"]).read_text() == "// structural summary\nclass Sample\n"

    def test_cached_summary_reuses_previous_structural_read(self, tmp_path, monkeypatch):
        source = tmp_path / "sample.py"
        source.write_text("\n".join(f"line {idx}" for idx in range(220)))

        calls = []

        class Result:
            content = "// structural summary\nclass Sample\n"
            mode = "structural"

        def fake_structural_read(path):
            calls.append(path)
            return Result()

        monkeypatch.setattr("skim.ast_engine.structural_read", fake_structural_read)

        first = hook_cmd._build_read_output(source)
        second = hook_cmd._build_read_output(source)

        assert first == ("// structural summary\nclass Sample\n", "structural")
        assert second == first
        assert calls == [source]

    def test_legacy_cached_summary_is_ignored(self, tmp_path, monkeypatch):
        source = tmp_path / "sample.py"
        source.write_text("\n".join(f"line {idx}" for idx in range(220)))

        output_file, summary_file, meta_file = hook_cmd._hook_cache_paths(source)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        summary_file.write_text("// stale summary\n")
        stat = source.stat()
        meta_file.write_text(
            json.dumps(
                {
                    "summary_version": hook_cmd._HOOK_SUMMARY_VERSION - 1,
                    "mtime_ns": stat.st_mtime_ns,
                    "size": stat.st_size,
                    "mode": "structural",
                }
            )
        )

        calls = []

        class Result:
            content = "// fresh summary\n"
            mode = "structural"

        def fake_structural_read(path):
            calls.append(path)
            return Result()

        monkeypatch.setattr("skim.ast_engine.structural_read", fake_structural_read)

        rebuilt = hook_cmd._build_read_output(source)

        assert rebuilt == ("// fresh summary\n", "structural")
        assert calls == [source]

    def test_targeted_read_does_not_rewrite(self, tmp_path, capsys):
        source = tmp_path / "sample.py"
        source.write_text("\n".join(f"line {idx}" for idx in range(220)))

        hook_cmd._handle_read_file(
            {
                "tool_name": "read_file",
                "tool_input": {
                    "filePath": str(source),
                    "startLine": 120,
                    "endLine": 140,
                },
            }
        )

        assert capsys.readouterr().out == ""
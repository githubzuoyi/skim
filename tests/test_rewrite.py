"""Tests for skim.hooks.rewrite."""

from skim.hooks.rewrite import rewrite_command


class TestRewriteCommand:
    def test_cat_code_file(self):
        assert rewrite_command("cat main.py") == "skim read main.py"
        assert rewrite_command("cat src/auth.ts") == "skim read src/auth.ts"
        assert rewrite_command("cat server.rs") == "skim read server.rs"

    def test_cat_non_code_file(self):
        assert rewrite_command("cat README.md") is None
        assert rewrite_command("cat data.json") is None

    def test_cat_with_flags(self):
        assert rewrite_command("cat -n main.py") is None

    def test_head_code_file(self):
        assert rewrite_command("head -50 auth.ts") == "skim read auth.ts"
        assert rewrite_command("head main.py") == "skim read main.py"

    def test_tail_code_file(self):
        assert rewrite_command("tail server.go") == "skim read server.go"

    def test_git_status(self):
        assert rewrite_command("git status") == "skim git status"

    def test_git_diff(self):
        assert rewrite_command("git diff") == "skim git diff"

    def test_git_log(self):
        result = rewrite_command("git log --oneline")
        assert result == "skim git log --oneline"

    def test_git_push_no_rewrite(self):
        assert rewrite_command("git push origin main") is None

    def test_compound_command(self):
        result = rewrite_command("cat file.py && git status")
        assert result == "skim read file.py && skim git status"

    def test_pipe_not_rewritten(self):
        assert rewrite_command("cat main.py | grep test") is None
        assert rewrite_command("cat main.py | wc -l") is None
        assert rewrite_command("git status | grep modified") is None

    def test_already_skim(self):
        assert rewrite_command("skim read file.py") is None

    def test_excluded_commands(self):
        assert rewrite_command("curl https://example.com") is None
        assert rewrite_command("wget file") is None

    def test_empty(self):
        assert rewrite_command("") is None
        assert rewrite_command("   ") is None

    def test_semicolon_compound(self):
        result = rewrite_command("cat a.py ; git diff")
        assert "skim read a.py" in result
        assert "skim git diff" in result

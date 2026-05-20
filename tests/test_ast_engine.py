"""Tests for skim.ast_engine."""

import importlib.util
from pathlib import Path

import pytest

from skim.ast_engine import structural_read, read_symbol, LANGUAGES

FIXTURES = Path(__file__).parent / "fixtures"


class TestStructuralRead:
    def test_small_file_returns_full(self):
        result = structural_read(FIXTURES / "small.py")
        assert result.mode == "full"
        assert "def add" in result.content
        assert "def multiply" in result.content

    def test_python_structural(self):
        result = structural_read(FIXTURES / "sample.py", small_file_threshold=50)
        assert result.mode == "structural"
        assert result.original_lines > result.summary_lines
        assert "UserService" in result.content
        assert "AuthService" in result.content
        assert "hash_password" in result.content
        assert result.symbols_count > 0

    def test_structural_summary_includes_line_spans(self):
        result = structural_read(FIXTURES / "sample.py", small_file_threshold=50)

        assert "class UserService  [L13-L53]" in result.content
        assert "def get_user(self, user_id: int) -> Optional[dict]  [L20-L28]" in result.content
        assert "def hash_password(password: str, salt: Optional[str] = None) -> str  [L76-L82]" in result.content
        assert "skim tokens ~" not in result.content
        assert "saved ~" not in result.content
        assert "drill-down: use the original file path above" not in result.content
        assert "lines ->" not in result.content

    def test_python_module_constants_fallback(self, tmp_path):
        source = tmp_path / "constants.py"
        source.write_text(
            '"""Module constants."""\n'
            "from __future__ import annotations\n"
            "\n"
            "PRIMARY_MODEL = \"gpt-5.4\"\n"
            "API_OPTIONS = {\n"
            "    \"timeout\": 30,\n"
            "    \"retries\": 2,\n"
            "}\n"
            "PROMPT_TEMPLATE = \"\"\"system\n"
            "user\n"
            "assistant\n"
            "\"\"\"\n"
        )

        result = structural_read(source, small_file_threshold=1)

        assert result.mode == "structural"
        assert "0 symbols" not in result.content
        assert "PRIMARY_MODEL = \"gpt-5.4\"  [L4]" in result.content
        assert "API_OPTIONS = {  [L5-L8]" in result.content
        assert "PROMPT_TEMPLATE = \"\"\"system  [L9-L12]" in result.content
        assert '"""Module constants."""' not in result.content

    def test_decorated_class_and_method_are_extracted(self, tmp_path):
        source = tmp_path / "decorated.py"
        source.write_text(
            "import functools\n"
            "\n"
            "@requires(backend=\"torch\")\n"
            "class Trainer:\n"
            "    @classmethod\n"
            "    def build(cls):\n"
            "        pass\n"
            "\n"
            "@functools.lru_cache\n"
            "def helper():\n"
            "    return 1\n"
        )

        result = structural_read(source, small_file_threshold=1)

        assert result.mode == "structural"
        assert '@requires(backend="torch")' in result.content
        assert "class Trainer  [L4-L7]" in result.content
        assert "def build(cls)  [L6-L7]" in result.content
        assert "def helper()  [L10-L11]" in result.content

    def test_typescript_structural(self):
        result = structural_read(FIXTURES / "sample.ts", small_file_threshold=50)
        assert result.mode == "structural"
        assert result.original_lines > result.summary_lines
        assert "UserRepository" in result.content
        assert "AuthService" in result.content
        assert "validateEmail" in result.content

    def test_rust_structural(self):
        if importlib.util.find_spec("tree_sitter_rust") is None:
            pytest.skip("tree_sitter_rust is optional and not installed in this environment")
        result = structural_read(FIXTURES / "sample.rs", small_file_threshold=50)
        assert result.mode == "structural"
        assert "InMemoryRepo" in result.content or "hash_password" in result.content

    def test_nonexistent_language_fallback(self):
        """Files with unknown extensions should use head+tail fallback."""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".xyz", mode="w", delete=False) as f:
            f.write("\n".join(f"line {i}" for i in range(200)))
            f.flush()
            result = structural_read(Path(f.name), small_file_threshold=50)
            assert result.mode in ("head_tail", "full")
            Path(f.name).unlink()

    def test_savings_percentage(self):
        result = structural_read(FIXTURES / "sample.ts", small_file_threshold=50)
        ratio = result.summary_lines / result.original_lines
        assert ratio < 0.5, f"Expected >50% reduction, got {ratio:.0%}"


class TestReadSymbol:
    def test_read_function(self):
        result = read_symbol(FIXTURES / "sample.py", "hash_password")
        assert result.mode == "symbol"
        assert "def hash_password" in result.content
        assert "hashlib" in result.content

    def test_read_class(self):
        result = read_symbol(FIXTURES / "sample.py", "UserService")
        assert result.mode == "symbol"
        assert "class UserService" in result.content

    def test_read_method(self):
        result = read_symbol(FIXTURES / "sample.py", "UserService.get_user")
        assert result.mode == "symbol"
        assert "def get_user" in result.content

    def test_read_nonexistent_symbol(self):
        result = read_symbol(FIXTURES / "sample.py", "nonexistent_function")
        assert "not found" in result.content.lower()

    def test_read_ts_symbol(self):
        result = read_symbol(FIXTURES / "sample.ts", "validateEmail")
        assert result.mode == "symbol"
        assert "validateEmail" in result.content


class TestLanguageConfigs:
    def test_python_config(self):
        assert ".py" in LANGUAGES
        cfg = LANGUAGES[".py"]
        assert "function_definition" in cfg.function_types
        assert "class_definition" in cfg.class_types

    def test_typescript_config(self):
        assert ".ts" in LANGUAGES
        cfg = LANGUAGES[".ts"]
        assert cfg.ts_language_fn == "language_typescript"

    def test_rust_config(self):
        assert ".rs" in LANGUAGES
        cfg = LANGUAGES[".rs"]
        assert "function_item" in cfg.function_types

    def test_go_config(self):
        assert ".go" in LANGUAGES

    def test_java_config(self):
        assert ".java" in LANGUAGES

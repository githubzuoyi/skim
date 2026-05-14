"""Tests for skim.session."""

from skim.session import SessionManager, estimate_tokens


class TestEstimateTokens:
    def test_empty(self):
        assert estimate_tokens("") == 0

    def test_ascii(self):
        # 12 bytes → ceil(12/4) = 3
        assert estimate_tokens("hello world!") == 3

    def test_unicode(self):
        text = "こんにちは"  # 15 bytes in UTF-8
        assert estimate_tokens(text) == 4  # ceil(15/4)

    def test_large(self):
        text = "x" * 1000
        assert estimate_tokens(text) == 250


class TestSessionManager:
    def _make_session(self):
        sm = SessionManager(session_id="test-session-unit")
        sm.clear()
        return sm

    def test_first_read_returns_full(self):
        sm = self._make_session()
        output, saved = sm.check("key1", "content here")
        assert output == "content here"
        assert saved == 0
        sm.clear()

    def test_unchanged_content_dedup(self):
        sm = self._make_session()
        long_content = "x" * 200
        sm.check("key2", long_content)
        output, saved = sm.check("key2", long_content)
        assert "[unchanged" in output
        assert saved > 0
        sm.clear()

    def test_changed_content_returns_delta(self):
        sm = self._make_session()
        sm.check("key3", "original content " * 10)
        output, saved = sm.check("key3", "changed content " * 10)
        assert "[changed]" in output
        sm.clear()

    def test_small_content_not_deduped(self):
        sm = self._make_session()
        sm.check("key4", "tiny")
        output, saved = sm.check("key4", "tiny")
        # Small content should return as-is because unchanged marker is longer
        assert saved == 0
        assert output == "tiny"
        sm.clear()

    def test_session_info(self):
        sm = self._make_session()
        sm.check("info-key", "some content " * 20)
        info = sm.info()
        assert info["entries"] == 1
        assert info["session_id"] == "test-session-unit"
        sm.clear()

    def test_clear(self):
        sm = self._make_session()
        sm.check("clear-key", "data")
        sm.clear()
        info = sm.info()
        assert info["entries"] == 0

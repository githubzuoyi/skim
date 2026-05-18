"""Tests for skim.tracking."""

import json
import tempfile
from pathlib import Path

from skim.pricing import estimate_input_cost, resolve_pricing_model
from skim.tracking import Tracker


class TestTracker:
    def _make_tracker(self):
        db_path = Path(tempfile.mktemp(suffix=".db"))
        return Tracker(db_path=db_path), db_path

    def test_record_and_summary(self):
        tracker, db = self._make_tracker()
        tracker.record("read file.py", "x" * 4000, "x" * 200, "structural")
        tracker.record("read file.py", "x" * 4000, "[unchanged]", "dedup")

        summary = tracker.gain_summary()
        assert summary["total_operations"] == 2
        assert summary["total_tokens_saved"] > 0

        tracker.close()
        db.unlink(missing_ok=True)

    def test_mode_breakdown(self):
        tracker, db = self._make_tracker()
        tracker.record("read a.py", "x" * 1000, "x" * 100, "structural")
        tracker.record("git status", "x" * 500, "x" * 50, "compress")
        tracker.record("read a.py", "x" * 1000, "[unchanged]", "dedup")

        summary = tracker.gain_summary()
        modes = {m["mode"]: m for m in summary["modes"]}
        assert "structural" in modes
        assert "compress" in modes
        assert "dedup" in modes

        tracker.close()
        db.unlink(missing_ok=True)

    def test_reset(self):
        tracker, db = self._make_tracker()
        tracker.record("test", "abc", "a", "compress")
        tracker.reset()

        summary = tracker.gain_summary()
        assert summary["total_operations"] == 0

        tracker.close()
        db.unlink(missing_ok=True)

    def test_empty_summary(self):
        tracker, db = self._make_tracker()
        summary = tracker.gain_summary()
        assert summary["total_operations"] == 0
        assert summary["total_tokens_saved"] == 0
        assert summary["pricing_model"] == "gpt-5.4"

        tracker.close()
        db.unlink(missing_ok=True)

    def test_gain_summary_uses_gpt_5_4_input_pricing(self):
        tracker, db = self._make_tracker()
        tracker.record("read file.py", "x" * 4000, "x" * 200, "structural")

        summary = tracker.gain_summary()
        assert summary["pricing_display_name"] == "GPT-5.4"
        assert summary["input_price_per_million"] == 2.50
        assert summary["est_input_cost_saved"] == estimate_input_cost(summary["total_tokens_saved"])

        tracker.close()
        db.unlink(missing_ok=True)

    def test_gain_summary_includes_latest_copilot_session_share(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        tracker, db = self._make_tracker()

        session_ts = 1_800_000_000.0
        session_dir = tmp_path / "session-123"
        session_dir.mkdir()
        session_log = session_dir / "main.jsonl"
        monkeypatch.setenv("VSCODE_TARGET_SESSION_LOG", str(session_log))
        monkeypatch.setattr("skim.tracking.time.time", lambda: session_ts + 5)
        tracker.record("read file.py", "x" * 4000, "x" * 200, "structural")

        session_log.write_text(
            json.dumps(
                {
                    "ts": int(session_ts * 1000),
                    "dur": 1000,
                    "type": "llm_request",
                    "attrs": {
                        "inputTokens": 3000,
                        "outputTokens": 120,
                        "cachedTokens": 800,
                    },
                }
            )
            + "\n"
        )

        summary = tracker.gain_summary(session_log_path=session_log)
        latest = summary["latest_copilot_session"]

        assert latest is not None
        assert latest["non_cached_input_tokens"] == 2200
        assert latest["skim_saved_tokens"] == summary["total_tokens_saved"]
        assert latest["skim_input_tokens"] == 1000
        assert latest["skim_share_of_non_cached_input_pct"] == round(
            summary["total_tokens_saved"] / 2200 * 100,
            1,
        )
        assert latest["skim_compression_efficiency_pct"] == round(
            summary["total_tokens_saved"] / 1000 * 100,
            1,
        )

        tracker.close()
        db.unlink(missing_ok=True)

    def test_gain_summary_ignores_time_window_rows_with_mismatched_session_id(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        tracker, db = self._make_tracker()

        session_ts = 1_800_000_000.0
        session_dir = tmp_path / "session-abc"
        session_dir.mkdir()
        session_log = session_dir / "main.jsonl"

        monkeypatch.setattr("skim.tracking.time.time", lambda: session_ts + 5)
        tracker.record(
            "read file.py",
            "x" * 4000,
            "x" * 200,
            "structural",
            session_id="legacy-pid",
        )

        session_log.write_text(
            json.dumps(
                {
                    "ts": int(session_ts * 1000),
                    "dur": 1000,
                    "type": "llm_request",
                    "attrs": {
                        "inputTokens": 3000,
                        "outputTokens": 120,
                        "cachedTokens": 800,
                    },
                }
            )
            + "\n"
        )

        summary = tracker.gain_summary(session_log_path=session_log)
        latest = summary["latest_copilot_session"]

        assert latest is not None
        assert latest["non_cached_input_tokens"] == 2200
        assert latest["skim_input_tokens"] == 0
        assert latest["skim_saved_tokens"] == 0
        assert latest["skim_share_of_non_cached_input_pct"] == 0.0
        assert latest["skim_compression_efficiency_pct"] == 0.0

        tracker.close()
        db.unlink(missing_ok=True)

    def test_gain_summary_backfills_legacy_rows_for_active_session(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        tracker, db = self._make_tracker()

        session_ts = 1_800_000_000.0
        session_dir = tmp_path / "session-live"
        session_dir.mkdir()
        session_log = session_dir / "main.jsonl"

        monkeypatch.setenv("VSCODE_TARGET_SESSION_LOG", str(session_log))
        monkeypatch.setattr("skim.tracking.time.time", lambda: session_ts + 5)
        tracker.record(
            "read file.py",
            "x" * 4000,
            "x" * 200,
            "structural",
            session_id="12345",
        )

        session_log.write_text(
            json.dumps(
                {
                    "ts": int(session_ts * 1000),
                    "dur": 1000,
                    "type": "llm_request",
                    "attrs": {
                        "inputTokens": 3000,
                        "outputTokens": 120,
                        "cachedTokens": 800,
                    },
                }
            )
            + "\n"
        )

        summary = tracker.gain_summary()
        latest = summary["latest_copilot_session"]

        assert latest is not None
        assert latest["skim_input_tokens"] == 1000
        assert latest["skim_saved_tokens"] == 950
        assert tracker._conn.execute("SELECT DISTINCT session_id FROM commands").fetchall() == [
            ("session-live",),
        ]

        tracker.close()
        db.unlink(missing_ok=True)

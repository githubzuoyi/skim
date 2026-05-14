"""Tests for skim.tracking."""

import tempfile
from pathlib import Path
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

        tracker.close()
        db.unlink(missing_ok=True)

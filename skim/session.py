"""Session state manager for cross-invocation deduplication.

Tracks content hashes across skim invocations within the same AI agent
session (keyed by parent PID). When the agent re-reads a file that hasn't
changed, returns ``[unchanged]`` instead of the full content.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from skim.pricing import savings_pct


# ---------------------------------------------------------------------------
# Token estimation (matches rtk's ceil(byte_length / 4) approach)
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Estimate token count: ceil(byte_length / 4)."""
    return -(-len(text.encode("utf-8")) // 4)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class CacheEntry:
    content_hash: str
    first_seen: float
    last_seen: float
    hit_count: int = 1
    original_tokens: int = 0
    saved_tokens: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> CacheEntry:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# SessionManager
# ---------------------------------------------------------------------------

class SessionManager:
    """Manages per-session state for content deduplication.

    Session is keyed by the parent PID (the AI agent process). State is
    persisted to a JSON file in /tmp so it survives across skim invocations.
    """

    EXPIRY_SECONDS = 1800  # 30 min inactivity

    def __init__(self, *, session_id: str | None = None):
        if session_id:
            self._session_id = session_id
        else:
            self._session_id = str(os.getppid())

        self._state_path = Path(f"/tmp/skim-{self._session_id}.json")
        self._entries: dict[str, CacheEntry] = {}
        self._session_start: float | None = None
        self._load()

    def check(self, key: str, current_content: str) -> tuple[str, int]:
        """Check if content was seen before in this session.

        Returns (output_to_send, tokens_saved).
        - If unchanged: returns "[unchanged since <time>]" and large savings.
        - If changed: returns delta and partial savings.
        - If first read: stores hash and returns full content.
        """
        current_hash = hashlib.sha256(current_content.encode()).hexdigest()
        now = time.time()

        if key in self._entries:
            entry = self._entries[key]

            if entry.content_hash == current_hash:
                entry.hit_count += 1
                entry.last_seen = now
                current_tokens = estimate_tokens(current_content)
                unchanged_msg = _format_unchanged_marker(
                    now - entry.first_seen,
                    current_tokens,
                )
                saved = current_tokens - estimate_tokens(unchanged_msg)
                if saved <= 0:
                    # Content is smaller than the unchanged marker — not worth deduplicating
                    self._save()
                    return current_content, 0
                entry.saved_tokens += saved
                self._save()
                return unchanged_msg, saved
            else:
                delta = _compute_delta(entry.content_hash, current_content, key)
                delta_tokens = estimate_tokens(delta)
                current_tokens = estimate_tokens(current_content)
                saved = current_tokens - delta_tokens

                entry.content_hash = current_hash
                entry.last_seen = now
                entry.hit_count += 1
                entry.saved_tokens += max(saved, 0)
                self._save()
                return delta, max(saved, 0)
        else:
            current_tokens = estimate_tokens(current_content)
            self._entries[key] = CacheEntry(
                content_hash=current_hash,
                first_seen=now,
                last_seen=now,
                original_tokens=current_tokens,
            )
            self._save()
            return current_content, 0

    def clear(self) -> None:
        """Clear all session state."""
        self._entries.clear()
        self._session_start = None
        if self._state_path.exists():
            self._state_path.unlink()

    def info(self) -> dict[str, Any]:
        """Return session info for display."""
        total_saved = sum(e.saved_tokens for e in self._entries.values())
        return {
            "session_id": self._session_id,
            "entries": len(self._entries),
            "total_saved_tokens": total_saved,
            "state_path": str(self._state_path),
            "started_at": _fmt_absolute_time(self._session_start) if self._session_start else None,
        }

    # ----- persistence -----

    def _load(self) -> None:
        if not self._state_path.exists():
            return
        try:
            data = json.loads(self._state_path.read_text())
            self._session_start = data.get("session_start")

            now = time.time()
            for key, entry_dict in data.get("entries", {}).items():
                entry = CacheEntry.from_dict(entry_dict)
                if now - entry.last_seen < self.EXPIRY_SECONDS:
                    self._entries[key] = entry
        except (json.JSONDecodeError, KeyError, TypeError):
            self._entries.clear()

    def _save(self) -> None:
        if self._session_start is None:
            self._session_start = time.time()

        data = {
            "session_start": self._session_start,
            "session_id": self._session_id,
            "entries": {k: v.to_dict() for k, v in self._entries.items()},
        }
        try:
            self._state_path.write_text(json.dumps(data))
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_delta(old_hash: str, new_content: str, key: str) -> str:
    """Compute a human-readable delta description when content has changed.

    We don't store old content (only its hash), so we return the new content
    prefixed with a change marker. A future enhancement could store old content
    for real diffs.
    """
    lines = new_content.split("\n")
    if len(lines) < 30:
        return f"[changed] {key}\n{new_content}"

    return f"[changed] {key} ({len(lines)} lines)\n{new_content}"


def _format_unchanged_marker(age_seconds: float, current_tokens: int) -> str:
    """Keep dedup markers compact while still surfacing saved-token impact."""

    relative = _fmt_relative_time(age_seconds)
    marker = f"[unchanged since {relative}]"

    for _ in range(2):
        marker_tokens = estimate_tokens(marker)
        saved = current_tokens - marker_tokens
        if saved <= 0:
            return marker
        marker = (
            f"[unchanged since {relative} | skim ~{saved:,} input tokens saved / "
            f"{savings_pct(current_tokens, marker_tokens)}%]"
        )

    return marker


def _fmt_relative_time(seconds: float) -> str:
    """Format seconds into a human-readable relative time."""
    if seconds < 60:
        return f"{int(seconds)}s ago"
    elif seconds < 3600:
        return f"{int(seconds / 60)}m ago"
    else:
        return f"{int(seconds / 3600)}h ago"


def _fmt_absolute_time(ts: float | None) -> str | None:
    """Format a timestamp into a readable string."""
    if ts is None:
        return None
    import datetime

    return datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")

"""Fire-and-forget usage reporter for BATWTechworks internal telemetry.

Sends a lightweight POST to the skim stats server on each operation.
Uses a background thread so it never blocks the CLI.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
import urllib.error
from typing import Any


def report_usage(
    *,
    command: str,
    input_tokens: int,
    output_tokens: int,
    saved_tokens: int,
    mode: str,
    project: str | None = None,
) -> None:
    """Send usage data to the stats server (non-blocking).

    Silently does nothing if email is not configured or server is unreachable.
    """
    from skim.config import get_config

    config = get_config()
    email = config.user.email
    if not email:
        return

    server_url = config.server.url.rstrip("/")

    if project is None:
        try:
            project = os.path.basename(os.getcwd())
        except OSError:
            project = "unknown"

    payload: dict[str, Any] = {
        "email": email,
        "command": command,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "saved_tokens": saved_tokens,
        "mode": mode,
        "project": project,
        "timestamp": time.time(),
        "hostname": _hostname(),
    }

    t = threading.Thread(target=_send, args=(server_url, payload), daemon=True)
    t.start()


def _send(server_url: str, payload: dict[str, Any]) -> None:
    """POST payload to the stats server. Fails silently."""
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{server_url}/api/report",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass


def _hostname() -> str:
    try:
        import socket
        return socket.gethostname()
    except Exception:
        return "unknown"

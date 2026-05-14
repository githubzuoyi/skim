"""Configuration management for skim.

Reads settings from ``~/.config/skim/config.toml`` with sensible defaults.
Supports Python 3.10 (uses ``tomli``) and 3.11+ (uses ``tomllib``).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class HooksConfig:
    exclude_commands: list[str] = field(default_factory=lambda: ["curl", "wget", "ssh", "scp"])


@dataclass
class ReadConfig:
    small_file_threshold: int = 150
    structural_summary: bool = True


@dataclass
class SessionConfig:
    enabled: bool = True
    expiry_minutes: int = 30


@dataclass
class TrackingConfig:
    enabled: bool = True
    history_days: int = 90


@dataclass
class DisplayConfig:
    show_savings_hint: bool = True


@dataclass
class ServerConfig:
    url: str = "http://localhost:7745"


@dataclass
class UserConfig:
    email: str = ""


@dataclass
class SkimConfig:
    hooks: HooksConfig = field(default_factory=HooksConfig)
    read: ReadConfig = field(default_factory=ReadConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    tracking: TrackingConfig = field(default_factory=TrackingConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    user: UserConfig = field(default_factory=UserConfig)


def _config_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".config"
    return base / "skim" / "config.toml"


def _load_toml(path: Path) -> dict[str, Any]:
    """Load a TOML file, handling Python 3.10 vs 3.11+."""
    if not path.exists():
        return {}

    raw = path.read_bytes()

    if sys.version_info >= (3, 11):
        import tomllib
        return tomllib.loads(raw.decode("utf-8"))
    else:
        try:
            import tomli
            return tomli.loads(raw.decode("utf-8"))
        except ImportError:
            return {}


def load_config(path: Path | None = None) -> SkimConfig:
    """Load skim configuration from TOML file.

    Falls back to defaults for any missing values.
    """
    if path is None:
        path = _config_path()

    data = _load_toml(path)

    config = SkimConfig()

    hooks_data = data.get("hooks", {})
    if "exclude_commands" in hooks_data:
        config.hooks.exclude_commands = hooks_data["exclude_commands"]

    read_data = data.get("read", {})
    if "small_file_threshold" in read_data:
        config.read.small_file_threshold = int(read_data["small_file_threshold"])
    if "structural_summary" in read_data:
        config.read.structural_summary = bool(read_data["structural_summary"])

    session_data = data.get("session", {})
    if "enabled" in session_data:
        config.session.enabled = bool(session_data["enabled"])
    if "expiry_minutes" in session_data:
        config.session.expiry_minutes = int(session_data["expiry_minutes"])

    tracking_data = data.get("tracking", {})
    if "enabled" in tracking_data:
        config.tracking.enabled = bool(tracking_data["enabled"])
    if "history_days" in tracking_data:
        config.tracking.history_days = int(tracking_data["history_days"])

    display_data = data.get("display", {})
    if "show_savings_hint" in display_data:
        config.display.show_savings_hint = bool(display_data["show_savings_hint"])

    server_data = data.get("server", {})
    if "url" in server_data:
        config.server.url = str(server_data["url"])

    user_data = data.get("user", {})
    if "email" in user_data:
        config.user.email = str(user_data["email"])

    return config


def save_user_email(email: str, path: Path | None = None) -> None:
    """Persist user email to the config file (TOML format)."""
    if path is None:
        path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = ""
    if path.exists():
        existing = path.read_text()

    if "[user]" in existing:
        lines = existing.split("\n")
        new_lines: list[str] = []
        in_user = False
        email_written = False
        for line in lines:
            if line.strip() == "[user]":
                in_user = True
                new_lines.append(line)
                continue
            if in_user and line.strip().startswith("email"):
                new_lines.append(f'email = "{email}"')
                email_written = True
                in_user = False
                continue
            if in_user and line.strip().startswith("["):
                if not email_written:
                    new_lines.append(f'email = "{email}"')
                    email_written = True
                in_user = False
            new_lines.append(line)
        if in_user and not email_written:
            new_lines.append(f'email = "{email}"')
        path.write_text("\n".join(new_lines))
    else:
        with open(path, "a") as f:
            f.write(f'\n[user]\nemail = "{email}"\n')

    global _config
    if _config is not None:
        _config.user.email = email


# Cached global config
_config: SkimConfig | None = None


def get_config() -> SkimConfig:
    """Get or load the global config singleton."""
    global _config
    if _config is None:
        _config = load_config()
    return _config

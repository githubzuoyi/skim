"""Terminal styling for skim CLI output.

Provides ANSI color utilities with automatic TTY detection.
Respects NO_COLOR (https://no-color.org/) and dumb terminals.
"""

from __future__ import annotations

import os
import sys


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


_COLOR = _supports_color()


def _ansi(code: str) -> str:
    return f"\033[{code}m" if _COLOR else ""


# --- Base codes ---
RESET = _ansi("0")
BOLD = _ansi("1")
DIM = _ansi("2")
ITALIC = _ansi("3")
UNDERLINE = _ansi("4")

# --- Foreground ---
BLACK = _ansi("30")
RED = _ansi("31")
GREEN = _ansi("32")
YELLOW = _ansi("33")
BLUE = _ansi("34")
MAGENTA = _ansi("35")
CYAN = _ansi("36")
WHITE = _ansi("37")

# --- Bright foreground ---
BRIGHT_BLACK = _ansi("90")
BRIGHT_RED = _ansi("91")
BRIGHT_GREEN = _ansi("92")
BRIGHT_YELLOW = _ansi("93")
BRIGHT_BLUE = _ansi("94")
BRIGHT_MAGENTA = _ansi("95")
BRIGHT_CYAN = _ansi("96")
BRIGHT_WHITE = _ansi("97")

# --- Background ---
BG_BLACK = _ansi("40")
BG_WHITE = _ansi("47")
BG_CYAN = _ansi("46")
BG_GREEN = _ansi("42")


# --- Semantic helpers ---

def bold(text: str) -> str:
    return f"{BOLD}{text}{RESET}"


def dim(text: str) -> str:
    return f"{DIM}{text}{RESET}"


def colored(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


def savings_color(pct: int) -> str:
    """Pick a color based on savings percentage."""
    if pct >= 90:
        return BRIGHT_GREEN
    elif pct >= 70:
        return GREEN
    elif pct >= 50:
        return YELLOW
    elif pct > 0:
        return WHITE
    else:
        return DIM


def fmt_savings(pct: int) -> str:
    """Format a savings percentage with color."""
    color = savings_color(pct)
    return f"{color}-{pct}%{RESET}"


def fmt_number(n: int) -> str:
    """Format a number with thousands separators."""
    return f"{n:,}"


# --- Layout ---

LOGO = f"""{BOLD}{CYAN}skim{RESET}"""

BOX_H = "─"
BOX_V = "│"
BOX_TL = "┌"
BOX_TR = "┐"
BOX_BL = "└"
BOX_BR = "┘"
BOX_T = "┬"
BOX_B = "┴"
BOX_L = "├"
BOX_R = "┤"
BOX_X = "┼"


def hline(width: int = 60) -> str:
    """Horizontal line with dim style."""
    return f"{DIM}{BOX_H * width}{RESET}"


def header_line(text: str, width: int = 60) -> str:
    """A section header with surrounding dashes."""
    pad = width - len(text) - 4
    left = pad // 2
    right = pad - left
    return f"{DIM}{BOX_H * left}{RESET} {BOLD}{text}{RESET} {DIM}{BOX_H * right}{RESET}"


# --- Symbols ---
CHECK = f"{GREEN}✓{RESET}" if _COLOR else "✓"
CROSS = f"{RED}✗{RESET}" if _COLOR else "✗"
WARN = f"{YELLOW}⚠{RESET}" if _COLOR else "⚠"
ARROW = f"{CYAN}→{RESET}" if _COLOR else "→"
BULLET = f"{DIM}•{RESET}" if _COLOR else "•"
SAVED = f"{GREEN}▼{RESET}" if _COLOR else "▼"

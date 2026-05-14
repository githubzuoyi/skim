#!/bin/sh
# skim installer — installs skimcode from PyPI and sets up hooks
# Usage: curl -fsSL https://raw.githubusercontent.com/skim-ai/skim/main/install.sh | sh
set -e

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

info() { printf "${GREEN}▸${RESET} %s\n" "$1"; }
warn() { printf "${YELLOW}▸${RESET} %s\n" "$1"; }
error() { printf "${RED}▸${RESET} %s\n" "$1"; exit 1; }

echo ""
echo "${BOLD}skim${RESET} — AST-aware token optimizer for AI coding"
echo ""

# Check Python version
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        version=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    error "Python 3.10+ is required. Install it from https://www.python.org/downloads/"
fi

info "Using $PYTHON ($($PYTHON --version 2>&1))"

# Install skimcode
if command -v uv >/dev/null 2>&1; then
    info "Installing via uv..."
    uv tool install skimcode 2>/dev/null || uv pip install --system skimcode
elif command -v pipx >/dev/null 2>&1; then
    info "Installing via pipx..."
    pipx install skimcode
else
    info "Installing via pip..."
    $PYTHON -m pip install --user skimcode
fi

# Verify installation
if ! command -v skim >/dev/null 2>&1; then
    # Try common user bin paths
    for bindir in "$HOME/.local/bin" "$HOME/.cargo/bin" "$HOME/Library/Python/*/bin"; do
        if [ -f "$bindir/skim" ]; then
            export PATH="$bindir:$PATH"
            break
        fi
    done
fi

if command -v skim >/dev/null 2>&1; then
    info "skim $(skim --version 2>/dev/null || echo '') installed successfully"
else
    warn "skim installed but not in PATH"
    warn "Add ~/.local/bin to your PATH, then run: skim init -g"
    exit 0
fi

# Detect which AI tool to configure
AGENT="claude"
if [ -d "$HOME/.cursor" ] && [ ! -d "$HOME/.claude" ]; then
    AGENT="cursor"
fi

# Install hooks
info "Installing hooks for $AGENT..."
skim init -g --agent "$AGENT"

echo ""
info "Done! Restart your AI coding tool to activate skim."
info "Run ${BOLD}skim gain${RESET} anytime to see token savings."
echo ""

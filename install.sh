#!/usr/bin/env bash
# skim installer — installs skim from the GitHub repository into a managed user venv.
# Usage: curl -fsSL https://raw.githubusercontent.com/ericzuo-ai/skim/main/install.sh | bash
set -euo pipefail

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

info() { printf "%b\n" "${GREEN}▸${RESET} $1"; }
warn() { printf "%b\n" "${YELLOW}▸${RESET} $1"; }
error() { printf "%b\n" "${RED}▸${RESET} $1"; exit 1; }

REPO_URL="${SKIM_REPO_URL:-https://github.com/ericzuo-ai/skim.git}"
REPO_REF="${SKIM_REPO_REF:-main}"
INSTALL_ROOT="${SKIM_INSTALL_ROOT:-${HOME}/.local/share/skim}"
REPO_DIR="${SKIM_REPO_DIR:-${INSTALL_ROOT}/repo}"
VENV_DIR="${SKIM_VENV_DIR:-${INSTALL_ROOT}/venv}"
BIN_DIR="${SKIM_BIN_DIR:-${HOME}/.local/bin}"
WRAPPER_PATH="${BIN_DIR}/skim"

echo ""
echo "${BOLD}skim${RESET} — token-optimized context routing for AI coding agents"
echo ""

if ! command -v git >/dev/null 2>&1; then
    error "git is required for the one-click installer. Install git first, then rerun this command."
fi

PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        version=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
        major=${version%%.*}
        minor=${version#*.}
        if [ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; }; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    error "Python 3.10+ is required. Install it first, then rerun the installer."
fi

info "Using $PYTHON ($($PYTHON --version 2>&1))"

mkdir -p "$INSTALL_ROOT" "$BIN_DIR"

if [ -d "$REPO_DIR/.git" ]; then
    info "Updating existing skim checkout..."
    git -C "$REPO_DIR" remote set-url origin "$REPO_URL"
    git -C "$REPO_DIR" fetch --depth 1 origin "$REPO_REF"
    git -C "$REPO_DIR" checkout -q FETCH_HEAD
else
    if [ -e "$REPO_DIR" ]; then
        rm -rf "$REPO_DIR"
    fi
    info "Cloning skim from $REPO_URL..."
    git clone --depth 1 --branch "$REPO_REF" "$REPO_URL" "$REPO_DIR"
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
    info "Creating managed virtual environment..."
    rm -rf "$VENV_DIR"
    "$PYTHON" -m venv "$VENV_DIR"
fi

info "Installing skim into the managed virtual environment..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel >/dev/null
"$VENV_DIR/bin/python" -m pip install --upgrade "$REPO_DIR" >/dev/null

cat > "$WRAPPER_PATH" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "$VENV_DIR/bin/skim" "\$@"
EOF
chmod 755 "$WRAPPER_PATH"

info "Installed $("$VENV_DIR/bin/skim" --version 2>/dev/null || echo 'skim')"
info "Managed repo: $REPO_DIR"
info "Managed venv: $VENV_DIR"
info "CLI wrapper: $WRAPPER_PATH"

case ":$PATH:" in
    *":$BIN_DIR:"*)
        info "$BIN_DIR is already on PATH."
        ;;
    *)
        warn "$BIN_DIR is not on PATH yet. Add this line to your shell profile:"
        printf "\n    export PATH=\"%s:\$PATH\"\n\n" "$BIN_DIR"
        ;;
esac

echo ""
info "Next step for Copilot: cd into your target repo, then run: skim init --agent copilot"
info "Next step for Claude Code or Cursor: skim init -g --agent claude|cursor"
echo ""

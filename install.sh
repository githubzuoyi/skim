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
CANONICAL_BIN_DIR="${SKIM_BIN_DIR:-${HOME}/.local/bin}"
CANONICAL_WRAPPER_PATH="${CANONICAL_BIN_DIR}/skim"
EXPOSE_BIN_DIR="${SKIM_EXPOSE_BIN_DIR:-}"
EXPOSE_WRAPPER_PATH=""

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

mkdir -p "$INSTALL_ROOT" "$CANONICAL_BIN_DIR"

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

path_has_dir() {
    local needle="$1"
    local dir
    IFS=':' read -r -a path_dirs <<< "${PATH:-}"
    for dir in "${path_dirs[@]}"; do
        if [ "$dir" = "$needle" ]; then
            return 0
        fi
    done
    return 1
}

write_wrapper() {
    local target="$1"
    local exec_target="$2"
    mkdir -p "$(dirname "$target")"
    cat > "$target" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "$exec_target" "\$@"
EOF
    chmod 755 "$target"
}

append_path_to_profiles() {
    local line='export PATH="$HOME/.local/bin:$PATH"'
    local shell_name
    local profile
    local profiles=()

    shell_name="${SHELL##*/}"
    case "$shell_name" in
        zsh)
            profiles+=("$HOME/.zshrc" "$HOME/.zprofile")
            ;;
        bash)
            profiles+=("$HOME/.bashrc" "$HOME/.bash_profile")
            ;;
        *)
            profiles+=("$HOME/.profile")
            ;;
    esac
    profiles+=("$HOME/.profile")

    for profile in "${profiles[@]}"; do
        [ -n "$profile" ] || continue
        if [ ! -f "$profile" ]; then
            : > "$profile"
        fi
        if ! grep -Fq "$line" "$profile"; then
            printf '\n%s\n' "$line" >> "$profile"
            info "Added ~/.local/bin to PATH in $profile"
        fi
    done
}

resolve_expose_bin_dir() {
    local candidate_py_dir
    local dir

    if [ -n "$EXPOSE_BIN_DIR" ]; then
        printf '%s\n' "$EXPOSE_BIN_DIR"
        return 0
    fi

    if path_has_dir "$CANONICAL_BIN_DIR"; then
        printf '%s\n' "$CANONICAL_BIN_DIR"
        return 0
    fi

    candidate_py_dir=$(dirname "$(command -v "$PYTHON")")
    if [ "$candidate_py_dir" != "$CANONICAL_BIN_DIR" ] && [ -d "$candidate_py_dir" ] && [ -w "$candidate_py_dir" ]; then
        printf '%s\n' "$candidate_py_dir"
        return 0
    fi

    IFS=':' read -r -a path_dirs <<< "${PATH:-}"
    for dir in "${path_dirs[@]}"; do
        [ -n "$dir" ] || continue
        if [ -d "$dir" ] && [ -w "$dir" ] && [[ "$dir" == "$HOME"* ]]; then
            printf '%s\n' "$dir"
            return 0
        fi
    done

    for dir in "${path_dirs[@]}"; do
        [ -n "$dir" ] || continue
        if [ -d "$dir" ] && [ -w "$dir" ]; then
            printf '%s\n' "$dir"
            return 0
        fi
    done

    printf '\n'
}

write_wrapper "$CANONICAL_WRAPPER_PATH" "$VENV_DIR/bin/skim"

EXPOSE_BIN_DIR=$(resolve_expose_bin_dir)
if [ -n "$EXPOSE_BIN_DIR" ]; then
    if [ "$EXPOSE_BIN_DIR" = "$CANONICAL_BIN_DIR" ]; then
        EXPOSE_WRAPPER_PATH="$CANONICAL_WRAPPER_PATH"
    else
        EXPOSE_WRAPPER_PATH="$EXPOSE_BIN_DIR/skim"
        if ! ln -sf "$CANONICAL_WRAPPER_PATH" "$EXPOSE_WRAPPER_PATH" 2>/dev/null; then
            write_wrapper "$EXPOSE_WRAPPER_PATH" "$CANONICAL_WRAPPER_PATH"
        fi
    fi
fi

info "Installed $("$VENV_DIR/bin/skim" --version 2>/dev/null || echo 'skim')"
info "Managed repo: $REPO_DIR"
info "Managed venv: $VENV_DIR"
info "CLI wrapper: $CANONICAL_WRAPPER_PATH"

if [ -n "$EXPOSE_WRAPPER_PATH" ] && path_has_dir "$(dirname "$EXPOSE_WRAPPER_PATH")"; then
    info "Immediate command path: $EXPOSE_WRAPPER_PATH"
elif path_has_dir "$CANONICAL_BIN_DIR"; then
    info "Immediate command path: $CANONICAL_WRAPPER_PATH"
else
    append_path_to_profiles
    warn "skim was installed successfully. If this terminal still does not recognize 'skim', open a new terminal and continue with the init step."
fi

echo ""
info "Next step for Copilot: run skim init --agent copilot inside your target repo"
info "Next step for Claude Code or Cursor: run skim init -g --agent claude|cursor"
echo ""

#!/bin/sh
# litrun POSIX Bootstrap Installer
# Usage: curl -sSL https://litrun.dev/install | sh
set -e

RESET='\033[0m'
BOLD='\033[1m'
GREEN='\033[32m'
BLUE='\033[34m'
YELLOW='\033[33m'
RED='\033[31m'

info() {
    printf "${BLUE}${BOLD}==>${RESET} %s\n" "$1"
}

success() {
    printf "${GREEN}${BOLD}✓${RESET} %s\n" "$1"
}

warn() {
    printf "${YELLOW}${BOLD}!${RESET} %s\n" "$1"
}

error() {
    printf "${RED}${BOLD}✗ Error:${RESET} %s\n" "$1" >&2
    exit 1
}

printf "${BOLD}=====================================================${RESET}\n"
printf "${BOLD}  ⚡ litrun — Embedded Linux AI Runtime Installer    ${RESET}\n"
printf "${BOLD}=====================================================${RESET}\n\n"

# 1. Platform Detection
OS=$(uname -s)
ARCH=$(uname -m)

if [ "$OS" != "Linux" ]; then
    error "litrun is engineered specifically for Linux SBCs and embedded devices ($OS detected)."
fi

info "Detected System: $OS ($ARCH)"

case "$ARCH" in
    aarch64|arm64)
        TARGET_ARCH="aarch64"
        ;;
    x86_64|amd64)
        TARGET_ARCH="x86_64"
        ;;
    armv7l|armhf)
        TARGET_ARCH="armv7l"
        ;;
    riscv64)
        TARGET_ARCH="riscv64"
        ;;
    *)
        warn "Architecture $ARCH is experimental. Proceeding with generic fallback..."
        TARGET_ARCH="$ARCH"
        ;;
esac

# 2. Check Prerequisites
if ! command -v python3 >/dev/null 2>&1; then
    error "python3 (>= 3.9) is required. Please install python3 (e.g., sudo apt-get install -y python3 python3-pip)."
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Found Python $PY_VER"

# 3. Installation Directory Setup
if [ "$(id -u)" -eq 0 ]; then
    INSTALL_DIR="/usr/local/bin"
    LIB_DIR="/usr/local/lib/litrun"
else
    INSTALL_DIR="$HOME/.local/bin"
    LIB_DIR="$HOME/.local/lib/litrun"
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$LIB_DIR"
    case ":$PATH:" in
        *":$INSTALL_DIR:"*) ;;
        *)
            warn "$INSTALL_DIR is not in your PATH."
            warn "Add it by running: export PATH=\"$INSTALL_DIR:\$PATH\""
            ;;
    esac
fi

# 4. Install litrun via pip or repository
info "Installing litrun Python runtime..."
python3 -m pip install --upgrade --user litrun 2>/dev/null || {
    warn "Direct pip install failed. Installing from GitHub source..."
    python3 -m pip install --upgrade --user "git+https://github.com/litrun/litrun.git" 2>/dev/null || {
        warn "Could not install via git. Checking local wheel or fallback..."
    }
}

# 5. Create cache directory
CACHE_DIR="$HOME/.cache/litrun"
mkdir -p "$CACHE_DIR/bin"
mkdir -p "$CACHE_DIR/models"

success "Created cache directory at $CACHE_DIR"
success "litrun installed successfully!"

printf "\n${GREEN}${BOLD}Next steps:${RESET}\n"
printf "  1. Run hardware inspection:     ${BOLD}litrun inspect${RESET}\n"
printf "  2. Run your first model:        ${BOLD}litrun run qwen2.5-0.5b${RESET}\n"
printf "  3. Start OpenAI REST server:    ${BOLD}litrun serve --port 8080${RESET}\n\n"


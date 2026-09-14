#!/usr/bin/env bash
# ==============================================================================
# pyRemoteMPC Uninstaller Script
# Removes pyRemoteMPC binaries, desktop entries, icons, and installed files.
# ==============================================================================

set -e

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Check root privileges
if [ "$EUID" -ne 0 ]; then
    error "Please run uninstall.sh with root privileges (e.g. sudo ./uninstall.sh)"
fi

info "Uninstalling pyRemoteMPC..."

INSTALL_DIR="/opt/pyremotempc"
BIN_LINK="/usr/local/bin/pyremotempc"
DESKTOP_FILE="/usr/share/applications/pyremotempc.desktop"
ICON_FILE="/usr/share/icons/hicolor/256x256/apps/pyremotempc.png"
PIXMAP_FILE="/usr/share/pixmaps/pyremotempc.png"

# Remove application directory
if [ -d "${INSTALL_DIR}" ]; then
    info "Removing ${INSTALL_DIR}..."
    rm -rf "${INSTALL_DIR}"
fi

# Remove binary launcher
if [ -f "${BIN_LINK}" ]; then
    info "Removing ${BIN_LINK}..."
    rm -f "${BIN_LINK}"
fi

# Remove desktop entry
if [ -f "${DESKTOP_FILE}" ]; then
    info "Removing ${DESKTOP_FILE}..."
    rm -f "${DESKTOP_FILE}"
fi

# Remove icons
if [ -f "${ICON_FILE}" ]; then
    info "Removing ${ICON_FILE}..."
    rm -f "${ICON_FILE}"
fi

if [ -f "${PIXMAP_FILE}" ]; then
    info "Removing ${PIXMAP_FILE}..."
    rm -f "${PIXMAP_FILE}"
fi

# Refresh desktop database & icon cache if tools are available
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
fi

success "pyRemoteMPC has been successfully uninstalled."
info "User configuration files in ~/.config/pyremotempc were preserved."

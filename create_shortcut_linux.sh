#!/usr/bin/env bash
# ==============================================================================
# Script to create a Linux Desktop entry for OpenMath
#
# The shortcut will:
# 1. Be placed in ~/.local/share/applications/j2k-calculator.desktop (Application Menu)
# 2. Be placed on ~/Desktop/j2k-calculator.desktop (if Desktop exists)
# 3. Always run the latest code directly from this repository
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$SCRIPT_DIR"
APP_NAME="OpenMath"
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_PATH="$REPO_DIR/resources/AppIcon.png"
LAUNCHER_PATH="$REPO_DIR/run.sh"

echo "Creating Linux desktop shortcuts for $APP_NAME..."
chmod +x "$LAUNCHER_PATH"

mkdir -p "$DESKTOP_DIR"

DESKTOP_FILE="$DESKTOP_DIR/openmath.desktop"

cat << EOF > "$DESKTOP_FILE"
[Desktop Entry]
Version=1.0
Type=Application
Name=$APP_NAME
GenericName=Computer Algebra System
Comment=OpenMath Desktop CAS Calculator
Exec="$LAUNCHER_PATH" %F
Icon=$ICON_PATH
Terminal=false
Categories=Education;Science;Math;Development;
StartupNotify=true
StartupWMClass=com.j2k.calculator
EOF

chmod +x "$DESKTOP_FILE"

# If ~/Desktop exists, copy shortcut there
if [ -d "$HOME/Desktop" ]; then
    cp "$DESKTOP_FILE" "$HOME/Desktop/j2k-calculator.desktop"
    chmod +x "$HOME/Desktop/j2k-calculator.desktop"
    echo "Created Desktop shortcut: $HOME/Desktop/j2k-calculator.desktop"
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

echo "Created application menu entry: $DESKTOP_FILE"
echo "Done!"
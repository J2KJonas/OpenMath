#!/bin/bash
# ==============================================================================
# Script to create a macOS Application shortcut for OpenMath
# 
# The shortcut will:
# 1. Be placed in ~/Applications/OpenMath.app (Spotlight & Dock ready)
# 2. Be placed on ~/Desktop/OpenMath.app (Double-click ready)
# 3. Always run the latest code directly from this repository
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$SCRIPT_DIR"

APP_NAME="OpenMath"
APP_BUNDLE_DEST_APPS="$HOME/Applications/${APP_NAME}.app"
APP_BUNDLE_DEST_DESKTOP="$HOME/Desktop/${APP_NAME}.app"

echo "Building macOS application shortcut for OpenMath..."
echo "Repository: $REPO_DIR"

# Ensure ~/Applications exists
mkdir -p "$HOME/Applications"

# Create App bundle in ~/Applications
rm -rf "$APP_BUNDLE_DEST_APPS"
mkdir -p "$APP_BUNDLE_DEST_APPS/Contents/MacOS"
mkdir -p "$APP_BUNDLE_DEST_APPS/Contents/Resources"

# Copy Icon if available
if [ -f "$REPO_DIR/resources/AppIcon.icns" ]; then
    cp "$REPO_DIR/resources/AppIcon.icns" "$APP_BUNDLE_DEST_APPS/Contents/Resources/AppIcon.icns"
fi

# Write Info.plist
cat << PLIST_EOF > "$APP_BUNDLE_DEST_APPS/Contents/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.j2k.calculator</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSArchitecturePriority</key>
    <array>
        <string>arm64</string>
        <string>x86_64</string>
    </array>
    <key>LSRequiresNativeExecution</key>
    <true/>
</dict>
</plist>
PLIST_EOF

# Write launcher script
cat << LAUNCHER_EOF > "$APP_BUNDLE_DEST_APPS/Contents/MacOS/launcher"
#!/bin/bash
export PATH="/Library/Frameworks/Python.framework/Versions/3.14/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:\$PATH"

# Always navigate to the repository directory
REPO_DIR="${REPO_DIR}"
cd "\$REPO_DIR" || exit 1

# Detect Python interpreter (support virtualenvs, Homebrew on Apple Silicon, and official frameworks)
PYTHON_EXEC=""
if [ -x "\$REPO_DIR/.venv/bin/python3" ]; then
    PYTHON_EXEC="\$REPO_DIR/.venv/bin/python3"
elif [ -x "\$REPO_DIR/venv/bin/python3" ]; then
    PYTHON_EXEC="\$REPO_DIR/venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_EXEC="\$(command -v python3)"
elif [ -x "/opt/homebrew/bin/python3" ]; then
    PYTHON_EXEC="/opt/homebrew/bin/python3"
elif [ -x "/usr/local/bin/python3" ]; then
    PYTHON_EXEC="/usr/local/bin/python3"
elif [ -x "/Library/Frameworks/Python.framework/Versions/Current/bin/python3" ]; then
    PYTHON_EXEC="/Library/Frameworks/Python.framework/Versions/Current/bin/python3"
else
    for py in /Library/Frameworks/Python.framework/Versions/3.*/bin/python3; do
        if [ -x "\$py" ]; then
            PYTHON_EXEC="\$py"
            break
        fi
    done
fi

if [ -z "\$PYTHON_EXEC" ] || [ ! -x "\$PYTHON_EXEC" ]; then
    osascript -e 'display alert "OpenMath Error" message "Python 3 could not be found. Please ensure Python 3.10+ is installed (e.g. via brew install python or python.org)." as critical' 2>/dev/null
    exit 1
fi

# Determine native architecture (e.g. arm64 on Apple Silicon)
NATIVE_ARCH="\$(uname -m)"
ERR_LOG="/tmp/openmath_error.log"

if [ "\$NATIVE_ARCH" = "arm64" ]; then
    /usr/bin/arch -arm64 "\$PYTHON_EXEC" main.py "\$@" 2> "\$ERR_LOG"
else
    "\$PYTHON_EXEC" main.py "\$@" 2> "\$ERR_LOG"
fi
EXIT_CODE=\$?

# If there was an error, show a friendly alert
if [ \$EXIT_CODE -ne 0 ] && [ -s "\$ERR_LOG" ]; then
    ERR_MSG=\$(tail -n 15 "\$ERR_LOG" | sed 's/"/\\"/g')
    osascript -e "display alert \"OpenMath Error\" message \"\$ERR_MSG\" as critical" 2>/dev/null
fi
exit \$EXIT_CODE
LAUNCHER_EOF

chmod +x "$APP_BUNDLE_DEST_APPS/Contents/MacOS/launcher"

# Touch to refresh macOS LaunchServices / Finder cache
touch "$APP_BUNDLE_DEST_APPS"

# Also create Desktop shortcut by copying the bundle
rm -rf "$APP_BUNDLE_DEST_DESKTOP"
cp -R "$APP_BUNDLE_DEST_APPS" "$APP_BUNDLE_DEST_DESKTOP"
touch "$APP_BUNDLE_DEST_DESKTOP"

echo "Created shortcut in ~/Applications/${APP_NAME}.app"
echo "Created shortcut on ~/Desktop/${APP_NAME}.app"

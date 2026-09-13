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
REPO_DIR="${REPO_DIR}"
cd "\$REPO_DIR" || exit 1

ERR_LOG="/tmp/openmath_error.log"

# Run universal launcher (handles virtual environment, dependencies & native architecture)
if [ -x "./run.sh" ]; then
    ./run.sh "\$@" 2> "\$ERR_LOG"
    EXIT_CODE=\$?
else
    /bin/bash "./run.sh" "\$@" 2> "\$ERR_LOG"
    EXIT_CODE=\$?
fi

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

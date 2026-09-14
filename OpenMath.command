#!/usr/bin/env bash
# ==============================================================================
# OpenMath - macOS Double-Clickable Launcher (.command)
# ==============================================================================
# You can double-click this file in macOS Finder to:
# 1. Automatically check requirements & dependencies
# 2. Install any missing packages into an isolated virtual environment
# 3. Launch the OpenMath desktop application
# ==============================================================================

# Set macOS Terminal window title
echo -n -e "\033]0;OpenMath Launcher\007" 2>/dev/null || true

# Determine script directory, with fallback in case copied to Desktop
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ ! -f "$SCRIPT_DIR/main.py" ]; then
    if [ -f "/Users/jacobel-omar/Documents/GitHub/openmath/main.py" ]; then
        SCRIPT_DIR="/Users/jacobel-omar/Documents/GitHub/openmath"
    fi
fi

cd "$SCRIPT_DIR" || {
    echo "[ERROR] Failed to navigate to OpenMath directory: $SCRIPT_DIR" >&2
    read -n 1 -s -r -p "Press any key to close..."
    exit 1
}

echo "=============================================================================="
echo "                      OpenMath CAS Calculator Launcher                        "
echo "=============================================================================="
echo "[INFO] Verifying environment and dependencies..."

# Run main launcher
if [ -x "./run.sh" ]; then
    ./run.sh "$@"
    EXIT_CODE=$?
elif [ -f "./run.sh" ]; then
    bash ./run.sh "$@"
    EXIT_CODE=$?
else
    echo "[ERROR] run.sh not found in $SCRIPT_DIR" >&2
    EXIT_CODE=1
fi

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "=============================================================================="
    echo "[ERROR] OpenMath exited with error code $EXIT_CODE."
    echo "=============================================================================="
    echo ""
    read -n 1 -s -r -p "Press any key to close this window..."
    echo ""
fi

exit $EXIT_CODE

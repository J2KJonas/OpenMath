#!/usr/bin/env bash
# ==============================================================================
# Launcher for OpenMath on macOS and Linux
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Check for local virtual environment
PYTHON_BIN=""
if [ -x "$SCRIPT_DIR/.venv/bin/python3" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python3"
elif [ -x "$SCRIPT_DIR/venv/bin/python3" ]; then
    PYTHON_BIN="$SCRIPT_DIR/venv/bin/python3"
elif [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
elif [ -x "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
elif [ -x "/opt/homebrew/bin/python3" ]; then
    PYTHON_BIN="/opt/homebrew/bin/python3"
elif [ -x "/usr/local/bin/python3" ]; then
    PYTHON_BIN="/usr/local/bin/python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "[ERROR] Python 3 was not found. Please install Python 3.10+." >&2
    exit 1
fi

# 2. Check dependencies (fast import check)
if ! "$PYTHON_BIN" -c "import PyQt6, sympy, matplotlib, numpy" >/dev/null 2>&1; then
    echo "[INFO] Missing required packages detected."
    echo "Installing dependencies from requirements.txt..."
    if ! "$PYTHON_BIN" -m pip install -r "$SCRIPT_DIR/requirements.txt"; then
        echo "[ERROR] Failed to install required packages." >&2
        echo "Please run: pip install -r requirements.txt" >&2
        exit 1
    fi
    echo "[SUCCESS] Dependencies installed successfully!"
fi

# 3. Native execution on Apple Silicon (macOS arm64) if applicable
if [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then
    exec /usr/bin/arch -arm64 "$PYTHON_BIN" main.py "$@"
else
    exec "$PYTHON_BIN" main.py "$@"
fi
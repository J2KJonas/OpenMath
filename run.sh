#!/usr/bin/env bash
# ==============================================================================
# Launcher for OpenMath on macOS and Linux
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Check for existing local virtual environment
PYTHON_BIN=""
if [ -x "$SCRIPT_DIR/.venv/bin/python3" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python3"
elif [ -x "$SCRIPT_DIR/venv/bin/python3" ]; then
    PYTHON_BIN="$SCRIPT_DIR/venv/bin/python3"
elif [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
elif [ -x "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
fi

# If no local venv, check if system Python already has dependencies
if [ -z "$PYTHON_BIN" ]; then
    SYS_PYTHON=""
    if command -v python3 >/dev/null 2>&1; then
        SYS_PYTHON="$(command -v python3)"
    elif [ -x "/opt/homebrew/bin/python3" ]; then
        SYS_PYTHON="/opt/homebrew/bin/python3"
    elif [ -x "/usr/local/bin/python3" ]; then
        SYS_PYTHON="/usr/local/bin/python3"
    elif command -v python >/dev/null 2>&1; then
        SYS_PYTHON="$(command -v python)"
    fi

    if [ -z "$SYS_PYTHON" ]; then
        echo "[ERROR] Python 3 was not found. Please install Python 3.10+." >&2
        exit 1
    fi

    # Check if system python already has the required packages
    if "$SYS_PYTHON" -c "import PyQt6, sympy, matplotlib, numpy" >/dev/null 2>&1; then
        PYTHON_BIN="$SYS_PYTHON"
    else
        # On modern Linux (Zorin OS, Ubuntu 24.04, Debian), PEP 668 blocks pip install without venv.
        # Automatically initialize a local .venv
        echo "[INFO] Creating virtual environment in .venv..."
        if ! "$SYS_PYTHON" -m venv "$SCRIPT_DIR/.venv"; then
            echo "[ERROR] Failed to create virtual environment (.venv)." >&2
            echo "On Zorin OS / Ubuntu / Debian, please install the python3-venv package:" >&2
            echo "    sudo apt update && sudo apt install -y python3-venv python3-pip" >&2
            exit 1
        fi
        PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python3"
    fi
fi

# 2. Check dependencies (fast import check)
if ! "$PYTHON_BIN" -c "import PyQt6, sympy, matplotlib, numpy" >/dev/null 2>&1; then
    echo "[INFO] Missing required packages detected."
    echo "Installing dependencies from requirements.txt..."
    if ! "$PYTHON_BIN" -m pip install --upgrade pip >/dev/null 2>&1; then
        true
    fi
    if ! "$PYTHON_BIN" -m pip install -r "$SCRIPT_DIR/requirements.txt"; then
        echo "[ERROR] Failed to install required packages." >&2
        echo "Please run: $PYTHON_BIN -m pip install -r requirements.txt" >&2
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
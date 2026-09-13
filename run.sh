#!/usr/bin/env bash
# ==============================================================================
# Universal Launcher for OpenMath on macOS and Linux
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure PATH includes common Python locations on macOS and Linux
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/local/sbin:/Library/Frameworks/Python.framework/Versions/Current/bin:$PATH"
for p in /Library/Frameworks/Python.framework/Versions/3.*/bin; do
    if [ -d "$p" ]; then
        PATH="$p:$PATH"
    fi
done
export PATH

# 1. Look for an existing local virtual environment
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

# 2. If no virtual environment is found, locate system Python 3 (3.10+)
if [ -z "$PYTHON_BIN" ]; then
    PYTHON_SYSTEM=""
    for cand in python3 \
                /opt/homebrew/bin/python3 \
                /usr/local/bin/python3 \
                /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
                /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
                /Library/Frameworks/Python.framework/Versions/3.10/bin/python3 \
                /usr/bin/python3 \
                python; do
        if command -v "$cand" >/dev/null 2>&1; then
            res="$(command -v "$cand")"
            if "$res" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
                PYTHON_SYSTEM="$res"
                break
            fi
        elif [ -x "$cand" ]; then
            if "$cand" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
                PYTHON_SYSTEM="$cand"
                break
            fi
        fi
    done

    if [ -z "$PYTHON_SYSTEM" ]; then
        echo "[ERROR] Python 3 (version 3.10 or higher) was not found." >&2
        echo "Please install Python from https://www.python.org or via Homebrew ('brew install python')." >&2
        exit 1
    fi

    # Check if system Python already has all required packages
    if "$PYTHON_SYSTEM" -c "import PyQt6, sympy, matplotlib, numpy" >/dev/null 2>&1; then
        PYTHON_BIN="$PYTHON_SYSTEM"
    else
        # Missing dependencies. Because modern Python (PEP 668) prevents direct system pip install,
        # create a local virtual environment in .venv.
        echo "[INFO] Creating virtual environment (.venv) for OpenMath..."
        if ! "$PYTHON_SYSTEM" -m venv "$SCRIPT_DIR/.venv"; then
            echo "[ERROR] Failed to create virtual environment." >&2
            exit 1
        fi
        PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python3"
    fi
fi

# 3. Check dependencies in selected Python environment
if ! "$PYTHON_BIN" -c "import PyQt6, sympy, matplotlib, numpy" >/dev/null 2>&1; then
    echo "[INFO] Missing required packages detected."
    echo "[INFO] Installing dependencies from requirements.txt..."
    "$PYTHON_BIN" -m pip install --quiet --upgrade pip 2>/dev/null || true
    if ! "$PYTHON_BIN" -m pip install -r "$SCRIPT_DIR/requirements.txt"; then
        echo "[ERROR] Failed to install required packages." >&2
        echo "Please run: $PYTHON_BIN -m pip install -r requirements.txt" >&2
        exit 1
    fi
    echo "[SUCCESS] Dependencies installed successfully!"
fi

# 4. Native execution on Apple Silicon (macOS arm64) if applicable
if [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then
    /usr/bin/arch -arm64 "$PYTHON_BIN" main.py "$@"
else
    "$PYTHON_BIN" main.py "$@"
fi
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "[ERROR] OpenMath exited with code $EXIT_CODE." >&2
    exit $EXIT_CODE
fi
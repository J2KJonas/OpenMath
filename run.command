#!/usr/bin/env bash
# ==============================================================================
# OpenMath - macOS Double-Clickable Launcher (.command)
# ==============================================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/OpenMath.command" "$@"

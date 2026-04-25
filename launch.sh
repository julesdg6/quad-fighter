#!/usr/bin/env bash
# Quad Fighter – Steam launcher
#
# Add Quad Fighter as a non-Steam game and point the "Launch Options" to this
# script.  Steam will execute it directly, so make sure it is marked executable:
#
#   chmod +x launch.sh
#
# The script resolves its own directory so it works regardless of the working
# directory Steam happens to use.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Prefer a local virtual-environment when one exists next to the game files,
# then fall back to the system Python 3 / Python interpreter.
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
elif [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/venv/bin/python"
else
    PYTHON="$(command -v python3 2>/dev/null || command -v python 2>/dev/null)"
fi

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3 not found. Please install Python 3 and run:" >&2
    echo "  pip install -r requirements.txt" >&2
    exit 1
fi

exec "$PYTHON" main.py "$@"

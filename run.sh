#!/usr/bin/env bash
# Script de inicio rápido para pyRemoteMPC

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="/home/adrian/.gemini/antigravity/scratch/mRemoteNG/.venv/bin/python3"

if [ -f "$VENV_PYTHON" ]; then
    PYTHON_CMD="$VENV_PYTHON"
else
    PYTHON_CMD="python3"
fi

cd "$SCRIPT_DIR"
exec "$PYTHON_CMD" -m pyremotempc.app "$@"

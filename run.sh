#!/usr/bin/env bash
# Script de inicio rápido para pyRemoteMPC

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${SCRIPT_DIR}/.venv/bin/python3" ]; then
    PYTHON_CMD="${SCRIPT_DIR}/.venv/bin/python3"
elif [ -f "/opt/pyremotempc/.venv/bin/python3" ]; then
    PYTHON_CMD="/opt/pyremotempc/.venv/bin/python3"
else
    PYTHON_CMD="python3"
fi

cd "$SCRIPT_DIR"
exec "$PYTHON_CMD" -m pyremotempc.app "$@"

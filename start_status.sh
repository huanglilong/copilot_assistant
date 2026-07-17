#!/usr/bin/env bash
# Start Copilot CLI Status Monitor
# Access from other devices: http://copilot.local:8585
# Access locally: http://localhost:8585

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Setting up virtual environment..."
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    pip install --quiet flask zeroconf
else
    source "$VENV_DIR/bin/activate"
fi

echo "🤖 Starting Copilot CLI Status Monitor..."
echo "   Local:   http://localhost:8585"
echo "   Network: http://copilot.$(whoami).$(hostname -s).local:8585"
echo ""

python3 -m copilot_status "$@"

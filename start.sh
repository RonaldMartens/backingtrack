#!/bin/bash
# Start de BackingTrack-server. Bereikbaar op deze Mac én op je iPhone (zelfde wifi).
set -euo pipefail
cd "$(dirname "$0")"
VENV="$HOME/.venvs/backingtrack"
PORT="${PORT:-8000}"

if [ ! -x "$VENV/bin/uvicorn" ]; then
  echo "Virtuele omgeving niet gevonden – draai eerst ./install.sh"
  exit 1
fi

HOST_NAME="$(scutil --get LocalHostName 2>/dev/null || hostname -s)"
echo "Mac:     http://localhost:$PORT"
echo "iPhone:  http://$HOST_NAME.local:$PORT   (zelfde wifi-netwerk)"
echo "API-docs: http://localhost:$PORT/docs"
echo

if [ -z "${BT_NO_BROWSER:-}" ]; then
  ( sleep 1.5 && open "http://localhost:$PORT" ) >/dev/null 2>&1 &
fi
exec "$VENV/bin/uvicorn" app.main:app --host 0.0.0.0 --port "$PORT"

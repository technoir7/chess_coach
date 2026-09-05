#!/bin/bash

# Start the Chess Coach server. Ctrl+C stops it.

# Change to script directory
cd "$(dirname "$0")"

# Load environment variables from .env file
if [ -f .env ]; then
  # Sourcing .env is often more reliable than export xargs
  set -a
  source .env
  set +a
fi

# Set defaults for engine paths if not in .env
export LEELA_ENGINE_PATH="${LEELA_ENGINE_PATH:-/opt/homebrew/bin/lc0}"
export LEELA_WEIGHTS_PATH="${LEELA_WEIGHTS_PATH:-./maia-1500.pb.gz}"

# Clear the port if an earlier run is still holding it, so restarting never
# fails with "address already in use" or silently serves stale code.
if lsof -ti:8000 >/dev/null 2>&1; then
  echo "Port 8000 still in use by an earlier run - stopping it first."
  lsof -ti:8000 | xargs kill -9 2>/dev/null
  sleep 1
fi

echo "Chess Coach: http://localhost:8000   (Ctrl+C to stop)"

# exec replaces this script with the server rather than running it as a child,
# so there is only ever one process. Without it, killing the script leaves the
# server orphaned and still holding the port.
exec ./env/bin/python api/main.py

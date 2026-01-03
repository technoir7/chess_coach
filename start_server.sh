#!/bin/bash

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

# Start the FastAPI server
./env/bin/python api/main.py

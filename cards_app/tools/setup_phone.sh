#!/bin/sh
# One-time setup: serve the app to my iPhone over Tailscale.
#
# 1. Builds the app from the latest deck.
# 2. Installs a background service (launchd) that serves cards_app/dist on
#    127.0.0.1:8767, only on this Mac, restarted automatically.
# 3. Tells Tailscale to pass https://<this mac>.<tailnet>.ts.net:8444 to it,
#    tailnet only. Other ports Tailscale serves are left alone.
#    The same server runs tools/update.py when the app's "Get new games"
#    button asks.
#
# Undo: launchctl bootout gui/$(id -u)/local.chesscards.app-server
#       rm ~/Library/LaunchAgents/local.chesscards.app-server.plist
#       tailscale serve --https=8444 off
set -eu
cd "$(dirname "$0")/.."
test -s tools/lichess_user || { echo "write your Lichess username to cards_app/tools/lichess_user" >&2; exit 1; }

pnpm deck && pnpm build

PLIST="$HOME/Library/LaunchAgents/local.chesscards.app-server.plist"
# launchd starts with a bare PATH, so the service gets this shell's: updates need
# claude, stockfish, node and pnpm. PYTHON=... picks the interpreter.
sed -e "s|__PYTHON__|${PYTHON:-$(command -v python3)}|" -e "s|__APP__|$PWD|g" -e "s|__PATH__|$PATH|" \
  tools/local.chesscards.app-server.plist.template > "$PLIST"
launchctl bootout "gui/$(id -u)/local.chesscards.app-server" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

tailscale serve --bg --https=8444 http://127.0.0.1:8767

sleep 1
curl -fsS -o /dev/null http://127.0.0.1:8767/ && echo "server: running"
HOST=$(tailscale status --json | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')
echo
echo "On your iPhone, open in Safari:  https://$HOST:8444"
echo "Then Share → Add to Home Screen."

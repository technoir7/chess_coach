# Chess cards

A phone app for the cards `make_cards.py` makes from my Lichess games. Each
card asks for a move: the opponent's threat, their reply to the move I was
about to play, or my own best move. I play it on the board, then step
through the answer's line and read the commentary. Spaced repetition (FSRS)
brings cards back; missed ones come back soon.

Vite + React + TypeScript, a home-screen web app
that works offline, progress kept on the phone (with a backup button).
`chess.js` handles the move rules.

## Common jobs

**New games**: press "Get new games" in the app's menu. The Mac
(`tools/serve_app.py`) runs `tools/update.py`: it downloads new games, makes
their cards and commentary, and rebuilds the app, which the phone then
loads. Progress carries over. If Claude's usage limit is hit, the new cards
come without commentary and the next update adds it. Log:
`tools/update.log`. Without the phone: `python3 tools/update.py`.

**Tests**: `pnpm test`, and `cd tools && /usr/bin/python3 -m unittest`.

**Try it locally**: `pnpm deck && pnpm build && pnpm preview`.

## On my phone

Served over Tailscale only (tailnet-only HTTPS, no login, nothing public).
`tools/serve_app.py` serves `dist/` on 127.0.0.1:8767 as a background
service, and `tailscale serve --https=8444` passes the phone's requests to
it. One-time setup: write your Lichess username to `tools/lichess_user` (one
line; it stays out of git), then run `tools/setup_phone.sh`.

The deck (`src/generated/deck.json`) names my games, so like `out/` it
stays out of git.

# Chess Coach

A chess coach in which Stockfish and Leela establish the facts about a position and a language model only puts them into words. What the model says about moves is checked against the board before the player sees it.

## The problem

Asked to explain a position, an LLM will often name illegal moves, invent variations, or call a quiet move a check, in fluent prose a learning player can't fact-check. Chess is a good test case because each of those claims can be checked mechanically.

## How it works

1. **Engines.** Stockfish searches to depth 15 and returns its top three lines. Leela (lc0, optional) runs the bundled Maia-1500 network for 100 nodes; the model gets its reading in words, as how a club player would see the position, not as a second evaluation.
2. **Facts.** Engine output goes into a `TruthPacket` (`src/models.py`): evaluation, the top lines as 8 plies of SAN, threats read off the board (hanging pieces, pieces attacked by something cheaper, check), and game phase. `line_facts.py` replays each line and states its checks, captures and material change. Packets are cached per position, so follow-up questions see the same lines.
3. **Gate.** `gate.py` decides whether to give in-game advice: only if the player lost more than 100cp or the game phase changed, and never if the evaluation moved less than 20cp or nothing is under threat. Explanations and chat are on demand.
4. **Narration.** The prompt (`prompts.py`) holds the packet, legal moves, move history and opening name, and tells the model to quote engine lines rather than calculate. `verifier.py` rejects a response that names a move legal for neither side and absent from the engine lines, gives a sequence that isn't a contiguous quote of an engine line, or misstates a check, an exchange or an attack. A rejected response is retried once; after that, advice is dropped and explanations fall back to an engine-only summary.

The model is set in `system_config.yaml` (default `gemma3:12b` via local Ollama). On failure `llm.py` falls back to Gemini Flash, then other local Ollama models. The web UI (FastAPI) lets you play White against Stockfish at a chosen strength and style, switch models, ask questions, and export the annotated game as Markdown.

## Setup

Requires Python 3.10+ (tested on 3.13), Stockfish on `PATH`, optionally lc0, and either Ollama with `gemma3:12b` or a Google API key.

```bash
python -m venv env
env/bin/pip install -r requirements_backup.txt
cp .env.template .env   # set GOOGLE_API_KEY; LEELA_ENGINE_PATH defaults to /opt/homebrew/bin/lc0
./start_server.sh       # http://localhost:8000
```

`start_server.sh` expects the virtualenv at `./env` and kills whatever is on port 8000. A terminal version runs with `env/bin/python main.py` and reads the Stockfish path from `CHESS_ENGINE_PATH`.

## Tests

```bash
env/bin/pip install pytest
env/bin/python -m pytest tests
```

107 tests, mostly with stand-in engines. `test_full_loop.py` starts the real Stockfish and is a smoke test with no assertions.

## Limitations

- The verifier is pattern-based. It can't check strategic claims, and skips bare pawn moves in prose ("e4") because they look like square names.
- The gate's chaos-score and null-move triggers never fire: nothing computes those values yet.
- Game phase comes from move count alone; threat detection looks one move deep.
- The opening book has names and ECO codes, no game statistics.
- The player is always White, and games live in memory.
- Some `system_config.yaml` sections (coaching modes, plan critique, meta-coaching) are parsed but unused.

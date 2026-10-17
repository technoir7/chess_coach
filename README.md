# Chess Coach

A chess coach in which Stockfish and Leela establish the facts about a position and a language model only puts them into words. What the model says about moves is checked against the board before the player sees it.

## Measured

How often an explanation says something false about the position, labelled blind by reviewers who checked every claim against the board ([method and data](evals/README.md)):

| | Wrong, as the model wrote it | Wrong, as the player saw it | Fell back to engine-only summary |
|---|---:|---:|---:|
| Round 1, `gemma3:12b` | 72 of 100 | 68 of 100 | 4 |
| Round 1, Claude Sonnet | 33 of 100 | 32 of 100 | 7 |
| Round 2, Claude Sonnet, fixes below, fresh positions | 21 of 100 | 20 of 100 | 1 |

What this showed:

- **The model mattered most.** Gemma got the evaluation's size wrong in 40 answers and invented trades in 35. Claude made half as many mistakes in a sixth of the time, so it is now the default.
- **The checker caught little and blocked good answers.** In round 1 it rejected 11 of Gemma's 72 wrong answers and 4 of Claude's 33. Of the 30 Claude answers it rejected, 25 were correct: it read "White's Nf3" as a move and "no queens are exchanged" as a claim that they are. Those false alarms are fixed, and in round 2 it rejected 4 answers.
- **The facts the model was given misled it.** "White ends up 3 pawns ahead" meant the gain over a line, and models read it as the balance; promotions weren't counted; lines that stop before a recapture looked like won material. Each line's facts now state the gain and the balance separately, count promotions, and say when a line stops mid-exchange.
- **The improvement is likely but not proven.** 33 to 21 wrong could arise by chance about 8% of the time. Reviewers differ in strictness, so 30 answers from each round were also labelled together by the same two reviewers: 12 wrong against 6.

The commonest remaining mistake is a wrong claim about what a piece attacks, defends or pins, which the checker does not cover.

## The problem

Asked to explain a position, an LLM will often name illegal moves, invent variations, or call a quiet move a check, in fluent prose a learning player can't fact-check. Chess is a good test case because each of those claims can be checked mechanically.

## How it works

1. **Engines.** Stockfish searches to depth 15 and returns its top three lines. Leela (lc0, optional) runs the bundled Maia-1500 network for 100 nodes; the model gets its reading in words, as how a club player would see the position, not as a second evaluation.
2. **Facts.** Engine output goes into a `TruthPacket` (`src/models.py`): evaluation, the top lines as 8 plies of SAN, threats read off the board (hanging pieces, pieces attacked by something cheaper, check), and game phase. `line_facts.py` replays each line and states its checks, captures and material change. Packets are cached per position, so follow-up questions see the same lines.
3. **Gate.** `gate.py` decides whether to give in-game advice: only if the player lost more than 100cp or the game phase changed, and never if the evaluation moved less than 20cp or nothing is under threat. Explanations and chat are on demand.
4. **Narration.** The prompt (`prompts.py`) holds the packet, legal moves, move history and opening name, and tells the model to quote engine lines rather than calculate. `verifier.py` rejects a response that names a move legal for neither side and absent from the engine lines and the game so far, gives a sequence that isn't a contiguous quote of an engine line or of the game, or misstates a check, an exchange or an attack. A rejected response is retried once; after that, advice is dropped and explanations fall back to an engine-only summary.

The model is set in `system_config.yaml` (default `claude-sonnet`, run through the `claude` command on your own Claude login, so no API key is needed). Any local Ollama model and Gemini can be picked in the UI instead. On failure `llm.py` falls back to Gemini Flash, then local Ollama models. The web UI (FastAPI) lets you play White against Stockfish at a chosen strength and style, switch models, ask questions, and export the annotated game as Markdown.

## Setup

Requires Python 3.10+ (tested on 3.13), Stockfish on `PATH`, optionally lc0, and one of: the `claude` command logged in to a Claude subscription, Ollama with a local model, or a Google API key.

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

139 tests, mostly with stand-in engines. `test_full_loop.py` starts the real Stockfish and is a smoke test with no assertions.

## Limitations

- The verifier is pattern-based. It can't check strategic claims or what a piece attacks or defends in prose, and skips bare pawn moves ("e4") because they look like square names. Measured, it catches only a small share of wrong answers (see above).
- The gate's chaos-score and null-move triggers never fire: nothing computes those values yet.
- Game phase comes from move count alone; threat detection looks one move deep.
- The opening book has names and ECO codes, no game statistics.
- The player is always White, and games live in memory.
- Some `system_config.yaml` sections (coaching modes, plan critique, meta-coaching) are parsed but unused.

# ♟️ Chess Coach

## Logic-Gated, Verifier-Bound AI Explanations in a Closed-World Decision System

> **A working reference implementation of truth-invariant, logic-gated LLM explanations grounded in external verification.**

Berkeley Chaos is a technical demonstration of **Truth-Invariant AI**: an architectural approach to eliminating hallucinations in complex explanations by strictly decoupling **calculation**, **verification**, and **narration**.

Rather than allowing a language model to reason freely, Berkeley Chaos binds all explanations to externally verified ground truth and enforces silence unless a genuine epistemic event has occurred.

Chess is used as the demonstration domain—not as the product.

---

## Why Chess?

Chess is a closed-world, adversarial system with:

* Perfectly formalized rules
* Immediate falsifiability
* A well-defined external oracle (engines)
* Zero tolerance for illegal or invented actions

These properties make chess an ideal **stress test for AI explanations**.
Any system that hallucinates in chess—where truth is precise and verifiable—will fail catastrophically in open-ended, high-stakes domains.

---

## Architecture: The Truth Invariance Loop

Berkeley Chaos enforces epistemic discipline through a three-layer architecture in which authority flows in only one direction.

### 1. Ground Truth Layer (Verification Engines)

This layer owns **all truth**.

* **Calculation Engine (Stockfish 17)**
  High-depth tactical search and centipawn evaluation.

* **Intuition Engine (Leela Chess Zero)**
  Neural-network–based positional evaluation capturing long-term structural pressure and instability.

* **Truth Packet Generation**
  The engines produce a structured, inspectable **Truth Packet** containing:

  * FEN position
  * Legal move subsets (SAN)
  * Evaluation deltas and inflection points
  * Tactical threats and irreversible commitments

The Truth Packet is finite, auditable, and immutable.

---

### 2. Logic Gate (Deterministic Middleware)

Before any language model is invoked, a strict logic gate determines whether explanation is epistemically justified.

* **Event-Triggered Cognition**
  Explanations are permitted only when a detectable epistemic event occurs:

  * Evaluation collapse (e.g. >50cp swing)
  * Phase transitions (opening → middlegame → endgame)
  * Volatility spikes where candidate moves diverge sharply

* **Silence by Default**
  If no trigger is hit, the system withholds explanation entirely.
  This prevents autopilot learning, explanation spam, and false authority.

---

### 3. Verifier-Bound Narrator (LLM)

The language model functions strictly as a **translator**, never as a reasoner.

* **No Independent Calculation**
  The LLM is explicitly forbidden from generating variations, tactics, or evaluations.

* **Truth-Packet-Only Context**
  All narrative output must reference data present in the Truth Packet.

* **Illegal Move Elimination**
  A pre-verified list of legal SAN moves is injected into context, removing a common LLM failure mode: suggesting impossible actions.

The result is explanation without invention.

---

## Key Technical Capabilities

* **Real-Time Inflection Detection**
  Automatically identifies irreversible decisions (pawn breaks, exchange sacrifices, structural commitments) using engine-verified deltas.

* **Adversarial Plan Critique**
  Users may submit their own strategic plans.
  The system evaluates claims by matching them against engine-verified contradictions rather than affirming intent.

* **Failure-Resilient Model Orchestration**
  Multi-model fallback across Gemini 2.0 / 2.5 and local Ollama models ensures uninterrupted real-time operation.

* **Decision-Focused Interface**
  A low-latency, glassmorphic UI designed to support reasoning—not dependency—paired with Markdown-annotated exports for post-hoc analysis.

---

## Failure Modes This Architecture Eliminates

Berkeley Chaos is explicitly designed to remove common AI explanation pathologies at the **architectural** level, not via prompt tuning:

* Illegal move hallucination
* Post-hoc rationalization
* Over-explanation in stable states
* Confident but unfalsifiable narratives
* Tactical invention disconnected from verification

When explanation is not warranted, the system remains silent.

---

## Stack & Implementation

* **Core Logic**: Python 3.10+ (FastAPI)
* **Verification Engines**: Stockfish 17 (UCI), Leela Chess Zero
* **Narrative Layer**: Google Gemini (via `google-genai`)
* **State Management**: Asynchronous game orchestration with structured Markdown export

---

## Deployment

### Requirements

* Stockfish (installed and in PATH)
* Leela Chess Zero (optional, for positional evaluation)
* Python 3.10+

### Configuration

```env
GOOGLE_API_KEY=your_gemini_key
CHESS_ENGINE_PATH=/usr/local/bin/stockfish
```

### Execution

```bash
pip install -r requirements.txt
./start_server.sh
```

The interface will be available at `http://localhost:8000`.

---

## Analysis & Scope

Berkeley Chaos serves as a reference implementation for **high-stakes AI explanation systems**, where hallucination is not merely misleading but unacceptable.

Chess exposes a core failure mode of contemporary AI: explanations that are fluent, persuasive, and wrong.
This project demonstrates one viable alternative—systems where explanation is subordinate to verification, and restraint is a feature rather than a limitation.

---

If you want, next we can:

* Derive a **generalized “Truth-Packet” pattern** from this
* Write the accompanying essay that turns this into intellectual leverage
* Design a one-page architecture diagram suitable for non-chess audiences

Just say which direction you want to push.
# chess_coach

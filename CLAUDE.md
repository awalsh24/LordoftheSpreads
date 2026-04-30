# CLAUDE.md — Project Context

> This file is read automatically by Claude Code when the project folder is opened.
> Keep it current. Every session that produces something meaningful adds a line to the Session Log.

---

## Project: Agent-Augmented Market-Making Bot on Decentralized Exchanges

### One-line summary
Build a traditional quantitative market-making bot, then layer an LLM agent on top that reads order book state and context to decide *which* algorithm to run *when* — replacing the human operator who would normally tune parameters by hand.

### Why this is interesting
- Decentralized perp exchanges (Hyperliquid, Pacifica, Extended) are on-chain, so other market makers' positions and order flow are publicly observable. We can study what works before committing capital.
- The same venues now list tokenized equities, commodities (oil, wheat), and prediction markets. Single connector, many markets.
- Agent layer is the differentiator. Classical market-making algos (Avellaneda-Stoikov, Glosten-Milgrom, basic spread-quoting) are well documented but brittle — they need a human to switch regimes. An LLM that reads the book and the news can plausibly do that switching.

### Why NOT certain venues
- **Lighter** — incumbent paid major retail brokers for market-maker flow. Capital and flow advantage too large to compete with directly. Studied but not targeted.
- **Centralized exchanges** — possible but lose the public order-flow visibility that makes the research tractable.

---

## Current State

**Phase:** Research complete for v1 scoping. Code: not started. First coding task is well-defined (data recorder).

**Language:** Python 3.11. Pinned in `.python-version`. Dependencies in `pyproject.toml`.

**Primary venue:** Hyperliquid (decision documented in `research/other_dexes.md`).
**Secondary venue (research only, no code yet):** Extended.

**Operator:** [your name/handle here — fill in]

**Collaborator context:** Friend is active in the Hummingbot community (open-source algo trading framework). Potential source of expertise.

---

## End-Goal Architecture (target, not current state)

```
┌─────────────────────────────────────────────────────────┐
│  LLM AGENT (Claude / orchestrator)                      │
│  - reads order book snapshots + features                │
│  - reads news / on-chain signals                        │
│  - selects which strategy module to run                 │
│  - tunes parameters (spread, inventory limits, etc.)    │
│  - monitors PnL and risk, can halt                      │
│  - runs every few minutes, NOT in per-quote loop        │
└────────────┬────────────────────────────────────────────┘
             │  small typed commands
             ▼
┌─────────────────────────────────────────────────────────┐
│  STRATEGY LAYER (Python, fast, deterministic)           │
│  - module per algorithm (AS, inventory-skewed, naive)   │
│  - exposes uniform interface to agent                   │
│  - emits quotes, cancels, hedges                        │
│  - hard risk limits enforced regardless of agent input  │
└────────────┬────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────┐
│  EXCHANGE CONNECTOR                                     │
│  - Hyperliquid via official Python SDK or Hummingbot    │
│  - decision deferred until a one-day eval (see          │
│    research/hummingbot.md)                              │
└─────────────────────────────────────────────────────────┘

Plus: continuous DATA RECORDER writing to parquet files
(this is the first thing we build).
```

---

## Conventions

- **Python only.** Version 3.11, pinned in `.python-version`.
- **Style:** type hints everywhere, ruff + mypy clean, no notebooks for production code (notebooks fine for exploration in `code/notebooks/`).
- **Async:** the connector and recorder are async. Strategy code can be sync internally.
- **Secrets:** never committed. Use `.env` (gitignored). See `.env.example`.
- **Config:** Pydantic settings classes loaded from env vars, not YAML.
- **Research notes:** every topic gets its own file in `research/`. Source links go inline.
- **Backtest before live:** no strategy goes to mainnet without a documented backtest.
- **Recorder runs first, always.** Data accumulates while we do other things.

---

## Open Questions (live list — update as we go)

- Hummingbot connector vs raw SDK — resolve via one-day eval (see `research/hummingbot.md`)
- Which Hyperliquid markets have enough volume but not so much MM competition that we get steamrolled? Resolve by inspecting recorded data after ~2 weeks of recording.
- What does the agent layer actually *see*? Pre-computed features? Charts as images? Start with structured features.
- Capital floor — what's the smallest meaningful size to deploy? Operator's call. Suggested $200-500 budget for "tuition" on Phase 3 of the live rollout.
- Regulatory posture — see `research/regulatory_notes.md`. Operator must read before any mainnet deposit.

---

# 🔑 Next Steps for Claude Code

> **This is the section to read first when opening this project in Claude Code.**
> The research phase is done. The first coding session has a clearly defined task list.
> Tackle these in order. Don't skip ahead — each step builds on the previous.

## Step 0: Get oriented (5 minutes)

1. Read this entire `CLAUDE.md` if you haven't.
2. Skim `research/index.md` to know what's where. You don't need to read every research file unless it's relevant to the current task.
3. Confirm you understand: **primary target is Hyperliquid, language is Python 3.11, first coding task is the data recorder.**

## Step 1: Environment setup

Walk the operator through setting up a working environment:

1. Verify Python 3.11 is available. If pyenv is installed, `pyenv install 3.11` and pyenv picks up `.python-version`.
2. Create a virtualenv: `python3.11 -m venv .venv` (or `uv venv` if uv is available).
3. Activate it.
4. Install: `pip install -e ".[dev]"` (or `uv pip install -e ".[dev]"`).
5. Copy `.env.example` to `.env` and fill in `ANTHROPIC_API_KEY` at minimum. Hyperliquid keys not needed yet for the recorder (it uses public read-only WebSocket data).
6. Verify: `python -c "import hyperliquid; import anthropic; print('ok')"`.

If any of this fails, debug it before moving on. The recorder uses `hyperliquid` and `pyarrow`; both must import cleanly.

`SETUP.md` has the same instructions in operator-friendly form.

## Step 2: Build the data recorder

Spec is in `code/data_recorder/README.md`. Summary:

- Single Python script (`code/data_recorder/recorder.py`)
- Reads `RECORD_COINS` and `DATA_DIR` from `.env`
- Connects to Hyperliquid mainnet WebSocket (`wss://api.hyperliquid.xyz/ws`) — read-only public data, no auth needed
- Subscribes to `l2Book` and `trades` for each coin
- Writes to parquet files: `data/{coin}/{YYYY-MM-DD}/books.parquet` and `trades.parquet`
- Handles disconnects with exponential backoff and reconnects
- Logs status every few minutes ("still alive, X books and Y trades today")
- Flushes to disk every minute or every N messages
- Clean Ctrl-C shutdown

Use the official Python SDK (`hyperliquid-python-sdk`). Its `WebsocketManager` handles reconnects; we add the persistence layer.

**Acceptance:** run the recorder for 30 minutes, then read back one of the produced parquet files in a Python REPL. Confirm books and trades look right.

## Step 3: Decide Hummingbot vs raw SDK

Spec is in `research/hummingbot.md` under "Decision deferred until we test."

Quick exercise:
1. Spin up Hummingbot in Docker against Hyperliquid testnet. Connect a test wallet. Run a built-in pure market-making strategy with $0 risk.
2. Separately, write 50 lines using the raw SDK that subscribes to the BTC L2 book on testnet and places one $5 limit order far from market.
3. Compare DX, reliability, observability. Recommendation in the file is hybrid (Hummingbot connector wrapped in our own interface). Document the decision in `research/hummingbot.md` — replace the "Decision deferred" section with the actual decision and date.

This is one day, not one week. Don't over-think it.

## Step 4: Wrap the connector

Build `code/connectors/hyperliquid.py` exposing a small async interface. Spec at the bottom of `research/hummingbot.md` ("What goes in the project's `code/connectors/` folder").

This wrapper is the boundary that everything else depends on. Get the interface right; the implementation behind it can change.

## Step 5: Naive symmetric quoter (sanity check)

Implement the simplest possible MM strategy from `research/algorithms.md`:

```
bid = mid - spread/2
ask = mid + spread/2
```

Plus inventory tracking and a hard position limit. This is the "is the plumbing real" test. Run on testnet for a few hours. Don't expect it to make money — that's not the point.

## Step 6: Backtester foundation

Don't reinvent. Adopt `nkaz001/hftbacktest` as the base. Spec in `research/backtesting_mm.md`. Adapt the Hyperliquid recorder data into hftbacktest's expected format. Replay the naive quoter strategy through the backtester. Compare to the testnet results from Step 5.

If they diverge wildly, the backtester is wrong (or our recorder is). Iterate until they match.

## Step 7+: Strategy progression and agent layer

Beyond Step 6, follow the order in `research/algorithms.md` ("Reading order for actually building this"). Then the agent layer per `research/agent_architecture.md`.

But don't get ahead of yourself. Ship Steps 1-6 first.

---

## Session Log

- **2026-04-26** — Project scaffolded. CLAUDE.md, README, research index created.
- **2026-04-26** — Round 1 research drop: order_books, market_making_101, algorithms, agent_architecture, where_does_the_edge_come_from. Key takeaway from edge analysis: maker rebates + market selection are the realistic baseline edge; agent layer is the experimental edge and shouldn't be the *only* edge.
- **2026-04-26** — Round 2 research drop: hyperliquid (fees, API, public MM tools), hummingbot (recommendation: hybrid), backtesting_mm (use hftbacktest as base, validate against testnet data, agent in shadow mode for weeks before touching live params).
- **2026-04-27** — Round 3 (final research before code): other_dexes (decision: Hyperliquid primary, Extended secondary for research, Pacifica deferred due to invite-only), regulatory_notes (US restriction on Hyperliquid is real, operator must decide their posture). Python project setup committed (.python-version, pyproject.toml, .env.example, SETUP.md). Data recorder spec written. **Project ready for handoff to Claude Code.** Next session is Step 1 of "Next Steps for Claude Code" above.
- **2026-04-28** — Steps 1 + 2 complete. Environment set up on Linux server (Ubuntu 24.04, Python 3.12). Repo pushed to GitHub (awalsh24/LordoftheSpreads). Data recorder implemented and running on server in screen session — writing books.parquet, trades.parquet, and book_deltas.parquet for BTC/ETH/SOL. Delta computation verified via REPL: correct schema, real timestamps, sensible size changes.
- **2026-04-30** — Step 3 partially complete. Track B (raw SDK eval) run against testnet: WS subscriptions confirmed working, l2Book + trades streaming correctly, REST /info clean, order placement returned expected auth error (API wallet not yet authorized on testnet UI). Key finding: trades are block-batched — within-block ordering is not available from the feed. Track A (Hummingbot Docker) deferred pending funded testnet account. **Decision committed: hybrid approach (Option B) — Hummingbot connector wrapped in our own interface, with raw SDK as fallback if wrapping proves painful.** Decision documented in `research/hummingbot.md`. Step 4 (connector wrapper) is unblocked.

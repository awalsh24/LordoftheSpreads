# Agent Architecture

How the LLM layer plugs into the trading system. What it perceives, what it decides, how it acts.

This file is a working design draft, not a final spec. Expected to evolve heavily.

---

## The two-tier design

```
┌─────────────────────────────────────────────────────────┐
│  AGENT TIER (slow, ~minutes per decision)               │
│  - Perceives market context (book, trades, news, vol)   │
│  - Selects strategy, sets parameters                    │
│  - Sets risk overrides (halt, reduce-only, etc.)        │
│  - Writes decisions + reasoning to a decision log       │
└────────────────┬────────────────────────────────────────┘
                 │  small, structured commands
                 │  (set_strategy, set_params, halt, etc.)
                 ▼
┌─────────────────────────────────────────────────────────┐
│  EXECUTION TIER (fast, ~milliseconds per decision)      │
│  - Runs the selected strategy (e.g. Avellaneda-Stoikov) │
│  - Maintains live quotes, processes fills               │
│  - Enforces hard risk limits regardless of agent input  │
│  - Streams state back to the agent on a schedule        │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
            EXCHANGE (Hyperliquid)
```

**Key principle:** the LLM is too slow and expensive to be in the per-quote loop. Quotes update many times per second; LLM calls take seconds and cost tokens. The agent operates on a *much slower* clock — every 1–15 minutes for routine decisions, immediately on triggered events (large drawdown, scheduled news).

The execution tier is plain Python, deterministic, fast, and dumb. It does what it's told. It also has hard-coded safety: max position, max loss, max age of last agent heartbeat. If the agent dies or goes crazy, the executor flattens and stops.

---

## What the agent needs to perceive

This is the question you asked. Sources break into five categories.

### 1. Market data (from the exchange)

Fed in directly from our own connector. Cheap and fast.

- **Order book snapshot** — top N levels of bids/asks, sizes, recent updates
- **Recent trade tape** — last K trades: price, size, side
- **Funding rate** — for perps, the periodic payment between longs and shorts
- **Open interest** — total outstanding contracts
- **Our own state** — current inventory, recent fills, P&L, open orders

The agent doesn't need raw firehose data. The Python layer pre-aggregates: `volatility_30s`, `volume_5m`, `book_imbalance`, `recent_fill_rate`, etc. Hand the agent ~30 features rather than 30,000 trades.

### 2. Cross-venue data (other exchanges)

For most assets, the "true" price isn't on the venue you're quoting on — it's on the deepest market (usually Binance for crypto). The agent should know:

- **Reference price** from a deeper venue (Binance, Coinbase, etc.) via their public WebSocket feeds
- **Basis** between our venue's price and the reference (premium/discount)
- **Funding rate divergence** across venues

When basis blows out, that's exactly when arbitrageurs are most active and adverse selection is highest. Defensive signal.

### 3. News and macro signals

This is where it gets messier. The available sources, roughly:

- **Crypto-native news terminals** — Tree of Alpha, BlockBeats, Phoenix News, others. They aggregate breaking news with sub-second latency and offer paid API/WebSocket feeds. The professional MM community uses these.
- **Twitter/X firehose** — major crypto news breaks here first. Paid API access required to do this programmatically; the free tier is too limited.
- **Macro calendars** — FOMC dates, CPI release times, employment numbers. These are scheduled, so the agent should know "FOMC announcement in 47 minutes, reduce risk."
- **On-chain alerts** — large wallet movements, whale liquidations, exchange inflows/outflows. Tools like Whale Alert, Arkham, Nansen.
- **Anthropic web search** — for our agent specifically, we can give it a tool to search the web on demand. Not real-time enough for breaking news, but good for "what is going on with token X" questions when the agent senses something is off.

**Realistic v1 posture:** start with macro calendars (free, scheduled, high signal) and our own market data. Add a single news source when we have a reason to believe it would change a trade decision. Don't pay for news terminals before you've proven the setup works without them.

### 4. Internal state

The agent should always have access to:

- Recent decision history (what did I decide 5 minutes ago, and how is that working out?)
- Current strategy and parameters
- P&L over multiple time windows (last hour, day, week)
- Risk metrics (current inventory, max drawdown, win rate)

This goes in a structured "state" object passed in every prompt. Critical for continuity — without it the agent can't tell whether it's making the same mistake repeatedly.

### 5. The order book chart (vision, optional v2)

Your original idea included the agent reading order book charts as images. This is feasible — Claude can process images. Useful for:

- Recognizing visual patterns (book imbalance, walls, spoofing) the feature engineering missed
- Sanity-checking numerical features against what a trader would actually see

Cost: vision tokens are more expensive and the inference is slower. Probably v2 — start with structured features, add vision when there's a specific decision the agent is getting wrong without it.

---

## What the agent decides

Three buckets:

**Strategy selection.** Pick one of N pre-built strategy modules. Possible options for v1:

- `quote_tight_avellaneda` — calm market, capture spread aggressively
- `quote_wide_defensive` — uncertain market, bigger spreads, smaller size
- `one_sided_skew` — strong directional bias, only quote on one side
- `halt` — pull all quotes, do nothing, wait

**Parameter tuning** within the chosen strategy:

- Risk aversion `γ`
- Volatility estimate (overrides or scales the realized estimate)
- Maximum position size
- Quote refresh rate

**Risk overrides.** Special instructions:

- "Reduce only" — only place quotes that would reduce inventory, never grow it
- "Flatten" — close existing position via market orders, then halt
- "Pause for X minutes" — used around scheduled news events

---

## How the agent acts (tool interface)

The agent talks to the executor through a small set of typed function calls. Initial sketch:

```python
get_state() -> dict          # everything the agent should know about now
set_strategy(name: str, params: dict) -> ack
halt(reason: str) -> ack
flatten(reason: str) -> ack
log_decision(reasoning: str) -> ack   # for our records, not for the executor
```

Designed to be small. The agent doesn't place individual orders — that would be the wrong abstraction layer. It tells the executor what to do; the executor handles the how.

---

## Cadence and triggers

Two kinds of agent invocation:

**Scheduled** — every N minutes, regardless of state. Routine "is everything still correct?" check. N starts large (15 min) and we tighten if needed.

**Event-triggered** — anything unusual wakes the agent immediately:
- Large drawdown threshold crossed
- Inventory exceeds soft limit
- Scheduled news event approaching (FOMC, CPI, etc.)
- Cross-venue basis exceeds threshold (likely arb activity)
- Volatility spike beyond threshold

Triggers come from the executor, not from the agent itself. Cheap to implement, important for safety.

---

## Failure modes to design around

**Agent hallucinates parameters.** Mitigation: parameters are validated by the executor. `γ = 0.0001` and `γ = 100` both rejected as out of range. Agent gets an error and has to retry.

**Agent makes a slow decision.** Mitigation: executor has a default safe state (current parameters, no override). If the agent doesn't return in time, executor just keeps doing what it was doing. No "I'll wait for the agent" stalls.

**Agent dies entirely.** Mitigation: heartbeat. If no agent decision in 30 minutes, executor enters reduce-only mode. After 60 minutes, executor flattens.

**Agent gets stuck in a bad loop.** Mitigation: human review of decision log. Hard limits on losses-per-day that bypass the agent entirely.

**Agent latches onto a story and won't update.** This is the genuinely scary one for LLM agents. Mitigation: fresh context window per call (no chat-history-style memory accretion); state gets re-injected each time. Memory lives in the structured state object, not in the agent's running context.

---

## Open design questions

- How much reasoning do we want the agent to externalize before deciding? (Likely: think out loud in a scratchpad, then emit structured decision.)
- Single agent, or sub-agents (one for regime detection, one for risk, one for parameters)? Multi-agent has more failure modes but cleaner separation.
- How do we evaluate whether the agent layer is *adding value* vs. fixed-parameter AS? Need an A/B harness in the backtester.
- What model? Haiku is fast/cheap and might be enough for routine checks; Opus for critical decisions. Possibly a tiered design.

These resolve as we build. None of them block starting.

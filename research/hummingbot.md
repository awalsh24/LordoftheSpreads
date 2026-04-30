# Hummingbot

The build-vs-use decision on connectors. Your friend is in the community, which is a real asset.

Verified via web search 2026-04-27.

---

## What Hummingbot is

Hummingbot is the dominant open-source framework for crypto algo trading. Originally a Python application; the project has expanded into a small ecosystem:

- **Hummingbot Client** — the original CLI app, runs in Docker, connects to exchanges and runs strategies. V1 strategies (older, simpler) and V2 strategy controllers (newer, more flexible).
- **Hummingbot API** — REST/Python interface to manage credentials, portfolios, and orders programmatically without the CLI.
- **Condor** — newer multi-bot manager with cloud deployment, Telegram, MCP for AI agents. Aimed at trading agents, multi-bot setups, modern interfaces.
- **Dashboard** — older web UI for managing the client, now deprecated in favor of Condor.

It's free, the source is on GitHub, and the user community is large enough that most common questions have answers.

The Hummingbot Foundation has paid-partnership relationships with several exchanges (including Hyperliquid) — sign-ups via Hummingbot referral links earn rebates that fund the foundation. Worth knowing because it explains why connector quality is often better for sponsoring exchanges.

---

## What it gives us, concretely

The two things that are genuinely hard to build well:

**1. Exchange connectors.** Each connector handles auth, WebSocket subscriptions and reconnects, REST request/response handling, order state machines (placed → acknowledged → partially filled → filled / canceled / rejected), balance tracking, fee bookkeeping, rate limits, and a hundred edge cases that only show up after weeks of running. Hummingbot maintains:

- `hyperliquid_perpetual` — perp connector for Hyperliquid (this is what we'd use)
- `hyperliquid` (spot) — spot connector for Hyperliquid
- Connectors for dozens of other venues including Binance, Bybit, dYdX v4, Derive, Injective, XRPL

The Hyperliquid perp connector supports both auth modes — Arbitrum wallet + private key, and the newer API key authentication. Vault accounts work too, with some historical bugs (worth checking the GitHub issues before trusting).

**2. Strategy framework.** Hummingbot ships with implementations of common MM strategies — pure market making, cross-exchange MM, arbitrage, grid, etc. — as templated code we could fork. We probably won't use these strategy templates directly because we want our own strategy + agent layer, but they're useful as reference implementations.

**3. Execution infrastructure.** Order tracking, P&L computation, logging, alerting via Telegram, position management. Plumbing that works if we don't fight it.

---

## What it costs us

**1. Architectural opinions.** Hummingbot has a worldview: strategies are Python classes with specific lifecycle methods, configuration lives in YAML, the runtime is event-driven around exchange callbacks. If our agent layer fits inside that worldview cleanly, great. If our design (LLM agent calling shots every few minutes, separate process from the executor, structured tool calls) wants to live differently, we'll be working against the grain.

**2. Indirection.** Hummingbot is a substantial codebase. When something breaks at 2am — and it will — debugging through their layers is harder than debugging our own thin connector. Pros learn the codebase deeply; we'd be amateurs in that codebase.

**3. Maintenance lag.** Hyperliquid ships features (HIP-3 markets, new endpoints, auth changes). Sometimes Hummingbot keeps up immediately; sometimes there's a lag. We'd be at the mercy of someone else's release cadence for venue features.

**4. Strategy framework lock-in (the real risk).** If we adopt Hummingbot's strategy framework, our agent layer ends up being a Hummingbot extension. Migrating to anything else later means rewriting both layers. If we use Hummingbot *only* for the connector and run our own strategy + agent code on top, this risk shrinks.

---

## The decision: hybrid is probably right

Three concrete options:

### Option A: Full Hummingbot

Use Hummingbot for connector, strategy framework, runtime. Build the agent layer as a Hummingbot V2 controller or Condor extension.

**Pros:** Fastest start. Largest community. Built-in tooling.
**Cons:** Architectural lock-in. Our agent design has to fit their model. Harder to do anything novel.

### Option B: Hummingbot connector, our own everything else

Import only Hummingbot's `hyperliquid_perpetual` connector module. Wrap it in a clean interface our strategy code talks to. Build our strategy modules, agent layer, backtester from scratch.

**Pros:** Save weeks of connector work. Keep architectural freedom for the part that matters (strategies + agent). Connector boundary is a natural API surface.
**Cons:** Importing pieces of a framework while ignoring the rest is sometimes painful. Some Hummingbot connectors expect to live inside the broader Hummingbot context. Need to verify the perp connector can run standalone or be cleanly wrapped.

### Option C: Roll our own connector

Use the official Python SDK from Hyperliquid directly. Build our own thin wrapper. Ignore Hummingbot.

**Pros:** Maximum control. No external dependencies on a moving framework. Cleanest architecture for our specific needs.
**Cons:** Weeks of work on connector reliability we'd otherwise have for free. Reinventing reconnect logic, order state tracking, edge case handling. Most of the painful bugs in any of this are in the connector layer, and building one from scratch is how you find them all yourself.

### Recommendation: Option B for v1, with Option C as a fallback

The right play is to use Hummingbot's connector via a clean wrapper, *unless* we discover the connector can't be cleanly extracted from the broader framework — in which case Hyperliquid's official Python SDK is our fallback. The official SDK is well-maintained and used by many bots; it's not the heavy lift it would be on a more obscure venue.

Either way, **the strategy and agent layers are ours.** That's where the actual work — and the actual edge — lives. The connector is plumbing.

---

## Your friend's involvement

Your friend being in the Hummingbot community is genuinely valuable for three things:

1. **Insider knowledge of connector quirks** — which Hummingbot connectors are battle-tested vs. which are flaky. The `hyperliquid_perpetual` connector specifically.
2. **Existing relationships** — getting answers in the Hummingbot Discord/GitHub faster than starting cold.
3. **Strategy reference** — they've seen real bots run and lose money in real ways. That tacit knowledge accelerates us past mistakes everyone makes once.

Concrete asks for them, when the time comes:

- "How stable is the `hyperliquid_perpetual` connector in late 2025? Any known issues with quote-heavy strategies?"
- "Can the connector be used standalone, outside the Hummingbot strategy framework? What's the cleanest way?"
- "What's the realistic latency from quote-decision to order-on-book using Hummingbot vs. raw SDK?"
- "Anyone in the community running an LLM-augmented strategy? Lessons learned?"

---

## Decision — 2026-04-30

**Hybrid: Option B. Hummingbot connector wrapped in our own interface.**

This is a provisional decision based on Track B (raw SDK) results. Track A (Hummingbot end-to-end) is deferred pending a funded testnet account but does not change the direction — it would only validate or add caveats to the Hummingbot side.

---

### Track B findings — raw `hyperliquid-python-sdk` (completed 2026-04-30)

Script: `scratch/track_b_sdk_eval.py`. Run against testnet with an unfunded API wallet.

**WebSocket — worked cleanly.**
- Connected immediately to `wss://api.hyperliquid-testnet.xyz/ws` with no friction
- `l2Book` subscription returned updates at ~0.5s intervals, 20 levels each side, clean JSON
- `trades` subscription returned data; trades arrive **batched per block** — multiple trades share an identical exchange timestamp, meaning the exchange delivers a whole block's worth of trades at once and they are unordered within the block. This is important for the backtester: within-block trade ordering is not available from this feed, only between-block ordering.
- Sample book data (BTC testnet, 2026-04-30):
  ```
  [BOOK #1] bid=76624.0 ask=76660.0 depth=20x20 exchange_ts=1777573535442
  [BOOK #2] bid=76624.0 ask=76660.0 depth=20x20 exchange_ts=1777573535999
  [BOOK #3] bid=76624.0 ask=76660.0 depth=20x20 exchange_ts=1777573536558
  ```
  Spread = $36 on testnet BTC. Update cadence ~0.5-0.6s, consistent with documented block time.

**REST `/info` — worked cleanly.**
- `Info(TESTNET_API_URL, skip_ws=True).all_mids()` returned BTC mid=76642.0 with no issues.

**Order placement attempt — 293ms round-trip, clean error message.**
- The SDK handles eth signing transparently; no boilerplate needed beyond `Account.from_key(private_key)`.
- Wallet not yet authorized on testnet (API wallet not linked to a main account via the UI), so placement returned:
  ```
  {'status': 'err', 'response': 'User or API Wallet 0x... does not exist.'}
  ```
  Error is machine-readable and interpretable. Not a crash, not an ambiguous exception.

**Surprises and gotchas:**
1. **Trades are block-batched.** Multiple trades arrive simultaneously with the same `ts`. Within a block, their order is arbitrary from the WebSocket consumer's perspective. The backtester must not assume intra-block trade ordering.
2. **API wallet authorization requires the UI.** Generating the keypair programmatically is easy (`eth_account`), but linking it to a main account requires a signed transaction via the Hyperliquid web app. There is no documented API-only path for this. This means initial account setup always requires the UI; ongoing bot operation does not.
3. **`skip_ws=True` is required** for the `Info` constructor if you don't want it to open a background WebSocket connection. Not prominently documented; would have caused a hang in some contexts without it.
4. **293ms order round-trip** from a European VPS. Acceptable for a strategy that quotes every few seconds; would be significant for a latency-sensitive strategy. Raw SDK adds no measurable overhead beyond network.

---

### Track A status — deferred

Hummingbot Docker eval requires a funded testnet account to run the built-in MM strategy and observe fill events. The testnet UI (`app.hyperliquid-testnet.xyz`) was inaccessible during the eval window due to a browser/MetaMask issue. Track A is **deferred, not skipped**.

When Track A runs, the specific things to verify:

1. **Reconnect behavior under network drops.** Does the `hyperliquid_perpetual` connector recover cleanly and re-subscribe? Does it re-send open orders that were in-flight during the disconnect, or silently drop them? This is the most important reliability question.
2. **Partial fill handling.** When a resting order is partially filled, does the connector emit the correct fill event with the right size, leaving the remainder in the book? Or does it incorrectly mark the order as fully filled / cancelled?
3. **Rate limit behavior under heavy quote/cancel load.** A market-making strategy cancels and replaces quotes frequently. Does the connector throttle gracefully, or does it error and require manual recovery?

---

### What this means for Step 4

Build `code/connectors/hyperliquid.py` as a clean async wrapper. The interface (the `ExchangeConnector` Protocol already documented below) stays fixed. The implementation initially wraps Hummingbot's `hyperliquid_perpetual` connector.

**The raw SDK (Option C) remains viable.** Track B showed the SDK is clean, low-friction, and well-behaved. If wrapping the Hummingbot connector proves painful — because it resists extraction from the broader framework, or because its internal event model fights our async design — switching the implementation to the raw SDK is a contained change behind the interface. The interface is the bet; the implementation is not.

The decision is Option B unless wrapping proves painful, in which case it becomes Option C. Either way the strategy and agent layers above the interface are unaffected.

---

## What goes in the project's `code/connectors/` folder

Whichever path we choose, the connector layer in our project should expose a small, well-typed interface:

```python
class ExchangeConnector(Protocol):
    async def subscribe_book(self, symbol: str) -> AsyncIterator[OrderBook]: ...
    async def subscribe_trades(self, symbol: str) -> AsyncIterator[Trade]: ...
    async def place_order(self, order: Order) -> OrderId: ...
    async def cancel_order(self, order_id: OrderId) -> None: ...
    async def get_position(self, symbol: str) -> Position: ...
    async def get_balance(self) -> Balance: ...
    # etc.
```

Whether the implementation wraps Hummingbot or uses the SDK directly is invisible to everything above this interface. This is the most important architectural choice we'll make in the connector layer — a clean API surface that the rest of the system depends on, not the underlying library.

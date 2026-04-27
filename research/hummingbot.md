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

## Decision deferred until we test

This file recommends Option B but doesn't commit. The right time to decide is when we're about to write the connector layer — we evaluate by trying. Steps:

1. Spin up Hummingbot client in Docker. Connect to Hyperliquid testnet. Run a built-in pure market-making strategy with $0 risk. Just to see it work.
2. In a separate scratch project, install `hyperliquid-python-sdk` from pip. Write 50 lines that subscribe to BTC L2 book and place a test limit order on testnet.
3. Compare developer experience, reliability, observability.
4. Decide.

This whole evaluation is a one-day exercise, not a week. We should not over-think it before doing it.

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

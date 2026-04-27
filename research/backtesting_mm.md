# Backtesting Market-Making Strategies

The boring-but-critical file. The single biggest reason MM bots blow up live is that the backtest lied. This file is about not letting that happen.

---

## Why MM backtesting is harder than directional backtesting

A directional backtest is straightforward: at time T, the strategy says "buy at price P." The historical data tells us whether the market traded at P after time T. If it did, we got filled. We compute the P&L from there.

A market-making backtest can't work this way because **our quotes don't just sit there waiting to be filled — they exist in a queue, behind other people's quotes, and they get filled only if enough volume arrives at our price level to reach our position in the queue**. This depends on:

1. Where in the queue our quote actually was when it arrived (which depends on latency)
2. How much volume traded at that price level (which the historical data tells us)
3. Whether our quote, by existing, *changed* the market (which it would have, if we'd been there in real time)

Point 3 is the killer. In real life, our quote is a real quote that other traders react to. In a backtest, we're inserting our quote into a historical recording that already happened *without us in it*. The simulation is always partly fiction.

This isn't an academic concern. **It is the dominant reason MM strategies that look great in backtest lose money live.** Every paper, every framework, every honest practitioner says the same thing.

---

## The four big sources of backtest dishonesty

### 1. Optimistic fill probability

Naive simulators say: "if the market traded through your price, you got filled." This is wrong. Even if 100 BTC traded at your bid price, you might have been at the back of a queue with 200 BTC ahead of you — only 100 traded, your order didn't fill.

**Fix:** Model queue position explicitly. When your order arrives, place it at the back of the current queue at that price level. As trades happen at that price, decrement the queue from the front. Your order fills only when its turn comes up.

This is what serious frameworks like `hftbacktest` do. It's the standard approach in the literature. See [Lalor & Swishchuk 2025](https://arxiv.org/pdf/2409.12721) for an empirical study and [Moallemi & Yuan 2017](https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2996221_code2323791.pdf?abstractid=2996221) for the theoretical model of queue value.

### 2. Ignoring adverse fills

In real markets, fills are not random — they are **correlated with price moves against you**. You sell at the ask, then price moves up. You buy at the bid, then price moves down. This is adverse selection in numbers.

A backtest that assumes fills happen at the historical mid (or even at your quoted price with no further adjustment) overstates P&L because it ignores this adverse drift after the fill.

**Fix:** Track post-fill mark-to-market. After each simulated fill, evaluate where the price moves over the next N seconds. If fills are systematically followed by adverse moves in your simulator, you're seeing reality. If they're not, your simulator is wrong.

The Lalor & Swishchuk paper found that adverse fills occur in the *majority* of MM trade executions on liquid futures contracts. A backtest that doesn't show this pattern is broken.

### 3. Ignoring latency

Real systems have latency. Time elapses between observing the book, deciding to quote, sending the order, and the order appearing on the book. Same for cancels.

Latency lets faster traders pick off your stale quotes. If price moves $5 in the time between your decide-to-cancel and your cancel-arrives, anyone faster than you can hit your stale quote and lock in $5 free.

**Fix:** Model latency explicitly. Build in a feed-side delay (you see book updates N ms after they happen on the venue) and an order-side delay (your orders arrive at the venue M ms after you send them). Run the simulator with realistic numbers — for Hyperliquid, expect ~100-300ms round-trip from a typical residential connection. Vary these and observe sensitivity.

### 4. Ignoring market impact

In real life, our orders affect the book. A big bid we post at the top of the book might cause others to step in front of us, or might cause sellers to revise down. Our cancel might be observed and reacted to.

This effect is small for tiny operators. **For our scale it can probably be ignored** — a $500 bid in a $10M depth book moves nothing. But if we ever scale up, this becomes real.

**Fix:** For now, just acknowledge it. Document a market-impact assumption ("orders <X% of top-of-book size assumed to have zero impact") and revisit if our size ever grows.

---

## The validation criterion that actually matters

The single most important test of a backtester:

> If you ran a strategy live in January 2026, the backtest of that strategy on January 2026 data should produce results that closely match the actual live results.

This is the criterion `hftbacktest` (the leading open-source MM backtester) explicitly uses. Until the backtester passes this test, all results from it are unreliable — not "approximately right," not "directionally useful." Unreliable.

The catch: we can only run this test after we have live trading data. Before that, we have no objective check on the backtester. So:

**Phase 0 (now):** Build the backtester carefully, modeling queue position, adverse fills, and latency. Document every assumption.

**Phase 1 (testnet):** Run our strategy on Hyperliquid testnet with the same code that does live trading. Capture all the data. Replay it through the backtester. Tune until backtest matches testnet behavior.

**Phase 2 (live, tiny):** Trade live with hundreds of dollars at risk, not thousands. Capture data. Compare to backtest. The gap is our model error. Iterate.

**Phase 3 (live, larger):** Only after backtest matches live within a tolerance we've defined upfront. *Then* we trust the backtester for strategy research.

---

## Build vs. use, again

There's an open-source MM backtester that does most of this right: **`nkaz001/hftbacktest`**.

- Models queue position via configurable probability models
- Models feed and order latency
- Uses Numba JIT for speed (Python with C-like performance)
- Built around full Level-2 (and Level-3 where available) tick data
- Examples for Binance and Bybit; not Hyperliquid out-of-box but extensible
- Active development as of 2026

Almost certainly the right base for our backtester. Building one from scratch that matches its quality is months of work and has no upside — the math is the math.

The work that's left:
- Adapt it to Hyperliquid's data format (we'll need to record L2 books and trades from our own WebSocket connection over time)
- Build our strategies as compatible modules
- Build the agent-layer integration (more on that below)

---

## The MM-specific data we need to collect

We can't backtest what we don't have. From day one of this project, we should be recording:

- **Full L2 book snapshots** (top 20 levels each side) at every update from the WebSocket
- **Public trade tape** — every trade, with price, size, side, timestamp
- **Funding rate history** for perps
- **Our own orders and fills** when we start placing them, with full timestamps (decide / send / ack / fill)

Storage is cheap. Lost data is gone. Set up recording before doing anything else trade-related.

For Hyperliquid specifically, this means a lightweight Python service that subscribes to `l2Book` and `trades` for our target coins and writes to disk (parquet files, partitioned by day and coin). Maybe 100 lines. Critical.

---

## Backtesting the agent layer is its own problem

Standard MM backtesting models the *strategy*. We have an extra layer: an LLM agent that picks strategies and parameters. How do we backtest that?

Two reasonable approaches:

**Replay the agent.** Run the historical market data through the agent in fast-forward, letting it make decisions at its normal cadence. Capture what it decides. Then run the strategy backtester with those decisions to compute P&L. This is honest but expensive in token costs.

**Replay the decisions.** During paper or live trading, log every agent decision with the full input. To backtest "what if the agent had been smarter," we replay the same situations and let an updated agent prompt decide differently. We don't re-run the strategy from scratch; we just compare decisions.

**Honest assessment:** Backtesting the agent is harder than backtesting the strategy, and the result is less reliable. The right posture is probably: get the strategy backtest solid, then run the agent in **shadow mode** (it makes decisions, we record them, but they don't affect trading) for weeks before letting the agent touch live parameters. Shadow mode lets us measure agent value without backtesting it.

---

## Concrete kill criteria

Define these *before* deploying real capital:

- **Maximum daily loss** — if we lose more than $X in a day, halt. No exceptions.
- **Maximum drawdown from peak** — if we're 20% below our peak P&L, halt and review.
- **Backtest-to-live divergence** — if live results deviate from backtest predictions by more than Y% over a week, halt.
- **Consecutive losing days** — if we lose 5+ days in a row, regardless of size, halt for a manual review.

These are not negotiable. They go into the executor as hard-coded rules that the agent cannot override. If the agent argues for overriding them, that argument is logged, ignored, and reviewed by us later — not acted on.

---

## Summary in one paragraph

Build the backtester to model queue position, adverse fills, and latency from day one. Use `hftbacktest` as the base, adapt for Hyperliquid. Validate by recording testnet data and comparing simulation to actual testnet behavior before trusting any backtest result. Run the agent in shadow mode for weeks before it touches real parameters. Define kill criteria upfront. Treat every "the backtest says we'd make money" claim with extreme skepticism until it's been tested live with small capital. The backtest is a hypothesis, never a result.

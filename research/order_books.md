# Order Books

Foundational. Read before anything else.

## What it is

A limit order book (LOB) is the live list of every unfilled order at an exchange, organized by price. Two stacks meet in the middle:

```
                ASKS (sellers, sorted ascending)
        $99,200 ──── 5.0 BTC
        $99,150 ──── 2.0 BTC
        $99,100 ──── 1.0 BTC   ← best ask
        ──────────────────────  spread = $100, mid = $99,050
        $99,000 ──── 1.0 BTC   ← best bid
        $98,950 ──── 3.0 BTC
        $98,900 ──── 8.0 BTC
                BIDS (buyers, sorted descending)
```

Each row is a **price level**. The number of contracts/coins available at that price is the **size** at that level. Together, the levels form **depth**. The first level on each side is the **top of book** or **best bid/best ask** (often abbreviated BBO — best bid and offer).

The space between best bid and best ask is the **spread**. Halfway between them is the **midpoint** or **mid**. Most pricing math uses mid as the reference price.

## Order types

- **Limit order** — "buy/sell at this price or better." Sits in the book until matched or canceled. Provides liquidity. **You are a maker.**
- **Market order** — "buy/sell now at whatever price is available." Crosses the spread immediately. Removes liquidity. **You are a taker.**
- **Post-only** — limit order that cancels itself if it would execute immediately as a taker. Used by makers who *only* want to earn the maker rebate and never pay taker fees.
- **IOC** (Immediate-or-Cancel) — execute whatever you can right now, cancel the rest.
- **FOK** (Fill-or-Kill) — execute the entire order immediately or cancel everything. Don't partially fill.
- **Stop** — triggers a market or limit order when price crosses a threshold. Used for stop-losses.

For market making, the workhorse is **post-only limit orders**. You're a maker by definition; you should never accidentally pay taker fees.

## How orders match

When a market buy hits the book, it eats orders starting from the best ask going up until filled. Same in reverse for market sells.

Within a price level, there's an ordering rule:

- **Price-time priority** (most exchanges) — orders at the same price fill in the order they arrived. First in, first filled. This is why latency matters — being faster to the front of the queue means more fills.
- **Pro-rata** (some derivatives venues) — fills are split proportionally across all orders at the level by size. Less benefit from speed, more benefit from posting big.

Hyperliquid uses price-time priority on a centralized matching engine that settles to its own L1 blockchain. The matching itself isn't on-chain (that would be too slow); the resulting trades and balances are.

## Spread, depth, and what they tell you

A **tight spread** (small gap) means the market is liquid and competitive. Many MMs are fighting for fills. Hard to make money.

A **wide spread** (big gap) means few quoters or high uncertainty. More money per trade, but probably less volume, and the wide spread might exist because volatility is making MMs nervous.

**Deep books** (lots of size at every level) absorb large orders without much price movement. **Thin books** are easily moved — a single big trade can blow through several levels.

A useful heuristic: profitable MM hunting grounds have decent spread *relative to volatility*. If the spread is $50 but the price moves $500 every minute, you can't capture that spread before you're underwater on inventory.

## CLOB vs AMM (DEX-specific)

Two flavors of decentralized exchange exist:

**Central Limit Order Book (CLOB)** — same model as a traditional exchange. Hyperliquid, Pacifica, Extended, dYdX, Polymarket all use CLOBs. This is what we care about. Market making here looks like market making anywhere.

**Automated Market Maker (AMM)** — Uniswap, Curve, etc. No order book. Liquidity providers deposit pairs of tokens into a pool and a formula (`x * y = k` for Uniswap V2) determines the price as people trade against the pool. "Market making" on an AMM means depositing into pools and earning fees, not posting bids and asks. Different game, not our target.

Our project is CLOB-only.

## On-chain visibility

The killer feature of DEX CLOBs for our purposes: you can see who's trading. On Hyperliquid, every position, every order, every fill is associated with a wallet address. Tools like Hyperscan, Hypurrscan, and various dashboards let you pull up the leaderboard of profitable traders and inspect their behavior.

Practical implications:
- We can identify which wallets are running market-making strategies and study their quote patterns.
- We can see where the largest positions sit, which gives us early warning of potential liquidations (forced selling at predictable price levels).
- We can measure adverse selection empirically — when our quotes get hit, who hit them, and what did that wallet do next?

This is genuinely impossible on centralized venues. Worth its own research file later.

## Glossary

- **BBO** — Best bid and offer (top of book)
- **Mid** — midpoint between best bid and best ask
- **Spread** — best ask minus best bid
- **Depth** — total size available across price levels
- **Maker** — order that adds liquidity (rests in book)
- **Taker** — order that removes liquidity (crosses spread)
- **Fill** — executed trade
- **Lift the offer** — buy at the best ask
- **Hit the bid** — sell at the best bid
- **Walk the book** — large order eating through multiple levels
- **Iceberg** — order with hidden size (shows small, has more)
- **Adverse selection** — getting filled mostly when you're on the wrong side of information
- **Inventory** — the net position you're holding from MM activity
- **Skew** — asymmetric quoting (e.g., wider ask when you're long)

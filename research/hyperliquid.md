# Hyperliquid

The primary target venue. This file makes "the venue" concrete: fees, API, what to study, what to know before going near it.

All figures and details verified via web search on 2026-04-27. Fee schedules and tier thresholds change — check Hyperliquid's official docs (`https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees`) before any deployment.

---

## What Hyperliquid is, briefly

A decentralized perpetual futures exchange that runs its own purpose-built Layer 1 blockchain. The order book is fully on-chain — every order, cancel, fill, and position is recorded on the chain. Matching happens via a custom consensus protocol (HyperBFT, derived from Hotstuff) optimized for low-latency trading. No gas fees on trades. Withdrawals: flat 1 USDC fee.

This is a CLOB DEX, not an AMM. Market making here looks like market making on a centralized venue, with the critical addition that everyone's positions are publicly visible.

**One thing to know up front:** Hyperliquid treats the United States as a restricted jurisdiction. The platform's official position is that US users cannot access the interface. This has implications for our project that aren't addressed in this file — covered separately in `regulatory_notes.md` (to be written).

---

## Fees (the heart of the matter)

### Base tier (Tier 0)

- **Perps:** 0.015% maker / 0.045% taker
- **Spot:** 0.040% maker / 0.070% taker

These are notional-based — fees are charged on the trade's notional value, not on margin posted. A $10,000 perp position at 10x leverage with $1,000 margin is charged on the $10,000.

### Volume tier system

Fee tier is determined by your **14-day rolling weighted volume**, computed as:

```
weighted_volume = (14d perps volume) + 2 × (14d spot volume)
```

Note: spot counts double. Tiers are evaluated daily in UTC. Sub-accounts share the master account's tier.

At Tier 4+, the maker fee drops to zero. The current top maker tier offers **negative maker fees (a rebate)** — at sufficient maker volume share (~0.5% of total venue maker volume over 14 days), makers receive approximately -0.001% to -0.003% per filled maker order. This is the venue *paying you* to provide liquidity.

The exact tier table moves; pull the current table from the docs at deployment time.

### Discount stack

These stack multiplicatively:

- **Referral discount** — 4% lifetime, applies to first $25M in your volume. Trivial to claim.
- **HYPE staking** — 5–40% off, based on staked amount. Tiers from "≥10 HYPE" (5% off) up to "≥500,000 HYPE" (40% off). Real cost: locking capital in HYPE itself, which carries token price risk.
- **Aligned quote assets** — certain pairs (denominated in specific quote tokens) get 20% lower taker fees, 50% better maker rebates, 20% more volume contribution toward tier progression. The list of aligned pairs is in the docs and changes.
- **HIP-3 growth mode** — newly launched permissionless perp markets (the HIP-3 framework) can run in "growth mode" where protocol fees are reduced ~90% to bootstrap liquidity. Time-limited per market.

### What this means for our project

The realistic v1 fee posture:

- Sign up via referral (4% off, free)
- Skip HYPE staking unless we have idle HYPE capital we don't mind locking up
- Look for HIP-3 markets in growth mode as fee-attractive starting points
- Forget about reaching the maker rebate tier in v1 — that requires meaningful share of total venue maker volume, which is institutional-scale

Our edge from fees in v1 is: avoid taker fees entirely (post-only discipline), capture the 4% referral, and target growth-mode markets where the math is more forgiving. Maker rebates are a v3+ aspiration.

---

## API

### Endpoints

- **Mainnet REST:** `https://api.hyperliquid.xyz`
- **Mainnet WebSocket:** `wss://api.hyperliquid.xyz/ws`
- **Testnet REST:** `https://api.hyperliquid-testnet.xyz`
- **Testnet WebSocket:** `wss://api.hyperliquid-testnet.xyz/ws`

The same code paths work against testnet — critical for our development workflow. We will do all initial integration on testnet with fake USDC.

### SDKs

- **Official Python SDK:** [`hyperliquid-dex/hyperliquid-python-sdk`](https://github.com/hyperliquid-dex/hyperliquid-python-sdk) — this is what we'll use unless we find a strong reason otherwise.
- **Rust SDK** (community): `infinitefield/hypersdk`
- **TypeScript SDKs** (community): `nktkas/hyperliquid`, `nomeida/hyperliquid`
- **CCXT integration** also available, conforms to the standard CCXT interface.

### Auth

Two options:

1. **Wallet signing** — your account wallet (Arbitrum-connected) signs each order. Means the trading machine has access to a key that can move funds.
2. **API wallet (agent)** — generate a separate API wallet from the Hyperliquid web UI that can place trades but cannot withdraw. This is the right pattern for a bot. Generate via `app.hyperliquid.xyz/API`. Set "Days Valid" to maximum (180 days, often). Re-authorize before expiry.

We will use API wallets, not main wallet keys. Loss of an API wallet key means trades can be placed in your name; it does NOT mean funds can be withdrawn. This is the critical security boundary.

### WebSocket — what we'll subscribe to

Relevant subscription types (full list in docs):

- `l2Book { coin, nSigFigs, nLevels }` — L2 order book snapshots, pushed each block where book has changed (~0.5s typical interval)
- `bbo { coin }` — best bid/offer updates only when BBO changes
- `trades { coin }` — public trade tape
- `candle { coin, interval }` — OHLCV at specified interval
- `userFills { user }` — our own fills, snapshot then streaming
- `userEvents { user }` — fills, funding payments, liquidations, non-user cancels
- `webData2 { user }` — combined user state (positions, orders, balances)
- `allMids` — mid prices across all coins

### Limits and gotchas

- **1000 WebSocket subscriptions per IP** — plenty for our scale, but worth knowing.
- **Disconnects happen** without warning. SDKs handle reconnect; missed messages arrive in the snapshot ack. Our connector layer must be robust to this.
- **Rate limits** are token-bucket. Official Python SDK handles this transparently.
- **Order book snapshot cadence** — pushed per block when the book has changed, with a minimum interval of ~0.5s between pushes for the same coin. So our quote refresh rate is bounded by chain speed, not by our code speed.

---

## What to study: public market makers on-chain

This is the unique-to-DEX advantage. Tools that expose Hyperliquid wallet behavior:

- **HyperTracker** (`hypertracker.io`) — wallet leaderboards, position tracking, alerts. Free tier is generous. Has an API.
- **Hyperscreener (ASXN)** (`hyperscreener.asxn.xyz`) — perps, spot, HIP-3, HyperEVM, revenue, builder codes, top traders.
- **CoinGlass Hyperliquid** (`coinglass.com/hl`) — wallet categorization (smart money, "Giga Rekt"), position heatmaps.
- **Dexly Hyperliquid leaderboard** — ranks wallets by realized PnL across 24h/7d/30d/all-time windows.
- **CoinMarketMan / HyperTracker article** — they run a read-only Hyperliquid node and publish global trader analytics.
- **Hyperliquid's own leaderboard** (`app.hyperliquid.xyz/leaderboard`) — official, less granular but authoritative.

Methodology for studying public MMs:

1. Pull leaderboard, filter by 30-day PnL > $X with high trade count and low average hold time. These are likely MMs, not directional traders.
2. Inspect their fills — do they consistently fill on both sides of a market within seconds of each other? That's MM behavior.
3. Track their positions over time. MMs will hover near zero net position; directional traders accumulate.
4. Note which markets they concentrate on. Where the experienced MMs aren't paying attention is potentially where smaller operators have room.

The HLP vault (Hyperliquidity Provider) is Hyperliquid's official community MM vault. Anyone can deposit USDC and share in PnL. Studying the HLP's behavior is valuable but it's not really "competition" — it's a baseline. Beating HLP on the markets it operates in is hard; ignoring HLP on markets where it doesn't quote is fine.

---

## HIP-3 markets (the underrated angle)

HIP-3 is Hyperliquid's framework for permissionless perp market creation. Third parties ("builders") can deploy new perp markets — examples include `trade.xyz` for tokenized stocks and commodities. These markets have:

- 2x base fee rates (the builder takes 50% of fees)
- Optional growth mode that reduces fees ~90%
- Lower volume, so less MM competition
- Often weirder underlying assets (oil, wheat, S&P 500 perps, individual stocks)

For a small operator, HIP-3 markets in growth mode are potentially more attractive than the core perps. Less competition, better fees per fill, weirder dynamics that are less efficiently priced. Worth a dedicated research pass once we have the basic system working.

---

## Practical first steps with this venue

When the time comes:

1. Create a Hyperliquid account through someone's referral link (claim the 4%).
2. Bridge a small amount of USDC from Arbitrum to test (under $50). Bridging cost is a few cents in Arbitrum gas.
3. Generate an API wallet via `app.hyperliquid.xyz/API`. Save the key in a `.env` (gitignored).
4. Install the Python SDK, run a "hello world" script that fetches the BTC L2 book and prints it.
5. Place a single $10 limit order far from the current price on testnet. Observe the fill flow end-to-end before it becomes urgent.
6. Pull a leaderboard from HyperTracker and identify 5-10 wallets that look like consistent MMs. Save their addresses to `references/mm_wallets_to_watch.md`.

None of this requires our strategy code to exist yet. It's pure infrastructure and reconnaissance.

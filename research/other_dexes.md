# Other DEXes — venue comparison and decision

Hyperliquid is the primary target (covered in `hyperliquid.md`). This file surveys the alternatives and answers: should we use Hyperliquid alone, or alongside another venue? If we ever pivot off Hyperliquid, where do we go?

Verified via web search 2026-04-27. Numbers shift; check official docs before committing.

---

## Quick comparison

| Feature | Hyperliquid | Pacifica | Extended (ex-X10) |
|---|---|---|---|
| Chain | Own L1 (HyperBFT) | Solana | Starknet (ZK rollup) |
| Maker fee (base) | 0.015% | 0.0075% (or 0.02%, sources vary) | **0.000%** |
| Taker fee (base) | 0.045% | 0.020% | 0.025% |
| Maker rebate (top tier) | -0.001% to -0.003% | 0.000% (zero, not rebate) | up to -0.020% (2 bps) |
| Leverage | up to 50x | up to 50x | up to 100x |
| Markets | 100+ perps + spot + HIP-3 | 20 perps | 100+ (crypto, equities, FX, commodities) |
| Public leaderboard | Yes, very mature | Limited | Limited |
| Status | Public | **Closed beta, invite-only** | Public |
| US accessibility | **Restricted** | Restricted | Varies |
| Tokenized stocks/commodities | Yes (HIP-3) | No | **Yes (native)** |
| Notable | Dominant DEX, deep on-chain data | Solana speed, no token yet | EVM-friendly bridge, native TradFi |

---

## Pacifica

Solana-based perp DEX, founded January 2025 by Constance Wang (ex-FTX COO) and others. Lots of buzz, real volume — was #1 perp DEX on Solana by daily volume in late September 2025, processing $100B+ in cumulative trades by early 2026.

**The case for it:**
- Maker fees as low as 0.0075% at base tier, dropping to zero at VIP levels
- Active points program (500K points distributed weekly) with potential airdrop value
- Self-funded team (ex-FTX, Binance, Coinbase, Jane Street, OpenAI) — credible execution
- Built in Rust from scratch, low-latency design
- API supports batch orders, post-only (ALO), conditional orders, TWAP-like features

**The case against it:**
- **Closed beta, invite-only.** This is the killer for our project. Without an invite, we can't even start. With an invite, the friction is real and the user base is small (~10,000 wallets).
- **$50K equity cap and $50K/24h withdrawal cap during closed beta.** Fine for our v1 capital, but means we can't scale here without the venue scaling first.
- Limited public visibility into other traders' behavior compared to Hyperliquid. Less "study the pros" opportunity.
- Smaller market selection (20 perps vs 100+ on HL).
- Solana network outages have historically been a thing. Worth knowing.

**Verdict:** Don't pivot here unless someone hands you an invite. If you get one, it's worth running a parallel small position to farm points and learn the venue, but Hyperliquid stays primary.

---

## Extended (formerly X10)

Starknet-based perp DEX with a hybrid architecture (off-chain matching, on-chain settlement). Built by an ex-Revolut team. Around $319M average daily volume in late 2025.

**The case for it — and there's a real case:**
- **0% maker fee at base tier.** This is genuinely better than Hyperliquid for makers, no tier-climbing required.
- Maker rebates up to 2 bps (-0.020%) on a 30-day maker-share basis — easier to access than Hyperliquid's rebate tier.
- **Native tokenized equities, FX, and commodities** (SPX, EUR, XAU/gold, Brent crude) trade alongside crypto. This directly matches your interest in trading oil/wheat/equities on-chain.
- 100+ markets, up to 100x leverage.
- EVM-friendly UX — deposit/withdraw USDC from Ethereum, Arbitrum, Base, BSC, Avalanche, Polygon. No need to deal with native Starknet wallets if you don't want to.
- Active points program (similar airdrop dynamics to Pacifica).
- Has an "XVS Vault" that quotes across markets — analogous to Hyperliquid's HLP. Means there's a "professional MM baseline" to study.

**The case against it:**
- Starknet auth has more moving parts. Read-only ops use a standard API key; write ops require a Stark signature. The official SDK handles this, but it's a bit more complex than Hyperliquid's API-wallet model.
- Smaller than Hyperliquid (volume, liquidity, ecosystem tooling).
- Less public on-chain visibility into other MMs' positions and PnL. The "study the pros" advantage of Hyperliquid is weaker here.
- Market orders are interesting: not natively supported. A market order is sent as a limit IOC with a `(1 ± 1.5%)` crossing buffer. Worth understanding before assuming standard CEX semantics.
- Order expirations are mandatory. Mainnet max 90 days; testnet max 28. Affects how we structure long-resting orders.

**Verdict:** **The most realistic secondary venue.** If we want exposure to tokenized equities and commodities (which you specifically called out as interesting), this is where it lives most naturally. The 0% maker fee + rebate availability is a genuine edge over Hyperliquid for our scale. Worth treating as a parallel target — not "instead of Hyperliquid" but "alongside, when we want different markets."

---

## dYdX (mentioned for completeness)

Mature, established perp DEX. Maker rebates up to -0.011%, taker fees from 0.05%, 220+ markets, up to 50x leverage. Runs on its own appchain (dYdX Chain).

**Verdict:** Not a target for v1. Volume and ecosystem are real but the market is more crowded with established MMs, and the architectural advantages of Hyperliquid (HyperBFT, deeper on-chain data) make it a better starting point for our project. Revisit if Hyperliquid becomes uncompetitive for some reason.

---

## EdgeX, ApeX, others

Several other perp DEXes exist (EdgeX claims top throughput rankings, ApeX has zero-knowledge L2 and some interesting tokenized stock support). Not researched in depth here. The principle: don't venue-hop. Master one venue (Hyperliquid), then add a second when there's a clear strategic reason (which Extended provides). Don't try to support five.

---

## Decision

**Primary: Hyperliquid.** Reasons:
1. Largest CLOB perp DEX by volume
2. Mature SDKs (official Python SDK is what we use)
3. **Best public on-chain data for studying other MMs.** This is the unique-to-DEX research advantage, and Hyperliquid has it most fully.
4. HIP-3 markets in growth mode give us a lower-competition + lower-fee starting niche
5. Hummingbot already has a working `hyperliquid_perpetual` connector

**Secondary (research only for now): Extended.** Reasons:
1. 0% maker fees at base tier — fee math just works for us out of the box
2. Tokenized equities, FX, commodities — directly addresses your stated interest in trading oil/wheat/equities on a DEX
3. Distinct enough architecture (Starknet, hybrid CLOB) that learning it broadens our perspective

We don't write Extended connector code in v1. We just keep it on the list so when we're ready to expand markets, the research is already done.

**Not pursuing now: Pacifica, dYdX, EdgeX, ApeX.** Pacifica because closed-beta friction. The others because focus matters more than coverage at this stage.

---

## What this means concretely for v1 work

- Connector layer: Hyperliquid only
- Strategy testing: Hyperliquid testnet
- Public MM study: Hyperliquid wallets via HyperTracker, Hyperscreener
- Capital deployment: Hyperliquid mainnet, small size
- Markets: start with majors (BTC, ETH, SOL perps) for liquidity; add a HIP-3 market in growth mode as a side experiment once basic system works
- Extended: read their docs occasionally, save interesting articles to `references/`, but no code

When we hit the v2 expansion question — "we have a working bot on Hyperliquid, where do we go next?" — Extended is the answer. Not until then.

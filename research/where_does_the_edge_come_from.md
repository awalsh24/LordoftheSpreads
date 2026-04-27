# Where Does the Edge Come From?

The most important question in the project. You said it yourself: the hard part isn't the connection to Hyperliquid, it's making this profitable.

This file is a brutally honest accounting of why this might work, why it might not, and how we'll know.

---

## The default outcome is losing money

Most retail market-making bots lose money. This is not a controversial claim — it's documented in the Hummingbot community, in academic studies, in honest postmortems on r/algotrading. The default expectation should be that a v1 bot loses to fees and adverse selection.

Why is the default loss?

- **Adverse selection.** The traders most likely to hit your quotes are the ones who think they have an edge. On average, they do.
- **Fees.** A round-trip captures spread minus fees. If fees are larger than your captured spread (after adverse selection), every trade is a small loss.
- **Inventory risk.** A trending market is the MM's nightmare. You accumulate position on the losing side.
- **Competition.** Even on smaller DEXes, there are other quoters competing for the same flow. Their edge has to come from somewhere — often it's at the expense of weaker quoters.

For a project to work, it needs a specific, articulable answer to "why am I making money when the average bot is losing money?" If we can't answer that, we shouldn't deploy capital.

---

## Possible sources of edge for a small operator

Listed roughly in order of how realistic each is:

### 1. Maker rebates on the right venues

Some venues pay makers. Tier structures reward higher volume with better rates. If we can hit a tier where rebates exceed our adverse selection cost on uninformed flow, we make money mechanically — *as long as we can fill enough volume on both sides*.

This is a real, measurable, non-magical edge. It also has a clear ceiling — there's no rebate-only path to outsized returns. But it's a way to be unambiguously profitable on a thin margin.

**What to research:** current Hyperliquid maker tier schedule, volume thresholds, whether tiers reset. Compare to Pacifica and Extended.

### 2. Picking markets with weak competition

Big institutional MMs concentrate on the highest-volume markets where they can deploy size. The long tail — newer perps, smaller-cap tokens, less popular pairs — gets less attention. Spreads are wider. Adverse selection is lower (fewer informed traders).

The trade-off: lower volume, so fewer fills, so lower absolute profit even with better margins. And these markets are riskier (delistings, manipulation, sudden volume drops).

**What to research:** which Hyperliquid perps have the best spread-to-volatility ratio at moderate volume. Which ones have the least concentrated liquidity provision (i.e., not dominated by 1-2 wallets we can't outcompete).

### 3. Cross-venue arbitrage as a baseline

If Hyperliquid's BTC is at $99,000 and Binance's is at $99,050, we can quote on Hyperliquid and hedge instantly on Binance. We collect the basis ($50 minus fees) on every fill. This isn't pure market making — it's basis trading dressed as market making — but it's a real and documented strategy.

The capital cost is significant: you need accounts and balances on both venues. The execution risk is real: if your hedge fails, you have unhedged inventory at exactly the moment you didn't want it.

**This may be the most realistic v1 edge.** It's not a sexy LLM agent thing, but it's a thing that works.

### 4. Studying public market makers

The on-chain visibility of DEXes is genuinely a research advantage. We can:

- Identify the most consistently profitable MM wallets on Hyperliquid
- Observe their quote behavior over time — when do they widen? Pull? Skew hard?
- Reconstruct their apparent strategy from observed actions
- Adapt techniques without paying for the R&D

This is closer to industrial espionage than algorithmic insight. Still, it's an edge that didn't exist on centralized venues.

**What to research:** which dashboards expose this data (Hyperscan, Hypurrscan, etc.) and how to programmatically pull MM wallet behavior.

### 5. Better regime detection (the agent's contribution)

This is the bet of the whole project. The thesis: classical MM algorithms have one big weakness — they don't change strategy when the market changes character. Quoters that work in calm markets get destroyed during news; quoters that survive news leave money on the table in calm markets. Most retail bots use a single fixed strategy and live with the average.

If an LLM agent can correctly identify regimes and switch strategies, the resulting system should outperform any single fixed strategy. This is testable.

But: this edge is unproven, and it has competition. Pro MMs already have humans (and increasingly ML systems) doing exactly this regime switching. We're betting that an LLM agent can do it well enough to matter, on the kinds of regimes that occur on small DEX markets where pros aren't paying full attention.

**This is the experimental edge.** Worth pursuing, but should not be the *only* edge in the v1 system.

### 6. Niches: prediction markets, tokenized equities, exotics

Polymarket-style prediction markets have unusual dynamics — bounded prices, event-driven volume, idiosyncratic information. Tokenized equities on DEXes are new and pricing is often inefficient (especially during US-market-closed hours). Exotic perps on commodities and forex on a crypto-native venue are strange enough that big firms may not bother.

These niches can sustain better margins precisely because they're weird. Worth a serious look.

---

## Sources of disadvantage for us specifically

To be fair, it goes the other way too:

- **Capital.** Big MMs deploy millions; we'll deploy thousands. Fewer fills, less ability to absorb drawdowns, less negotiating power for fee tiers.
- **Latency.** On a DEX this gap shrinks but doesn't vanish. A pro shop with co-located infra and direct sequencer access still beats a laptop in someone's apartment.
- **Information.** Pros pay for news terminals, order flow data, exchange-side analytics we can't access.
- **Time.** This is a side project; theirs is a full-time business with engineers and risk teams.
- **Survival bias.** The MMs whose strategies we'd study are the ones who survived. Their strategies look like edge but are partly luck. Our strategies, even if comparable, may not survive.

---

## How we'll know if we have edge

Three questions to keep asking:

**1. Is the strategy profitable in backtest after realistic costs and slippage?**

Honest backtests for MM are hard. You have to model:
- Your own quote-fill probability (which depends on your queue position, which depends on the market state)
- Maker rebates with actual tier accounting
- Realistic adverse selection (the fact that fills correlate with wrong-side moves)

A backtest that ignores any of these will look better than reality. Build the backtester to *over*-estimate costs by default. If it still shows positive expected value, that's meaningful.

**2. Does paper trading (live market, fake money) match the backtest?**

If backtest predicts $X/day and paper trading produces $Y/day, the gap is the modeling error. Big gap = backtest is fiction.

**3. Does live trading at minimum size match paper trading?**

If yes, we have edge. If not, the gap is information leakage — our actual orders are giving up information that paper orders weren't, or our quotes are being adversely selected in a way the simulator missed.

We commit serious capital only after passing all three.

---

## A realistic profit picture

If everything works as hoped — solid maker rebates, decent market selection, working agent layer — a small operator deploying single-digit thousands of dollars on a DEX MM bot might realistically target:

- 0.5–2% per month after costs in *good* months
- Negative months are normal; the goal is positive expected value over quarters
- Returns scale roughly linearly with capital up to a ceiling, then sub-linearly as you start affecting your own markets

This is not a get-rich-fast project. The pitch is: a small, durable yield-generating system, deployed on capital that would otherwise sit idle, with an interesting AI research angle as a bonus.

If the goal is 10x returns in a year, we're in the wrong business and should be doing directional strategies (which are riskier and harder to do well, but have higher ceilings).

---

## What to do about all this

Concrete near-term actions, not abstractions:

1. **Build the basic system on a venue with attractive maker rebates.** Maker rebate edge is the cleanest baseline — if we can't even capture that, the agent layer can't save us.
2. **Pick one or two specific markets** based on spread-to-volatility ratio and competitive intensity, not based on what's popular.
3. **Get the cross-venue hedge optional but available** so we have a fallback if pure quote capture isn't profitable.
4. **Treat the agent layer as a research experiment.** Run it in shadow mode (it makes decisions, we record them, but they don't affect trading) for weeks before letting it touch real parameters.
5. **Define kill criteria upfront.** Maximum drawdown that triggers shutdown. Number of consecutive losing weeks that triggers a strategy review. Decide these before going live, not after a bad week.

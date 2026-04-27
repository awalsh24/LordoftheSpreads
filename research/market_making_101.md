# Market Making 101

What an MM actually does, where the money comes from, and where it goes.

## The basic loop

```
1. Estimate fair value of the asset (usually the midpoint, possibly tweaked)
2. Post a bid below fair value, an ask above it
3. Wait for fills
4. When filled, you now have inventory — adjust quotes to manage it
5. Cancel and replace quotes as fair value moves
6. Repeat thousands of times per day
```

That's it. Everything else is detail.

## Where the money comes from

Three sources of revenue, in roughly decreasing order of reliability:

**1. The spread.** If your bid fills at $99,000 and your ask fills at $99,100, you've earned $100 minus fees. Multiply by daily volume. This is the headline number but it's gross — adverse selection eats a chunk of it (see below).

**2. Maker rebates.** Many exchanges *pay* makers a small fee (e.g., 0.01–0.02% per fill) because makers create the liquidity that takers pay for. On some venues, the maker rebate alone can be the entire edge — you don't need the spread to capture, you just need to fill on both sides eventually. Hyperliquid's fee schedule and rebate tiers are critical to study; they change.

**3. Inventory P&L when you're right.** If you're long 10 BTC at $99,000 average and price runs to $99,500, that's $5,000 even if you never sold. Conversely, this is also where you go broke. Most pros try to keep this contribution near zero — they want to make money from spreads, not from being right about price.

## Where the money goes (the four horsemen)

**Adverse selection** is the big one. The traders most likely to hit your quotes are the ones who think they're getting a good deal — i.e., they think your price is wrong. If they're right more often than they're wrong, your "spread capture" is fiction. You bought 1 BTC at $99,000, but only because some informed trader saw price about to drop to $98,500.

This is the central problem of market making. It's why pros invest heavily in detecting *who* is trading — distinguishing informed flow (large institutions, traders with private signals, arbitrageurs) from uninformed flow (retail, randomly motivated traders). MMs *want* to fill uninformed flow and *want to avoid* informed flow.

Practical implication: when you sense the next person about to hit you is informed, you widen your quotes (or pull them entirely) to either get paid more for taking that risk or refuse the trade.

**Inventory risk** is when fills come predominantly on one side because the market is trending. You bought, bought, bought as price fell because every seller hit your bid. Now you're long 50 BTC at $99,000 average and price is at $98,000. The spread you "earned" on each trade is dwarfed by the unrealized loss.

The classical fix is **skew**: as you accumulate long inventory, lower your bid (less aggressive about buying more) AND lower your ask (more aggressive about selling what you have). You're using your quote prices to actively recruit the side of trade you want.

**Fees** eat the marginal trade. If round-trip taker fees are 0.10% and the spread you're capturing is 0.05%, you lose every trade you accidentally take instead of make. Strict post-only discipline matters.

**Technology cost** is everything from servers to data subscriptions to development time. For a small operator this mostly means your own time. But it's a cost.

## The minimum viable mental model

A market maker is in the business of providing liquidity in exchange for compensation. The compensation is the spread plus rebates. The liquidity is the willingness to be the counterparty to anyone who shows up. The risk is that the people who show up know more than you, and the liquidity you provided to them is liquidity *out of* a position you didn't want.

Profitability requires that uninformed flow, plus rebates, exceeds the cost of getting picked off by informed flow. That's the entire equation.

## Skew, in pictures

You have a fair value estimate of $99,050. Naive symmetric quoting:

```
ASK $99,100  (fair + 50)
MID $99,050
BID $99,000  (fair − 50)
inventory: 0
```

Now suppose you got hit on the bid five times — you're long 5 BTC and getting nervous. Skewed quotes:

```
ASK $99,080  (fair + 30)  ← lowered, more eager to sell
MID $99,050
BID $98,970  (fair − 80)  ← lowered, less eager to buy
inventory: +5
```

You've shifted your entire quote downward. You'll sell sooner (good — reduces inventory) and only buy if the price comes way down (good — only adds inventory at a much better entry). This is exactly what Avellaneda-Stoikov computes formally. See `algorithms.md`.

## Cancel-replace and quote dynamics

Real markets don't sit still. Fair value drifts every second. So MMs don't post a single bid and wait — they constantly cancel and re-post quotes to track fair value.

This creates two costs:
- **Cancel rate** — many exchanges throttle the cancel/replace rate or charge for excessive cancellations to discourage spam.
- **Latency exposure** — the moment between cancel-old and post-new is when stale quotes can get picked off by faster traders.

This is why HFT MMs invest heavily in latency. On a DEX where everyone shares the chain's block time, latency advantages are smaller — which is part of why DEX MM is more accessible.

## Adverse selection on a DEX, briefly

DEX MM has its own flavor of adverse selection: **toxic flow** from on-chain arbitrageurs. If Hyperliquid's BTC price is $99,000 and Binance's is $99,100, an arbitrageur will lift Hyperliquid's $99,000 ask and short Binance, locking in $100 risk-free. They didn't hit your quote because they thought BTC was going up. They hit you because Binance was 0.1% richer. From your perspective, you just sold at $99,000 and 200ms later "the market" moves to $99,100 — pure adverse selection.

Defenses include cross-venue price feeds (you should know Binance's price too) and quoting wider when prices diverge. We'll cover this in the algorithms file.

## What an MM actually does in a day

For perspective: a high-frequency MM might do 100,000+ trades a day on a single market, with average per-trade P&L measured in cents to dollars. Edge comes from volume × thin margin. The "make money slowly, lose money fast if you mess up" pattern is exactly why MMs obsess over risk limits and kill switches.

For a small operator the volume will be much lower. The arithmetic still works if you pick markets with edge and don't blow up.

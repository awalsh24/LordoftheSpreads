# Market-Making Algorithms

A tour from naive to advanced. Each algorithm gets a one-line summary, the math (where useful), what it's good for, and what breaks it.

---

## 1. Naive symmetric spread

**What it is:** Quote a fixed spread around the midpoint.

```
bid = mid − spread/2
ask = mid + spread/2
```

**Use it when:** Learning. As a baseline. Never in production for real money.

**Breaks because:** Doesn't manage inventory. If you keep getting filled on one side, you accumulate position with no offsetting adjustment. Eventually a trend wipes you out.

---

## 2. Inventory-skewed spread

**What it is:** Same as naive, but shift quotes based on current position.

```
skew = k × inventory                 (k is a tuning constant)
bid = mid − spread/2 − skew
ask = mid + spread/2 − skew
```

If you're long (inventory > 0), `skew` is positive, both quotes move down — you're more eager to sell, less eager to buy. If you're short, both move up.

**Use it when:** First "real" strategy. Captures the core inventory management idea without heavy math.

**Breaks because:** No volatility awareness. In a calm market your spread is too wide; in a wild market it's too narrow. Doesn't account for adverse selection. Doesn't have a principled way to pick `k` or `spread` — you're guessing.

---

## 3. Avellaneda-Stoikov (the standard)

**What it is:** A 2008 paper ([Avellaneda & Stoikov, "High-frequency trading in a limit order book"](https://www.math.nyu.edu/~avellane/HighFrequencyTrading.pdf)) that derives optimal quotes from first principles, given an assumption about how often quotes get hit and how risk-averse you are.

**The math (simplified):**

Reservation price (your *personal* estimate of fair value, adjusted for inventory):

```
r = s − q × γ × σ² × (T − t)
```

- `s` = current midpoint
- `q` = your inventory (positive = long)
- `γ` = your risk aversion parameter (higher = more cautious)
- `σ²` = volatility squared
- `T − t` = time remaining (often set to a constant for continuous trading)

If you're long, `r < s` — your fair value is below the market, because you'd rather sell than buy. This is your skew, derived rather than guessed.

Optimal half-spread (distance from `r` to your bid and ask):

```
δ = γ × σ² × (T − t) / 2 + (1/γ) × ln(1 + γ/k)
```

- `k` = order arrival intensity (how often quotes near top-of-book get hit)

Quotes:

```
bid = r − δ
ask = r + δ
```

**What each parameter actually does:**

- **γ (risk aversion)** — turn it up when you can't afford to take inventory risk; down when you're aggressive. Affects both skew and spread width.
- **σ (volatility)** — fed in from a recent realized-volatility estimate. Higher vol → wider spread, stronger skew.
- **k (order arrival)** — estimated from recent fill data. Higher k means quotes get hit more often, so you can quote tighter and still capture flow.

**Use it when:** Default starting point for any serious MM strategy. Even when people deviate from it, they typically describe their strategy as "AS plus this modification."

**Breaks because:** Assumes a specific stochastic model of price movement (geometric Brownian motion) that doesn't match real markets, especially during regime changes. The parameters need to be re-estimated frequently. It has no concept of news, of who's trading, or of cross-venue pricing.

This is the natural place for the agent layer to sit on top: the agent estimates `γ` and `σ` for the current regime, and AS handles the moment-to-moment quoting.

---

## 4. Glosten-Milgrom

**What it is:** A 1985 paper that models market making as a problem of distinguishing informed from uninformed traders. Earlier than AS but conceptually deeper. Less commonly used directly; more often as a lens.

**Core idea:** Set bid and ask such that, conditional on being filled, you break even given the probability the trader was informed. If 30% of flow is informed and 70% noise, your bid should be the price that's fair *given* that you got hit (which leans informed).

**Use it when:** Thinking about adverse selection. The math gets used as a Bayesian update on fair value after each fill — "I just got hit, so I should revise my fair value estimate downward."

**Breaks because:** Hard to estimate the probability of informed flow directly. More useful as a mental model than as code.

---

## 5. Guéant-Lehalle-Tapia (multi-asset extension)

**What it is:** A 2013 extension of Avellaneda-Stoikov that handles correlated assets. If you market-make BTC and ETH together, your inventory in one affects optimal quotes for the other.

**Use it when:** Quoting multiple correlated markets simultaneously and wanting them to share risk. Probably v3+ of our project, not v1.

---

## 6. Reinforcement learning approaches

**What they are:** Train a neural network to output quotes, with a reward function tied to P&L minus risk penalties. A growing literature exists.

**Use it when:** You have lots of historical fill data (which you don't, starting out), serious compute, and patience. Backtesting is treacherous because the simulator can't model how your quotes would have changed the market.

**Skeptical take:** RL is fashionable but most published results don't survive contact with live markets. Classical algorithms with smart parameter tuning (which is where the agent layer comes in) usually beat naive RL. We are not going there.

---

## 7. Where the agent fits

The agent doesn't replace these algorithms. It sits *above* them. Two functions:

**Strategy selection.** Calm, range-bound, deep-book regime → tight Avellaneda-Stoikov. Trending market → switch to a different mode that quotes one-sided or pulls quotes during trend continuation. News event → halt entirely.

**Parameter tuning.** Within AS, the agent provides updated `γ` and `σ` based on the regime it perceives. Pre-FOMC announcement: crank `γ` way up (max risk aversion, wider quotes, smaller size).

The Python strategy code is the *skill*; the agent is the *judgment* about when to deploy which skill and how dialed up to make it.

---

## Reading order for actually building this

1. Naive symmetric → write it as a sanity check that the rest of the system works.
2. Inventory-skewed → first strategy that has a chance of not losing money.
3. Avellaneda-Stoikov → the v1 production strategy, with parameters initially set by hand.
4. Add the agent layer feeding parameters into AS.
5. Add a second strategy (probably one-sided trend-following quoter) and have the agent switch between them.

Don't try to skip ahead to RL. Don't try to invent a new algorithm. The edge is in the parameter tuning + regime detection, not in the math of step 3.

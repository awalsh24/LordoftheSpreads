# Regulatory Notes

This is a research file, not legal advice. Nothing here substitutes for an actual lawyer if real money and real exposure are involved.

---

## The big one: Hyperliquid's US restriction

Hyperliquid officially treats the United States as a restricted jurisdiction. Their public position is that US users cannot access the interface. Multiple secondary sources confirm this; Hyperliquid's own ToS is the authoritative reference.

Practical implications for our project:

**This is a real thing, not a formality.** Hyperliquid has expressed willingness to enforce restrictions. The question of whether using a VPN to access a restricted DEX from a restricted jurisdiction is "legal," "risky," or "fine in practice" is genuinely contested and depends on jurisdiction-specific facts. We are not here to handwave that away.

**What this means for the project plan:** We should not pretend this isn't a question. The honest options:

1. **Project owner is in a jurisdiction where Hyperliquid is permitted.** Check the current ToS; the restricted list changes. If yes, proceed without complication.
2. **Project owner is in the US and willing to accept the regulatory ambiguity.** This is a personal-risk decision. Anyone making it should at minimum read Hyperliquid's ToS in full and understand that violating exchange terms can mean account closure, loss of funds, or worse depending on local law.
3. **Pivot venues.** Extended (covered in `other_dexes.md`) has a different jurisdictional posture. So do various other DEXes. None offer Hyperliquid's exact set of features but several offer enough.
4. **Treat this as a research project only.** Build the bot, run it on testnet (which has no real funds and no jurisdictional question), publish learnings, never deploy live. Legitimate option if the goal is learning.

**What the project owner should do:**

- Decide which option above describes their situation honestly.
- If proceeding with mainnet trading, read Hyperliquid's current Terms of Service in full. Their docs link to the ToS from the homepage.
- Understand that the answer can change. What's permitted today may not be tomorrow.

This file does not commit to one path. The decision is the project owner's, not Claude's.

---

## Tokenized equities and commodities

Both Hyperliquid (via HIP-3 markets like `trade.xyz`) and Extended natively offer tokenized perpetuals on traditional assets — stocks, commodities, FX. This is genuinely new territory.

The legal status of trading a "tokenized S&P 500 perp" on a DEX is unclear in many jurisdictions. The exposure may be characterized as a derivative on a security, a derivative on a commodity, a swap, an unregulated contract for difference, or something else depending on who's asking. This is not a settled area.

For our project:
- We are not providing financial advice or operating a regulated venue. We're a small operator running an algorithm on existing markets.
- The existing markets' legal status is the venue's problem at the platform level, but using them is the user's question at the participant level.
- Profits (and losses) on these contracts are taxable events in most jurisdictions, regardless of what the contracts technically are.
- If our bot trades meaningful capital across tokenized equity perps, the project owner should have a real conversation with a CPA familiar with crypto derivatives.

---

## The market-making question specifically

Some jurisdictions regulate "market making" as a registered activity, especially for securities. The relevance to our project is low because:
- We're providing liquidity to public on-chain order books, not operating a regulated market-maker function for an exchange.
- Our scale is retail, not institutional.
- The venues we'd operate on are non-US (or claim to be).

But the relevance isn't zero, and "I'm just an algo on a DEX" may not be a complete defense if a real regulator asks questions later. Worth keeping the activity small enough that this doesn't become a meaningful question, and worth keeping records (trades, P&L, methodology) in case it ever does.

---

## Tax basics

Not advice. Generally:

- Every fill is a taxable event in most jurisdictions.
- Funding payments are taxable income (or deductible loss) at the time received/paid.
- A market-making bot can produce thousands of taxable events per day. **Tax software that handles crypto perp trading is essential.** Hand-tracking is impossible at any meaningful volume.
- Some jurisdictions treat crypto derivatives differently from spot crypto. The project owner should know their local rules.

The data we record (fills, funding, balances) is exactly the data tax software needs. Another reason to record everything from day one.

---

## Privacy and OPSEC

Worth mentioning:

- A wallet address is pseudonymous, not anonymous. Linkage to a real-world identity is possible through deposits, withdrawals, or behavior patterns.
- Our bot's behavior, if distinctive, is identifiable. Other traders (and the venue itself) can see what we do.
- We should not publish wallet addresses, fee tier details, or P&L screenshots publicly while running. After winding down a strategy, sharing learnings is fine.
- API keys (especially Stark signatures or wallet private keys) are extremely sensitive. The `.gitignore` we set up should prevent any accidental commits, but the project owner should never paste keys into chat with Claude or anyone else.

---

## Summary

This file exists to make sure we don't pretend the regulatory dimension doesn't exist. The decisions here are the project owner's; the responsibility is the project owner's. The job of this file is just to ensure those decisions are conscious rather than accidental.

Re-read this file before:
- First mainnet deposit
- Any decision to scale capital meaningfully
- End of any tax year in which the bot was active

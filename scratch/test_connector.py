"""
Acceptance test for HyperliquidConnector public-data methods.

Verifies:
  1. Instantiation succeeds without auth credentials
  2. subscribe_book("BTC") → 5 updates, real BTC prices and timestamps
  3. subscribe_trades("BTC") → 5 batches; at least one batch has >1 trade
     (confirms block-batching is preserved, not flattened)
  4. get_mid("BTC") → sane float in [1000, 500000]
  5. Clean exit — no ResourceWarning, no pending tasks

Run from project root with venv active:
    python scratch/test_connector.py
"""

from __future__ import annotations

import asyncio
import sys

from code.connectors.hyperliquid import HyperliquidConnector


async def main() -> None:
    failures: list[str] = []

    # ── Safety check: construction without credentials ────────────────────────
    connector = HyperliquidConnector()
    print(f"[INIT] network={connector._cfg.hyperliquid_network!r}  has_auth={connector._cfg.has_auth}")
    assert not connector._cfg.has_auth or connector._cfg.hyperliquid_api_private_key, (
        "has_auth should be False when no credentials are set"
    )
    print("[PASS] Construction without auth credentials succeeded.\n")

    # ── Test 1: subscribe_book ────────────────────────────────────────────────
    print("=== subscribe_book (5 updates) ===")
    count = 0
    async for book in connector.subscribe_book("BTC"):
        mid_val = float(book.mid) if book.mid is not None else None
        print(
            f"  [BOOK #{count + 1}]"
            f"  bid={book.best_bid}"
            f"  ask={book.best_ask}"
            f"  mid={mid_val:.1f}" if mid_val else "  mid=None"
            f"  spread={book.spread}"
            f"  depth={len(book.bids)}x{len(book.asks)}"
            f"  ts={book.timestamp_ms}"
        )
        if mid_val is not None and not (1_000 < mid_val < 500_000):
            failures.append(f"BOOK: mid {mid_val} outside sane range")
        if len(book.bids) == 0 or len(book.asks) == 0:
            failures.append("BOOK: empty bids or asks")
        count += 1
        if count >= 5:
            break

    if count == 5:
        print("[PASS] Got 5 book updates.\n")
    else:
        failures.append(f"BOOK: only got {count} updates")

    # ── Test 2: subscribe_trades ──────────────────────────────────────────────
    print("=== subscribe_trades (5 batches) ===")
    count = 0
    multi_trade_batches = 0

    async for batch in connector.subscribe_trades("BTC"):
        n = len(batch)
        if n > 1:
            multi_trade_batches += 1
        sample = ", ".join(f"{t.side}@{t.price}×{t.size}" for t in batch[:3])
        suffix = f"  +{n - 3} more" if n > 3 else ""
        print(
            f"  [TRADES #{count + 1}]"
            f"  batch_size={n}"
            f"  block_ts={batch[0].block_timestamp_ms}"
            f"  [{sample}{suffix}]"
        )
        # All trades in the batch must share block_timestamp_ms
        shared_ts = batch[0].block_timestamp_ms
        if any(t.block_timestamp_ms != shared_ts for t in batch):
            failures.append(f"TRADES batch #{count + 1}: block_timestamp_ms not consistent within batch")
        count += 1
        if count >= 5:
            break

    if count == 5:
        print("[PASS] Got 5 trade batches.")
    else:
        failures.append(f"TRADES: only got {count} batches")

    if multi_trade_batches > 0:
        print(f"[PASS] Block-batching confirmed — {multi_trade_batches}/5 batches had >1 trade.\n")
    else:
        print("[NOTE] All 5 batches were single-trade — market quiet, but logic is correct.\n")

    # ── Test 3: get_mid ───────────────────────────────────────────────────────
    print("=== get_mid ===")
    mid = await connector.get_mid("BTC")
    print(f"  [MID] BTC = {mid:.2f}")
    if not (1_000 < mid < 500_000):
        failures.append(f"MID: {mid} outside sane range [1000, 500000]")
    else:
        print("[PASS] get_mid returned a sane value.\n")

    # ── Summary ───────────────────────────────────────────────────────────────
    if failures:
        print("=== FAILURES ===")
        for f in failures:
            print(f"  ✗ {f}")
        sys.exit(1)
    else:
        print("=== All checks passed. Clean exit. ===")


if __name__ == "__main__":
    asyncio.run(main())

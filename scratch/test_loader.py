"""
Acceptance test for code/data/loader.py (live parquet reader).

What it checks:
  1. iter_trades() loads at least one day of BTC data from data/BTC/
  2. Each yielded item is a list[Trade] (block batch) with correct types
  3. All trades in a batch share block_timestamp_ms
  4. Prints 10 batches so you can eyeball the prices and structure
  5. iter_books() loads book snapshots and prints 5 of them

Run from project root with venv active:
    python scratch/test_loader.py

The script auto-discovers the most recent date under data/BTC/ so it works
regardless of when you ran the recorder.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from code.data.loader import iter_books, iter_trades  # noqa: E402
from code.connectors.types import OrderBook, Trade    # noqa: E402


def find_available_dates(data_dir: Path, coin: str) -> list[date]:
    """Return sorted list of dates that have parquet files."""
    coin_dir = data_dir / coin
    if not coin_dir.exists():
        return []
    dates = []
    for d in coin_dir.iterdir():
        if d.is_dir() and (d / "trades.parquet").exists():
            try:
                dates.append(date.fromisoformat(d.name))
            except ValueError:
                pass
    return sorted(dates)


def main() -> None:
    failures: list[str] = []

    data_dir = Path("data")
    coin = "BTC"

    # ── Discover available dates ───────────────────────────────────────────────
    available = find_available_dates(data_dir, coin)
    if not available:
        print(f"[ERROR] No data found under {data_dir / coin}/. Is the recorder running?")
        sys.exit(1)

    start = available[0]
    end = available[-1]
    print(f"[INFO] Found {len(available)} day(s) of {coin} data: {start} → {end}\n")

    # ── Test: iter_trades ──────────────────────────────────────────────────────
    print("=== iter_trades (first 10 batches) ===")
    batch_count = 0
    trade_count = 0
    multi_trade_batches = 0

    for batch in iter_trades(data_dir, coin, start, end):
        assert isinstance(batch, list), f"Expected list, got {type(batch)}"
        assert len(batch) > 0, "Empty batch yielded"

        for t in batch:
            assert isinstance(t, Trade), f"Expected Trade, got {type(t)}"
            assert t.block_timestamp_ms == batch[0].block_timestamp_ms, (
                f"batch has inconsistent block_timestamp_ms: "
                f"{t.block_timestamp_ms} != {batch[0].block_timestamp_ms}"
            )

        if len(batch) > 1:
            multi_trade_batches += 1

        trade_count += len(batch)

        if batch_count < 10:
            n = len(batch)
            sample = ", ".join(f"{t.side}@{t.price}×{t.size}" for t in batch[:3])
            suffix = f"  +{n - 3} more" if n > 3 else ""
            print(
                f"  [BATCH #{batch_count + 1:>3}]"
                f"  block_ts={batch[0].block_timestamp_ms}"
                f"  size={n}"
                f"  [{sample}{suffix}]"
            )

        batch_count += 1

    if batch_count == 0:
        failures.append("TRADES: zero batches yielded — parquet files may be empty")
    else:
        print(f"\n[PASS] {batch_count} batches, {trade_count} trades total.")
        if multi_trade_batches > 0:
            print(f"[PASS] Block-batching preserved — {multi_trade_batches}/{batch_count} batches had >1 trade.\n")
        else:
            print("[NOTE] All batches single-trade — quiet session, but logic is correct.\n")

    # ── Test: iter_books ───────────────────────────────────────────────────────
    print("=== iter_books (first 5 snapshots) ===")
    book_count = 0

    for book in iter_books(data_dir, coin, start, end):
        assert isinstance(book, OrderBook), f"Expected OrderBook, got {type(book)}"
        assert book.coin == coin, f"Unexpected coin {book.coin!r}"

        mid = float(book.mid) if book.mid is not None else None
        if mid is not None and not (1_000 < mid < 500_000):
            failures.append(f"BOOK: mid {mid} outside sane range at ts={book.timestamp_ms}")

        if book_count < 5:
            mid_str = f"{mid:.1f}" if mid else "None"
            print(
                f"  [BOOK #{book_count + 1:>3}]"
                f"  ts={book.timestamp_ms}"
                f"  bid={book.best_bid}"
                f"  ask={book.best_ask}"
                f"  mid={mid_str}"
                f"  depth={len(book.bids)}x{len(book.asks)}"
            )

        book_count += 1
        if book_count >= 5:
            break  # just spot-check; don't load everything for this test

    if book_count == 0:
        failures.append("BOOKS: zero snapshots yielded")
    else:
        print(f"\n[PASS] Got {book_count}+ book snapshots.\n")

    # ── Summary ────────────────────────────────────────────────────────────────
    if failures:
        print("=== FAILURES ===")
        for f in failures:
            print(f"  ✗ {f}")
        sys.exit(1)
    else:
        print("=== All checks passed. ===")


if __name__ == "__main__":
    main()

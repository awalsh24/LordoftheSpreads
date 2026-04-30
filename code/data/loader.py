"""
Unified data loader for recorded market data.

Reads live parquet files produced by code/data_recorder/recorder.py and
returns canonical OrderBook / list[Trade] objects from code/connectors/types.py.

Archive format (lz4-compressed, from c-i/hyperliquid-historical or similar) is
stubbed with NotImplementedError until the format is confirmed by your partner.

Live parquet schemas (written by recorder.py):
  books.parquet:  received_at_ms (int64), coin (str), time (int64), levels (str JSON)
  trades.parquet: received_at_ms (int64), coin (str), time (int64), side (str "B"/"A"),
                  px (str), sz (str), hash (str), tid (int64)

Trade batches are reconstructed by grouping rows that share the same `time`
value (exchange block timestamp). This preserves the block-batch boundary that
the backtester needs for queue-position modeling.
"""

from __future__ import annotations

import heapq
import json
from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal
from itertools import groupby
from pathlib import Path
from typing import Literal

import pyarrow.parquet as pq

from ..connectors.types import OrderBook, PriceLevel, Side, Trade


# ── Public API ─────────────────────────────────────────────────────────────────


def iter_books(
    data_dir: Path,
    coin: str,
    start: date,
    end: date,
    source: Literal["live", "archive"] = "live",
) -> Iterator[OrderBook]:
    """
    Yield OrderBook snapshots for coin between start and end (inclusive).

    source="live"    — reads from data/{coin}/{YYYY-MM-DD}/books.parquet
    source="archive" — raises NotImplementedError (format not yet confirmed)

    Results are yielded in ascending timestamp_ms order within each day.
    Across days, order is guaranteed because dates are iterated in order.
    """
    if source == "archive":
        raise NotImplementedError(
            "Archive loader not implemented. "
            "Format from c-i/hyperliquid-historical needs to be confirmed. "
            "Use source='live' to read from recorder parquet files."
        )
    yield from _iter_live_books(data_dir, coin, start, end)


def iter_trades(
    data_dir: Path,
    coin: str,
    start: date,
    end: date,
    source: Literal["live", "archive"] = "live",
) -> Iterator[list[Trade]]:
    """
    Yield trade batches (one list[Trade] per block) for coin between start and end.

    source="live"    — reads from data/{coin}/{YYYY-MM-DD}/trades.parquet
    source="archive" — raises NotImplementedError (format not yet confirmed)

    Batches are grouped by block_timestamp_ms (the `time` column in parquet).
    Within a batch, row order from parquet is preserved (arbitrary per Hyperliquid).
    """
    if source == "archive":
        raise NotImplementedError(
            "Archive loader not implemented. "
            "Format from c-i/hyperliquid-historical needs to be confirmed. "
            "Use source='live' to read from recorder parquet files."
        )
    yield from _iter_live_trades(data_dir, coin, start, end)


def iter_books_merged(
    data_dir: Path,
    coin: str,
    start: date,
    end: date,
) -> Iterator[OrderBook]:
    """
    Merge live and archive book streams by timestamp_ms.

    Archive is currently stubbed, so this just passes through the live stream.
    Once archive is implemented, this will use heapq.merge on both sources.
    """
    yield from iter_books(data_dir, coin, start, end, source="live")


def iter_trades_merged(
    data_dir: Path,
    coin: str,
    start: date,
    end: date,
) -> Iterator[list[Trade]]:
    """
    Merge live and archive trade streams by block_timestamp_ms.

    Archive is currently stubbed, so this just passes through the live stream.
    Once archive is implemented, this uses heapq.merge keyed on batch[0].block_timestamp_ms.
    """
    yield from iter_trades(data_dir, coin, start, end, source="live")


# ── Live parquet readers ───────────────────────────────────────────────────────


def _date_range(start: date, end: date) -> Iterator[date]:
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _iter_live_books(
    data_dir: Path,
    coin: str,
    start: date,
    end: date,
) -> Iterator[OrderBook]:
    for day in _date_range(start, end):
        path = data_dir / coin / day.strftime("%Y-%m-%d") / "books.parquet"
        if not path.exists():
            continue
        table = pq.read_table(path)
        # Sort ascending by exchange timestamp so caller gets chronological order.
        table = table.sort_by("time")
        for row in table.to_pylist():
            yield _row_to_orderbook(row)


def _iter_live_trades(
    data_dir: Path,
    coin: str,
    start: date,
    end: date,
) -> Iterator[list[Trade]]:
    for day in _date_range(start, end):
        path = data_dir / coin / day.strftime("%Y-%m-%d") / "trades.parquet"
        if not path.exists():
            continue
        table = pq.read_table(path)
        table = table.sort_by("time")
        rows = table.to_pylist()
        # Group by block timestamp (exchange time = block time for Hyperliquid).
        # All rows sharing the same `time` are co-block.
        for block_ts, group in groupby(rows, key=lambda r: r["time"]):
            batch = [_row_to_trade(r, block_ts) for r in group]
            if batch:
                yield batch


# ── Row translators ────────────────────────────────────────────────────────────
# These are the only functions allowed to touch raw parquet row dicts.


def _row_to_orderbook(row: dict) -> OrderBook:
    """Translate a parquet row from books.parquet into an OrderBook."""
    raw_levels: list[list[dict]] = json.loads(row["levels"])

    def parse_side(levels: list[dict]) -> list[PriceLevel]:
        return [
            PriceLevel(
                price=Decimal(lvl["px"]),
                size=Decimal(lvl["sz"]),
                num_orders=int(lvl["n"]),
            )
            for lvl in levels
        ]

    bids = parse_side(raw_levels[0] if len(raw_levels) > 0 else [])
    asks = parse_side(raw_levels[1] if len(raw_levels) > 1 else [])

    return OrderBook(
        coin=row["coin"],
        timestamp_ms=int(row["time"]),
        received_at_ms=int(row["received_at_ms"]),
        bids=bids,
        asks=asks,
    )


def _row_to_trade(row: dict, block_ts: int) -> Trade:
    """Translate a parquet row from trades.parquet into a Trade."""
    return Trade(
        coin=row["coin"],
        price=Decimal(row["px"]),
        size=Decimal(row["sz"]),
        side=Side.BUY if row["side"] == "B" else Side.SELL,
        timestamp_ms=int(row["time"]),
        block_timestamp_ms=block_ts,
        received_at_ms=int(row["received_at_ms"]),
        trade_id=int(row["tid"]),
        tx_hash=str(row["hash"]),
    )

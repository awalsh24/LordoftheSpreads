# Data Recorder

**Status:** not yet implemented. This is the first coding task. See `CLAUDE.md` for the spec.

## Purpose

Subscribe to Hyperliquid's WebSocket feeds (L2 book + trades) for our target coins and write the data to parquet files on disk. Runs continuously in the background. The data accumulated here is what the backtester replays later.

## Goal of the v1 implementation

A single Python script (`recorder.py`) that:

1. Reads the coin list and data directory from environment variables
2. Connects to Hyperliquid's mainnet WebSocket (read-only public data, no auth needed)
3. Subscribes to `l2Book` and `trades` for each coin
4. Writes incoming messages to parquet files, partitioned by coin and date
5. Handles disconnects with exponential backoff and reconnects gracefully
6. Logs minimal status to stdout (every N minutes: "still alive, X books and Y trades captured today")
7. Flushes to disk on a sane interval (every minute or every N messages, whichever comes first)
8. Can be Ctrl-C'd cleanly without corrupting the current parquet file

## Non-goals (for v1)

- No fancy schema management. Use Hyperliquid's native message format and add a `received_at_ms` timestamp column.
- No fancy storage layout. `data/{coin}/{YYYY-MM-DD}/books.parquet` and `trades.parquet` is fine.
- No metrics, no Prometheus, no alerting. We can add that later. Stdout is fine.
- No reading the data back. That's the backtester's job.

## Files this will produce

```
data/
  BTC/
    2026-04-27/
      books.parquet
      trades.parquet
    2026-04-28/
      books.parquet
      trades.parquet
  ETH/
    ...
```

The `data/` directory is gitignored — large, frequently changing, often sensitive in aggregate.

## Why this is the first task

Everything downstream needs historical data. We don't have any yet. The longer we wait to start, the less data we'll have when we need it.

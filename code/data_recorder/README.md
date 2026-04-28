# Data Recorder

**Status:** implemented. See `recorder.py`.

## Purpose

Subscribe to Hyperliquid's WebSocket feeds (L2 book + trades) for our target coins and write the data to parquet files on disk. Runs continuously in the background. The data accumulated here is what the backtester replays later.

## Output files

Three files are written per coin per day:

```
data/
  BTC/
    2026-04-28/
      books.parquet       ← full L2 snapshots
      trades.parquet      ← public trade tape
      book_deltas.parquet ← per-level size changes between consecutive snapshots
  ETH/
    ...
```

### books.parquet

Full L2 order book snapshots, written on every WebSocket push (~0.5s cadence on active markets).

| column | type | description |
|---|---|---|
| received_at_ms | int64 | wall-clock time we received the message |
| coin | string | e.g. "BTC" |
| time | int64 | exchange timestamp in the message |
| levels | string | JSON-encoded `[[bids...], [asks...]]`, each entry `{px, sz, n}` |

### trades.parquet

Every public trade that printed on the exchange for the subscribed coins.

| column | type | description |
|---|---|---|
| received_at_ms | int64 | wall-clock time we received the message |
| coin | string | |
| time | int64 | exchange timestamp of the trade |
| side | string | "B" (buy/aggressor) or "A" (sell/aggressor) |
| px | string | trade price |
| sz | string | trade size |
| hash | string | transaction hash |
| tid | int64 | trade ID |

### book_deltas.parquet

Per-level size changes computed by diffing consecutive L2 snapshots. Used by the backtester for queue-position modeling: by replaying what size was at each price level and how it changed, we can infer approximately where in the queue our simulated orders would have sat, rather than assuming a naive "if price traded there, we filled" model (see `research/backtesting_mm.md` for why this matters).

| column | type | description |
|---|---|---|
| timestamp_ms | int64 | wall-clock time of the snapshot that produced this delta |
| coin | string | |
| side | string | "bid" or "ask" |
| price | string | price level (raw string, no float rounding) |
| size_change | float64 | new_size − prev_size (negative = size decreased) |
| prev_size | float64 | size at this level in the previous snapshot (0 if level is new) |
| new_size | float64 | size at this level in the new snapshot (0 if level was removed) |

**Note on the first snapshot:** the first L2 snapshot received after connecting does not emit any delta rows — it just populates the internal cache. This is intentional: the first snapshot represents the book state at connection time, not a change from a known prior state. Treat the first entry in `books.parquet` as the baseline; `book_deltas.parquet` only contains changes *after* that baseline.

## Running

From the project root with the virtualenv active:

```bash
python code/data_recorder/recorder.py
```

Config is read from `.env`. Key variables:

| variable | default | description |
|---|---|---|
| RECORD_COINS | BTC,ETH,SOL | comma-separated list of coins to subscribe |
| DATA_DIR | ./data | where to write parquet files |

The recorder connects to the Hyperliquid mainnet public WebSocket. No API keys required — all subscribed data is public read-only.

## Behavior

- Flushes to disk every 60 seconds or every 1,000 buffered messages, whichever comes first
- Reconnects on disconnect with exponential backoff (1s → 2s → 4s … max 60s)
- Logs "still_alive" every 5 minutes with today's book snapshot, trade, and delta counts
- Ctrl-C / SIGTERM triggers a clean shutdown that flushes all buffers before exiting
- Data directory is gitignored — parquet files are never committed

## Why this is the first task

Everything downstream needs historical data. The longer we wait to start recording, the less data we have when we need it for backtesting.

"""
Hyperliquid data recorder.

Subscribes to l2Book and trades WebSocket feeds for configured coins and
writes incoming messages to date-partitioned parquet files.

Run from the project root:
    python code/data_recorder/recorder.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import structlog
from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log: structlog.stdlib.BoundLogger = structlog.get_logger()

# ── Config ─────────────────────────────────────────────────────────────────────


class RecorderConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    record_coins: list[str] = ["BTC", "ETH", "SOL"]
    data_dir: Path = Path("data")
    ws_url: str = "wss://api.hyperliquid.xyz/ws"

    flush_interval_s: int = 60
    flush_every_n: int = 1000
    status_interval_s: int = 300

    backoff_base_s: float = 1.0
    backoff_max_s: float = 60.0

    @field_validator("record_coins", mode="before")
    @classmethod
    def _parse_coins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [c.strip().upper() for c in v.split(",") if c.strip()]
        return [str(c).upper() for c in v]


# ── Parquet schemas ────────────────────────────────────────────────────────────

_BOOK_SCHEMA = pa.schema(
    [
        ("received_at_ms", pa.int64()),
        ("coin", pa.string()),
        ("time", pa.int64()),
        ("levels", pa.string()),  # JSON-encoded [[bids...], [asks...]]
    ]
)

_TRADE_SCHEMA = pa.schema(
    [
        ("received_at_ms", pa.int64()),
        ("coin", pa.string()),
        ("time", pa.int64()),
        ("side", pa.string()),
        ("px", pa.string()),
        ("sz", pa.string()),
        ("hash", pa.string()),
        ("tid", pa.int64()),
    ]
)

_DELTA_SCHEMA = pa.schema(
    [
        ("timestamp_ms", pa.int64()),
        ("coin", pa.string()),
        ("side", pa.string()),       # "bid" or "ask"
        ("price", pa.string()),      # raw string from exchange to avoid float precision loss
        ("size_change", pa.float64()),
        ("prev_size", pa.float64()),
        ("new_size", pa.float64()),
    ]
)


# ── Parquet writer ─────────────────────────────────────────────────────────────


class ParquetWriter:
    """Buffers records in memory and flushes to parquet files on demand."""

    def __init__(self, data_dir: Path, flush_every_n: int) -> None:
        self._data_dir = data_dir
        self._flush_every_n = flush_every_n
        self._books: list[dict[str, Any]] = []
        self._trades: list[dict[str, Any]] = []
        self._deltas: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

        # Previous book state per coin, used for delta computation.
        # Structure: {coin: {"bid": {price_str: size_float}, "ask": {...}}}
        self._prev_books: dict[str, dict[str, dict[str, float]]] = {}

    async def add_book(self, coin: str, msg: dict[str, Any]) -> None:
        async with self._lock:
            now = _now_ms()
            self._books.append(
                {
                    "received_at_ms": now,
                    "coin": coin,
                    "time": int(msg.get("time", 0)),
                    "levels": json.dumps(msg.get("levels", [])),
                }
            )

            # Compute deltas against the previous snapshot and update cache.
            new_deltas = _compute_deltas(coin, now, msg.get("levels", []), self._prev_books)
            self._deltas.extend(new_deltas)

            if len(self._books) >= self._flush_every_n:
                await self._flush_books_locked()
            if len(self._deltas) >= self._flush_every_n:
                await self._flush_deltas_locked()

    async def add_trades(self, coin: str, trades: list[dict[str, Any]]) -> None:
        async with self._lock:
            now = _now_ms()
            for t in trades:
                self._trades.append(
                    {
                        "received_at_ms": now,
                        "coin": coin,
                        "time": int(t.get("time", 0)),
                        "side": str(t.get("side", "")),
                        "px": str(t.get("px", "")),
                        "sz": str(t.get("sz", "")),
                        "hash": str(t.get("hash", "")),
                        "tid": int(t.get("tid", 0)),
                    }
                )
            if len(self._trades) >= self._flush_every_n:
                await self._flush_trades_locked()

    async def flush(self) -> tuple[int, int, int]:
        """Flush all buffers. Returns (books_written, trades_written, deltas_written)."""
        async with self._lock:
            b = await self._flush_books_locked()
            t = await self._flush_trades_locked()
            d = await self._flush_deltas_locked()
        return b, t, d

    # internal helpers — must be called while _lock is held

    async def _flush_books_locked(self) -> int:
        if not self._books:
            return 0
        rows, self._books = self._books, []
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _write_parquet, rows, "books", _BOOK_SCHEMA, self._data_dir)
        return len(rows)

    async def _flush_trades_locked(self) -> int:
        if not self._trades:
            return 0
        rows, self._trades = self._trades, []
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _write_parquet, rows, "trades", _TRADE_SCHEMA, self._data_dir)
        return len(rows)

    async def _flush_deltas_locked(self) -> int:
        if not self._deltas:
            return 0
        rows, self._deltas = self._deltas, []
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _write_parquet, rows, "book_deltas", _DELTA_SCHEMA, self._data_dir)
        return len(rows)


def _compute_deltas(
    coin: str,
    now_ms: int,
    levels: list[Any],
    prev_books: dict[str, dict[str, dict[str, float]]],
) -> list[dict[str, Any]]:
    """
    Diff the new L2 snapshot against the cached previous snapshot for this coin.

    First snapshot per coin: we skip emitting deltas and just populate the cache.
    This is intentional — the first snapshot represents the state of the book at
    the moment we connected, not a change from a known prior state. Emitting it
    as prev_size=0 for every level would mislead the backtester into thinking all
    liquidity appeared simultaneously. Downstream code should treat the first
    snapshot in books.parquet as the baseline, and use book_deltas.parquet only
    for changes after that baseline is established.
    """
    side_map = [("bid", 0), ("ask", 1)]  # levels[0] = bids, levels[1] = asks

    # Parse the new snapshot into {side: {price_str: size_float}}
    new_state: dict[str, dict[str, float]] = {"bid": {}, "ask": {}}
    for side_name, idx in side_map:
        if idx >= len(levels):
            continue
        for entry in levels[idx]:
            px = str(entry.get("px", ""))
            sz_raw = entry.get("sz", "0")
            if px:
                new_state[side_name][px] = float(sz_raw)

    if coin not in prev_books:
        # First snapshot: populate cache only, emit nothing.
        prev_books[coin] = new_state
        return []

    prev_state = prev_books[coin]
    deltas: list[dict[str, Any]] = []

    for side_name in ("bid", "ask"):
        old_side = prev_state.get(side_name, {})
        new_side = new_state.get(side_name, {})
        changed_prices = set(old_side) | set(new_side)

        for px in changed_prices:
            old_sz = old_side.get(px, 0.0)
            new_sz = new_side.get(px, 0.0)
            if old_sz != new_sz:
                deltas.append(
                    {
                        "timestamp_ms": now_ms,
                        "coin": coin,
                        "side": side_name,
                        "price": px,
                        "size_change": new_sz - old_sz,
                        "prev_size": old_sz,
                        "new_size": new_sz,
                    }
                )

    # Update cache with new state
    prev_books[coin] = new_state
    return deltas


def _write_parquet(
    rows: list[dict[str, Any]],
    kind: str,
    schema: pa.Schema,
    data_dir: Path,
) -> None:
    """Write rows to parquet, appending to any existing file for that coin/date."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        # book_deltas uses timestamp_ms; books and trades use received_at_ms
        ts = row.get("received_at_ms") or row.get("timestamp_ms", 0)
        key = (row["coin"], _ms_to_date(int(ts)))
        groups.setdefault(key, []).append(row)

    for (coin, date), group in groups.items():
        path = data_dir / coin / date / f"{kind}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        table = pa.Table.from_pylist(group, schema=schema)
        if path.exists():
            existing = pq.read_table(path, schema=schema)
            table = pa.concat_tables([existing, table])
        pq.write_table(table, path, compression="snappy")


# ── Recorder ───────────────────────────────────────────────────────────────────


class HyperliquidRecorder:
    def __init__(self, cfg: RecorderConfig) -> None:
        self._cfg = cfg
        self._writer = ParquetWriter(cfg.data_dir, cfg.flush_every_n)
        self._stop = asyncio.Event()
        self._books_today = 0
        self._trades_today = 0
        self._deltas_today = 0
        self._current_date = _today_utc()

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        flush_task = asyncio.create_task(self._flush_loop(), name="flush")
        status_task = asyncio.create_task(self._status_loop(), name="status")
        try:
            await self._connect_loop()
        finally:
            flush_task.cancel()
            status_task.cancel()
            await asyncio.gather(flush_task, status_task, return_exceptions=True)
            b, t, d = await self._writer.flush()
            log.info("final_flush", books=b, trades=t, deltas=d)

    async def _connect_loop(self) -> None:
        import websockets

        backoff = self._cfg.backoff_base_s
        while not self._stop.is_set():
            try:
                log.info("connecting", url=self._cfg.ws_url, coins=self._cfg.record_coins)
                async with websockets.connect(
                    self._cfg.ws_url,
                    ping_interval=20,
                    ping_timeout=10,
                ) as ws:
                    backoff = self._cfg.backoff_base_s
                    await self._subscribe_all(ws)
                    await self._read_loop(ws)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                if self._stop.is_set():
                    break
                log.warning("disconnected", error=str(exc), reconnect_in_s=round(backoff, 1))
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 2, self._cfg.backoff_max_s)

    async def _subscribe_all(self, ws: Any) -> None:
        for coin in self._cfg.record_coins:
            for sub_type in ("l2Book", "trades"):
                payload = json.dumps(
                    {"method": "subscribe", "subscription": {"type": sub_type, "coin": coin}}
                )
                await ws.send(payload)
        log.info("subscribed", coins=self._cfg.record_coins, feeds=["l2Book", "trades"])

    async def _read_loop(self, ws: Any) -> None:
        async for raw in ws:
            if self._stop.is_set():
                break
            try:
                await self._dispatch(json.loads(raw))
            except Exception as exc:
                log.warning("dispatch_error", error=str(exc))

    async def _dispatch(self, msg: dict[str, Any]) -> None:
        channel = msg.get("channel", "")
        data = msg.get("data", {})

        if channel == "l2Book":
            coin = data.get("coin", "") if isinstance(data, dict) else ""
            if coin:
                await self._writer.add_book(coin, data)
                self._books_today += 1
                # deltas_today tracks delta rows, not book snapshots; updated in flush log

        elif channel == "trades":
            if isinstance(data, list) and data:
                coin = data[0].get("coin", "")
                if coin:
                    await self._writer.add_trades(coin, data)
                    self._trades_today += len(data)

    async def _flush_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._cfg.flush_interval_s)
            except asyncio.TimeoutError:
                pass
            b, t, d = await self._writer.flush()
            if b or t or d:
                self._deltas_today += d
                log.debug("flushed", books=b, trades=t, deltas=d)

    async def _status_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._cfg.status_interval_s)
            except asyncio.TimeoutError:
                pass
            if self._stop.is_set():
                break
            today = _today_utc()
            if today != self._current_date:
                self._current_date = today
                self._books_today = 0
                self._trades_today = 0
                self._deltas_today = 0
            log.info(
                "still_alive",
                books_today=self._books_today,
                trades_today=self._trades_today,
                deltas_today=self._deltas_today,
                coins=self._cfg.record_coins,
            )


# ── Helpers ────────────────────────────────────────────────────────────────────


def _now_ms() -> int:
    return int(time.time() * 1000)


def _ms_to_date(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── Entry point ────────────────────────────────────────────────────────────────


def main() -> None:
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
    )

    load_dotenv()
    cfg = RecorderConfig()
    log.info(
        "recorder_starting",
        coins=cfg.record_coins,
        data_dir=str(cfg.data_dir),
        ws_url=cfg.ws_url,
    )

    recorder = HyperliquidRecorder(cfg)
    loop = asyncio.new_event_loop()

    def _shutdown(sig: signal.Signals) -> None:
        log.info("shutdown_requested", signal=sig.name)
        loop.call_soon_threadsafe(recorder.stop)

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown, sig)

    try:
        loop.run_until_complete(recorder.run())
    finally:
        loop.close()

    log.info("recorder_stopped")


if __name__ == "__main__":
    main()

"""
Hyperliquid connector — implements ExchangeConnector for Hyperliquid perps.

Public-data methods (subscribe_book, subscribe_trades, get_mid) are fully
implemented using the official Python SDK and raw WebSockets.

Auth methods (place_order, cancel_order, subscribe_fills, get_position,
get_balance) raise NotImplementedError until Track A (Hummingbot eval) is
complete and a funded testnet account is available to verify the full
order lifecycle end-to-end.

Translation between Hyperliquid's raw wire format and our canonical types
lives entirely in this file. Nothing above this file ever sees raw exchange
data.
"""

from __future__ import annotations

import asyncio
import json
import time
from decimal import Decimal
from typing import AsyncIterator, Literal

import structlog
import websockets
from hyperliquid.info import Info
from pydantic_settings import BaseSettings, SettingsConfigDict

from .base import ConnectorAuthError, ConnectorNetworkError, ConnectorVenueError
from .types import (
    Balance,
    Fill,
    Order,
    OrderBook,
    OrderId,
    Position,
    PriceLevel,
    Side,
    Trade,
)

log: structlog.stdlib.BoundLogger = structlog.get_logger()

_MAINNET_WS = "wss://api.hyperliquid.xyz/ws"
_TESTNET_WS = "wss://api.hyperliquid-testnet.xyz/ws"
_MAINNET_API = "https://api.hyperliquid.xyz"
_TESTNET_API = "https://api.hyperliquid-testnet.xyz"


# ── Config ─────────────────────────────────────────────────────────────────────


class HyperliquidConfig(BaseSettings):
    """
    Reads from .env. All fields match the names in .env.example so the same
    file serves both the recorder and the connector.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    hyperliquid_network: Literal["mainnet", "testnet"] = "testnet"
    hyperliquid_main_address: str = ""
    hyperliquid_api_wallet_address: str = ""
    hyperliquid_api_private_key: str = ""

    backoff_base_s: float = 1.0
    backoff_max_s: float = 60.0

    @property
    def ws_url(self) -> str:
        return _TESTNET_WS if self.hyperliquid_network == "testnet" else _MAINNET_WS

    @property
    def api_url(self) -> str:
        return _TESTNET_API if self.hyperliquid_network == "testnet" else _MAINNET_API

    @property
    def has_auth(self) -> bool:
        return bool(self.hyperliquid_api_private_key and self.hyperliquid_main_address)


# ── Wire-format parsers ────────────────────────────────────────────────────────
# These are the only functions allowed to touch raw Hyperliquid JSON.


def _parse_book(data: dict, received_at_ms: int) -> OrderBook:
    """Translate a raw l2Book WebSocket message into an OrderBook."""
    raw_levels: list[list[dict]] = data.get("levels", [[], []])

    def parse_side(levels: list[dict]) -> list[PriceLevel]:
        return [
            PriceLevel(
                price=Decimal(lvl["px"]),
                size=Decimal(lvl["sz"]),
                num_orders=int(lvl["n"]),
            )
            for lvl in levels
        ]

    return OrderBook(
        coin=data["coin"],
        timestamp_ms=int(data["time"]),
        received_at_ms=received_at_ms,
        bids=parse_side(raw_levels[0] if len(raw_levels) > 0 else []),
        asks=parse_side(raw_levels[1] if len(raw_levels) > 1 else []),
    )


def _parse_trades(raw_trades: list[dict], received_at_ms: int) -> list[Trade]:
    """
    Translate a raw trades WebSocket message into a list[Trade].

    All trades in the list share the same exchange timestamp — they are
    co-block. block_timestamp_ms is set to that shared timestamp so
    consumers can identify batch boundaries without inspecting the list
    structure itself.
    """
    if not raw_trades:
        return []

    # All trades in a WS batch share the same exchange timestamp (co-block).
    block_ts = int(raw_trades[0]["time"])

    return [
        Trade(
            coin=t["coin"],
            price=Decimal(str(t["px"])),
            size=Decimal(str(t["sz"])),
            side=Side.BUY if t["side"] == "B" else Side.SELL,
            timestamp_ms=int(t["time"]),
            block_timestamp_ms=block_ts,
            received_at_ms=received_at_ms,
            trade_id=int(t["tid"]),
            tx_hash=str(t["hash"]),
        )
        for t in raw_trades
    ]


# ── Connector ──────────────────────────────────────────────────────────────────


class HyperliquidConnector:
    """
    Hyperliquid connector implementing the ExchangeConnector Protocol.

    Each subscribe_* call opens its own WebSocket connection and manages
    reconnects independently. This is intentional: subscriptions are
    independent data streams and should not share failure domains.
    """

    def __init__(self, cfg: HyperliquidConfig | None = None) -> None:
        self._cfg = cfg or HyperliquidConfig()

    # ── Public data ────────────────────────────────────────────────────────────

    def subscribe_book(self, coin: str) -> AsyncIterator[OrderBook]:
        return self._book_stream(coin)

    async def _book_stream(self, coin: str) -> AsyncIterator[OrderBook]:  # type: ignore[override]
        """Async generator — yields OrderBook on each l2Book WS push."""
        sub = json.dumps(
            {"method": "subscribe", "subscription": {"type": "l2Book", "coin": coin}}
        )
        backoff = self._cfg.backoff_base_s

        while True:
            try:
                async with websockets.connect(
                    self._cfg.ws_url, ping_interval=20, ping_timeout=10
                ) as ws:
                    await ws.send(sub)
                    backoff = self._cfg.backoff_base_s
                    log.debug("book_subscribed", coin=coin, network=self._cfg.hyperliquid_network)

                    async for raw in ws:
                        msg = json.loads(raw)
                        if msg.get("channel") == "l2Book":
                            data = msg.get("data", {})
                            if data.get("coin") == coin:
                                yield _parse_book(data, _now_ms())

            except Exception as exc:
                log.warning(
                    "book_ws_reconnecting",
                    coin=coin,
                    error=str(exc),
                    backoff_s=round(backoff, 1),
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self._cfg.backoff_max_s)

    def subscribe_trades(self, coin: str) -> AsyncIterator[list[Trade]]:
        return self._trades_stream(coin)

    async def _trades_stream(self, coin: str) -> AsyncIterator[list[Trade]]:  # type: ignore[override]
        """Async generator — yields list[Trade] per block batch."""
        sub = json.dumps(
            {"method": "subscribe", "subscription": {"type": "trades", "coin": coin}}
        )
        backoff = self._cfg.backoff_base_s

        while True:
            try:
                async with websockets.connect(
                    self._cfg.ws_url, ping_interval=20, ping_timeout=10
                ) as ws:
                    await ws.send(sub)
                    backoff = self._cfg.backoff_base_s
                    log.debug("trades_subscribed", coin=coin, network=self._cfg.hyperliquid_network)

                    async for raw in ws:
                        msg = json.loads(raw)
                        if msg.get("channel") == "trades":
                            raw_trades = msg.get("data", [])
                            if raw_trades:
                                batch = _parse_trades(raw_trades, _now_ms())
                                if batch:
                                    yield batch

            except Exception as exc:
                log.warning(
                    "trades_ws_reconnecting",
                    coin=coin,
                    error=str(exc),
                    backoff_s=round(backoff, 1),
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self._cfg.backoff_max_s)

    async def get_mid(self, coin: str) -> float:
        """Fetch BTC mid price via REST. Runs sync SDK call in executor."""
        loop = asyncio.get_running_loop()
        try:
            info = Info(self._cfg.api_url, skip_ws=True)
            mids: dict[str, str] = await loop.run_in_executor(None, info.all_mids)
        except Exception as exc:
            raise ConnectorNetworkError(f"get_mid failed: {exc}") from exc

        if coin not in mids:
            raise ConnectorVenueError(f"coin {coin!r} not in /info mids response")

        return float(mids[coin])

    # ── Auth methods — not yet implemented ────────────────────────────────────
    # These require a funded account and a verified Hummingbot connector eval
    # (Track A). Stubs raise NotImplementedError with implementation notes
    # so callers get a clear message rather than an AttributeError.

    async def place_order(self, order: Order) -> OrderId:
        raise NotImplementedError(
            "place_order not yet implemented. "
            "Requires: (1) funded testnet account, (2) Track A Hummingbot eval "
            "complete, (3) API wallet authorized on venue. See Step 4 in CLAUDE.md."
        )

    async def cancel_order(self, order_id: OrderId, coin: str) -> None:
        raise NotImplementedError(
            "cancel_order not yet implemented. Depends on place_order being live first."
        )

    def subscribe_fills(self) -> AsyncIterator[Fill]:
        raise ConnectorAuthError(  # type: ignore[return-value]
            "subscribe_fills requires a configured API wallet (HYPERLIQUID_MAIN_ADDRESS "
            "and HYPERLIQUID_API_PRIVATE_KEY). Set these in .env and implement the "
            "userFills WebSocket subscription in this method."
        )

    async def get_position(self, coin: str) -> Position:
        raise NotImplementedError(
            "get_position not yet implemented. "
            "Will use Info.user_state(main_address) once auth is configured."
        )

    async def get_balance(self) -> Balance:
        raise NotImplementedError(
            "get_balance not yet implemented. "
            "Will use Info.user_state(main_address) once auth is configured."
        )


# ── Helpers ────────────────────────────────────────────────────────────────────


def _now_ms() -> int:
    return int(time.time() * 1000)

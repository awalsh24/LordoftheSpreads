"""
ExchangeConnector Protocol and exception hierarchy.

Callers (strategy layer, agent layer, backtester) import from here.
They never import from connector implementations directly.

Adding a new venue = new file in code/connectors/, implements this Protocol.
Swapping the implementation behind an existing venue = zero changes above this layer.
"""

from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from .types import Balance, Order, OrderBook, OrderId, Position, Trade


# ── Exception hierarchy ────────────────────────────────────────────────────────


class ConnectorError(Exception):
    """Base class for all connector errors."""


class ConnectorAuthError(ConnectorError):
    """
    Credentials are missing, invalid, or not authorized on the venue.

    Examples: API wallet not linked to main account, expired key, wrong network.
    Not retryable without operator intervention — log and halt.
    """


class ConnectorNetworkError(ConnectorError):
    """
    Connection lost, timed out, or WebSocket dropped.

    Connectors handle reconnects internally. This surfaces only when reconnect
    attempts are exhausted or the error is unrecoverable at the network level.
    The strategy layer should treat this as a temporary outage and wait.
    """


class ConnectorVenueError(ConnectorError):
    """
    The exchange accepted the connection but rejected the request.

    Examples: insufficient margin, invalid order size, post-only rejected,
    order not found on cancel, rate limit exceeded.
    Always includes the verbatim exchange error message for logging.
    May or may not be retryable depending on the cause — inspect the message.
    """


# ── Protocol ───────────────────────────────────────────────────────────────────


@runtime_checkable
class ExchangeConnector(Protocol):
    """
    The contract every connector implementation must satisfy.

    Public-data methods (subscribe_book, subscribe_trades, get_mid) require
    no credentials and should be implemented first.

    Auth methods (place_order, cancel_order, get_position, get_balance)
    require a configured API wallet. Until implemented, they must raise
    NotImplementedError — never silently succeed or return dummy data.
    When credentials are present but invalid, they raise ConnectorAuthError.

    Usage:
        connector: ExchangeConnector = HyperliquidConnector(cfg)

        # stream book updates
        async for book in connector.subscribe_book("BTC"):
            print(book.mid)

        # stream trade batches — note list[Trade], not Trade
        async for batch in connector.subscribe_trades("BTC"):
            print(f"{len(batch)} co-block trades at {batch[0].block_timestamp_ms}")
    """

    # ── Public data — no auth required ────────────────────────────────────────

    def subscribe_book(self, coin: str) -> AsyncIterator[OrderBook]:
        """
        Stream L2 order book snapshots for coin.

        Yields one OrderBook per exchange push (~0.5s cadence on active markets).
        Runs indefinitely; reconnects internally on network drops.
        Callers cancel the iterator to stop.

        Raises ConnectorNetworkError if reconnects are exhausted.
        """
        ...

    def subscribe_trades(self, coin: str) -> AsyncIterator[list[Trade]]:
        """
        Stream public trade batches for coin.

        Yields one list[Trade] per block batch. Trades within a list share
        block_timestamp_ms and arrived in a single WebSocket message — their
        intra-batch order is arbitrary (Hyperliquid delivers whole-block batches).
        Callers must not flatten batches; the boundary carries queue-position
        information used by the backtester.

        Runs indefinitely; reconnects internally on network drops.
        Raises ConnectorNetworkError if reconnects are exhausted.
        """
        ...

    async def get_mid(self, coin: str) -> float:
        """
        Return the current mid price for coin via a single REST call.

        Convenience method for one-off price checks (e.g., computing a limit
        price before placing an order). Prefer subscribe_book for anything
        in a hot loop — this pays a full round-trip each call.

        Raises ConnectorNetworkError on failure.
        """
        ...

    # ── Auth required ─────────────────────────────────────────────────────────

    async def place_order(self, order: Order) -> OrderId:
        """
        Submit order to the exchange and return the exchange-assigned order ID.

        Raises ConnectorAuthError if credentials are not configured or invalid.
        Raises ConnectorVenueError if the exchange rejects the order (insufficient
        margin, invalid params, post-only collision, etc.) — includes verbatim
        exchange message so the caller can log it.
        """
        ...

    async def cancel_order(self, order_id: OrderId, coin: str) -> None:
        """
        Cancel a resting order.

        coin is required because Hyperliquid's cancel endpoint takes both the
        coin name and the order ID — they are not globally unique without it.

        Silent no-op if the order is already filled or cancelled: the strategy
        layer should not need to track whether a cancel raced a fill.
        Raises ConnectorAuthError if credentials not configured.
        Raises ConnectorVenueError on unexpected exchange errors.
        """
        ...

    async def get_position(self, coin: str) -> Position:
        """
        Return our current position in coin.

        Returns a Position with size=0 if we have no open position —
        a flat position is valid, not an error condition.
        Raises ConnectorAuthError if credentials not configured.
        """
        ...

    async def get_balance(self) -> Balance:
        """
        Return a current account balance snapshot.

        Raises ConnectorAuthError if credentials not configured.
        """
        ...

    def subscribe_fills(self) -> AsyncIterator[Fill]:
        """
        Stream fill events for our account (userFills WebSocket subscription).

        Yields one Fill per partial or full execution of our resting orders.
        Runs indefinitely; reconnects internally on network drops.

        Auth required: Hyperliquid's userFills subscription is keyed to a
        wallet address. Raises ConnectorAuthError if no API wallet configured.

        Note: the first message after subscribing is a snapshot of recent fills,
        not a live event. Consumers should be prepared to receive historical fills
        on (re)connect and deduplicate by trade_id if needed.
        """
        ...

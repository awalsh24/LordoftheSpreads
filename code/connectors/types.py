"""
Canonical data types for the connector layer.

All exchange-facing code translates to/from these types. Strategy and agent
code speaks only these types — never raw exchange formats. Adding a new venue
means adding a new connector implementation; these types stay stable.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────────


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class TimeInForce(StrEnum):
    GTC = "gtc"  # good-till-cancelled — default for MM resting orders
    IOC = "ioc"  # immediate-or-cancel
    FOK = "fok"  # fill-or-kill


class OrderType(StrEnum):
    LIMIT = "limit"
    MARKET = "market"


# ── Order book ─────────────────────────────────────────────────────────────────


class PriceLevel(BaseModel):
    """A single price level in the L2 order book."""

    price: Decimal
    size: Decimal  # total size available at this level across all orders
    num_orders: int  # number of distinct resting orders (Hyperliquid's "n" field)


class OrderBook(BaseModel):
    """
    Full L2 order book snapshot for one coin at one point in time.

    bids: sorted descending by price (index 0 = best bid)
    asks: sorted ascending by price (index 0 = best ask)
    """

    coin: str
    timestamp_ms: int  # exchange-reported timestamp of this snapshot
    received_at_ms: int  # wall-clock ms when our process received the message
    bids: list[PriceLevel]
    asks: list[PriceLevel]

    @property
    def best_bid(self) -> Decimal | None:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Decimal | None:
        return self.asks[0].price if self.asks else None

    @property
    def mid(self) -> Decimal | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / 2

    @property
    def spread(self) -> Decimal | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid


# ── Trades ─────────────────────────────────────────────────────────────────────


class Trade(BaseModel):
    """
    A single public trade that printed on the exchange.

    Hyperliquid delivers trades batched per block: all trades sharing the same
    block_timestamp_ms arrived in a single WebSocket message and are co-block.
    Within a block, order is arbitrary — do not assume intra-batch ordering.

    The connector preserves this by yielding list[Trade] (one list per block
    batch), not individual Trade objects. Callers that need to reason about
    queue position must keep batches intact.
    """

    coin: str
    price: Decimal
    size: Decimal
    side: Side  # aggressor side: BUY = buyer initiated, SELL = seller initiated
    timestamp_ms: int  # exchange timestamp; shared by all trades in the same block
    block_timestamp_ms: int  # explicit co-block marker — same value as timestamp_ms
    received_at_ms: int  # wall-clock ms when our process received this batch
    trade_id: int  # Hyperliquid "tid"
    tx_hash: str  # Hyperliquid "hash" — on-chain transaction identifier


# ── Orders ─────────────────────────────────────────────────────────────────────


OrderId = int  # Hyperliquid order IDs are plain integers


class Order(BaseModel):
    """
    An order request — the shape we hand to the connector for placement.

    post_only defaults to True. Market makers must never accidentally cross
    the spread and pay taker fees. Override only with deliberate intent.
    """

    coin: str
    side: Side
    size: Annotated[Decimal, Field(gt=0)]
    price: Annotated[Decimal, Field(gt=0)]
    order_type: OrderType = OrderType.LIMIT
    time_in_force: TimeInForce = TimeInForce.GTC
    post_only: bool = True  # post-only by default — never accidentally take liquidity
    reduce_only: bool = False


class Fill(BaseModel):
    """
    A fill event: our resting order was partially or fully executed.

    fee is signed: positive = fee paid, negative = rebate received.
    At Hyperliquid maker rebate tiers, fee will be negative.
    """

    order_id: OrderId
    coin: str
    price: Decimal
    size: Decimal  # size of this specific fill (partial fills emit multiple Fill events)
    side: Side
    timestamp_ms: int
    fee: Decimal  # in fee_token units; negative = rebate
    fee_token: str = "USDC"
    is_maker: bool  # True if our order was the passive/resting side


# ── Positions and balance ──────────────────────────────────────────────────────


class Position(BaseModel):
    """
    Our current position in one perpetual market.

    size > 0 = long, size < 0 = short, size == 0 = flat.
    A flat position (size == 0) is a valid return value — not an error.
    """

    coin: str
    size: Decimal  # signed: positive = long, negative = short
    entry_price: Decimal
    unrealized_pnl: Decimal
    margin_used: Decimal
    leverage: int
    liquidation_price: Decimal | None = None  # None when flat or cross-margin


class Balance(BaseModel):
    """
    Account balance snapshot. All monetary values in USDC.

    available_usdc is what the risk layer should check before placing new orders.
    It accounts for margin already locked in open positions and open orders.
    """

    total_usdc: Decimal  # total account value including unrealized PnL
    available_usdc: Decimal  # free margin available for new orders
    margin_used: Decimal  # USDC locked across all open positions
    unrealized_pnl: Decimal
    timestamp_ms: int  # when this snapshot was taken (exchange or local time)

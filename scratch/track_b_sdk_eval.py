"""
Track B eval: raw hyperliquid-python-sdk on testnet.

Tests:
  1. Connect to testnet WS — subscribe to BTC l2Book + trades, print 5 of each
  2. Query REST /info for BTC mid price
  3. Attempt to place one limit bid $5000 below mid (0.001 BTC)
     - Insufficient margin is caught and logged as expected, not a crash
  4. If order placed: wait 30s, cancel, print lifecycle with latencies
  5. Exit cleanly

Reads from .env in the current directory:
  HL_MAIN_ADDRESS    - main testnet wallet address (owns the account/funds)
  HL_API_PRIVATE_KEY - API wallet private key (trades only, no withdrawals)

Run from ~/hl-sdk-test/ (NOT inside LordoftheSpreads):
  pip install hyperliquid-python-sdk websockets python-dotenv
  cp .env.example .env   # fill in credentials
  python track_b_sdk_eval.py
"""

from __future__ import annotations

import asyncio
import json
import os
import time

import websockets
from dotenv import load_dotenv
from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

load_dotenv()

MAIN_ADDRESS: str = os.environ["HL_MAIN_ADDRESS"]
API_PRIVATE_KEY: str = os.environ["HL_API_PRIVATE_KEY"]
WS_URL = "wss://api.hyperliquid-testnet.xyz/ws"


# ── Track B-1: WebSocket subscriptions ────────────────────────────────────────


async def collect_ws_events() -> None:
    """Subscribe to BTC l2Book + trades; print first 5 of each then exit."""
    print("\n=== [WS] Connecting to testnet WebSocket ===")
    book_count = 0
    trade_count = 0

    async with websockets.connect(WS_URL, ping_interval=20) as ws:
        for sub_type in ("l2Book", "trades"):
            await ws.send(
                json.dumps(
                    {"method": "subscribe", "subscription": {"type": sub_type, "coin": "BTC"}}
                )
            )
        print("[WS] Subscribed to l2Book + trades for BTC")

        async for raw in ws:
            msg = json.loads(raw)
            channel = msg.get("channel", "")
            data = msg.get("data", {})

            if channel == "l2Book" and book_count < 5:
                levels = data.get("levels", [[], []])
                best_bid = levels[0][0]["px"] if levels[0] else "?"
                best_ask = levels[1][0]["px"] if levels[1] else "?"
                depth_bid = len(levels[0])
                depth_ask = len(levels[1])
                print(
                    f"[BOOK #{book_count + 1}] "
                    f"bid={best_bid} ask={best_ask} "
                    f"depth={depth_bid}x{depth_ask} "
                    f"exchange_ts={data.get('time')}"
                )
                book_count += 1

            elif channel == "trades" and trade_count < 5:
                trades = data if isinstance(data, list) else []
                for t in trades:
                    if trade_count >= 5:
                        break
                    print(
                        f"[TRADE #{trade_count + 1}] "
                        f"side={t['side']} px={t['px']} sz={t['sz']} "
                        f"tid={t.get('tid')} ts={t.get('time')}"
                    )
                    trade_count += 1

            if book_count >= 5 and trade_count >= 5:
                break

    print("[WS] Done — got 5 book snapshots and 5 trades.\n")


# ── Track B-2: Order lifecycle ─────────────────────────────────────────────────


def run_order_lifecycle() -> None:
    """
    Query BTC mid, attempt a limit bid $5000 below mid.
    Handles all failure modes (margin, auth, API errors) without crashing.
    If order placed successfully: wait 30s then cancel.
    """
    print("=== [ORDER] Starting order lifecycle ===")

    # Step 1: REST /info — get BTC mid
    try:
        info = Info(constants.TESTNET_API_URL, skip_ws=True)
        mids = info.all_mids()
        mid = float(mids["BTC"])
        limit_px = round(mid - 5000, 1)
        print(f"[ORDER] REST /info OK — BTC mid={mid:.1f}")
        print(f"[ORDER] Placing bid at {limit_px:.1f} (${5000:.0f} below mid, 0.001 BTC)")
    except Exception as exc:
        print(f"[ORDER] ✗ Failed to fetch mid price: {exc}")
        return

    # Step 2: attempt order placement
    try:
        wallet = Account.from_key(API_PRIVATE_KEY)
        exchange = Exchange(wallet, constants.TESTNET_API_URL, account_address=MAIN_ADDRESS)

        t_place = time.perf_counter()
        result = exchange.order("BTC", True, 0.001, limit_px, {"limit": {"tif": "Gtc"}})
        place_ms = (time.perf_counter() - t_place) * 1000
        print(f"[ORDER] Place response ({place_ms:.0f}ms): {result}")
    except Exception as exc:
        print(f"[ORDER] ✗ Exception during order placement: {exc}")
        print("[ORDER] Exiting order lifecycle — WS results above are still valid.")
        return

    # Step 3: interpret response
    status = result.get("status")
    if status != "ok":
        # Captures "err" responses — insufficient margin, bad auth, etc.
        err = result.get("response", result)
        print(f"[ORDER] ✗ Order rejected (expected if no testnet funds) — verbatim: {err}")
        print("[ORDER] Skipping cancel — nothing to cancel.")
        print("[ORDER] Lifecycle complete (order rejected path).\n")
        return

    statuses = result["response"]["data"]["statuses"]
    first = statuses[0]

    if "error" in first:
        print(f"[ORDER] ✗ Order status error: {first['error']}")
        print("[ORDER] Skipping cancel.\n")
        return

    if "resting" not in first:
        print(f"[ORDER] ✗ Unexpected status (filled immediately? wrong venue?): {first}")
        print("[ORDER] Skipping cancel.\n")
        return

    oid = first["resting"]["oid"]
    print(f"[ORDER] ✓ Order resting on book — oid={oid}")

    # Step 4: wait then cancel
    print("[ORDER] Waiting 30 seconds before cancel ...")
    time.sleep(30)

    try:
        t_cancel = time.perf_counter()
        cancel_result = exchange.cancel("BTC", oid)
        cancel_ms = (time.perf_counter() - t_cancel) * 1000
        print(f"[ORDER] Cancel response ({cancel_ms:.0f}ms): {cancel_result}")

        if cancel_result.get("status") == "ok":
            print("[ORDER] ✓ Order cancelled cleanly.")
        else:
            print(f"[ORDER] ✗ Cancel response not ok — verbatim: {cancel_result}")
    except Exception as exc:
        print(f"[ORDER] ✗ Exception during cancel: {exc}")

    print("[ORDER] Lifecycle complete.\n")


# ── Entry point ────────────────────────────────────────────────────────────────


async def main() -> None:
    await collect_ws_events()
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, run_order_lifecycle)


if __name__ == "__main__":
    asyncio.run(main())

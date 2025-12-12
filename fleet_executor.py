# ================================================================
# HORUS FLEET EXECUTOR  (Async)
# ================================================================
# هذا الملف هو المنفّذ الفعلي لكل عمليات الشراء والبيع.
#
# يستقبل إشارات من قناتين:
#    • NORMAL       ← من Brain
#    • SMART_WAVE   ← من SmartEntryEngine
#
# ويختار الجندي الصحيح لكل عميل، ثم ينفّذ عن طريق Gate.
#
# ================================================================

import asyncio
import json
import logging
from datetime import datetime
import redis.asyncio as redis

# Soldiers
from soldiers.soldier_okx import SoldierOKX
from soldiers.soldier_binance import SoldierBinance
from soldiers.soldier_bybit import SoldierBybit

# Treasury: لمعرفة عملاء النظام
from core.treasury import Treasury

log = logging.getLogger("FleetExecutor")


# ================================================================
# CHOOSE SOLDIER BASED ON EXCHANGE
# ================================================================

def get_soldier(user_id, exchange):
    exchange = exchange.lower()
    if exchange == "okx":
        return SoldierOKX(user_id)
    if exchange == "binance":
        return SoldierBinance(user_id)
    if exchange == "bybit":
        return SoldierBybit(user_id)
    raise Exception(f"Unknown exchange: {exchange}")


# ================================================================
# CLASS EXECUTOR
# ================================================================

class FleetExecutor:

    def __init__(self):
        self.redis_url = "redis://localhost:6379"
        self.r = None

    async def connect(self):
        self.r = await redis.from_url(self.redis_url, decode_responses=True)
        log.info("⚡ Fleet Executor connected to Redis")

    # ------------------------------------------------------------
    # NORMAL EXECUTION FLOW
    # ------------------------------------------------------------

    async def handle_normal(self, packet):
        """
        Packet example:
        {
            "type": "NORMAL",
            "signal_id": "...",
            "symbol": "BTC/USDT",
            "action": "BUY",
            "per_exchange": {
                "okx": { "u1":100, "u5":50 },
                "binance": {...},
                "bybit": {}
            }
        }
        """

        symbol = packet["symbol"]
        action = packet["action"].upper()
        per_exchange = packet["per_exchange"]

        log.info(f"\n⚡ NORMAL EXECUTION STARTED | {symbol} | {action}")

        tasks = []

        for ex, clients in per_exchange.items():
            for user_id, usd in clients.items():

                soldier = get_soldier(user_id, ex)

                if action == "BUY":
                    tasks.append(soldier.buy(symbol, usd))
                elif action == "SELL":
                    tasks.append(soldier.sell(symbol, usd))
                elif action == "CLOSE":
                    tasks.append(soldier.close(symbol))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        log.info(f"✅ NORMAL EXECUTION DONE | {len(results)} orders processed")

    # ------------------------------------------------------------
    # SMART WAVE EXECUTION FLOW
    # ------------------------------------------------------------

    async def handle_wave(self, packet):
        """
        Packet example:
        {
            "type": "SMART_WAVE",
            "signal_id": "ID_wave1_okx",
            "symbol": "BTC/USDT",
            "exchange": "okx",
            "wave": 1,
            "per_client_amount_usd": { "u1":40, "u2":25 }
        }
        """

        symbol = packet["symbol"]
        ex = packet["exchange"]
        action = packet["action"].upper()
        client_amounts = packet["per_client_amount_usd"]

        log.info(f"\n🌊 EXECUTING WAVE {packet['wave']} | {ex} | {symbol}")

        tasks = []

        for user_id, usd in client_amounts.items():
            if usd <= 0:
                continue  # skip zero allocations

            soldier = get_soldier(user_id, ex)

            if action == "BUY":
                tasks.append(soldier.buy(symbol, usd))
            elif action == "SELL":
                tasks.append(soldier.sell(symbol, usd))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        log.info(f"🌊 WAVE DONE | {len(results)} orders processed")

    # ------------------------------------------------------------
    # MAIN LISTENER LOOP
    # ------------------------------------------------------------

    async def run(self):
        await self.connect()

        sub = self.r.pubsub()
        await sub.subscribe("NEXUS_FLEET_COMMAND")

        log.info("⚡ Fleet Executor ONLINE — Listening for execution packets...")

        async for msg in sub.listen():
            if msg["type"] != "message":
                continue

            try:
                packet = json.loads(msg["data"])
                typ = packet["type"]

                if typ == "NORMAL":
                    await self.handle_normal(packet)

                elif typ == "SMART_WAVE":
                    await self.handle_wave(packet)

                else:
                    log.error(f"❌ Unknown packet type: {typ}")

            except Exception as e:
                log.error(f"❌ FLEET ERROR: {e}", exc_info=True)


# ================================================================
# ENTRY POINT
# ================================================================

if __name__ == "__main__":
    asyncio.run(FleetExecutor().run())

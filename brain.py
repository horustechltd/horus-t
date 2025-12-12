# ================================================================
# HORUS BRAIN ENGINE  (Async)
# ================================================================
#  هذا هو "عقل حورس"
#  - يستقبل الإشارات من الكابتن أو من المراقب
#  - يقرر: NORMAL أو RISKY
#  - يحسب توزيع العملة على العملاء والمنصات
#  - يصنع Signal Packet جاهز للتنفيذ
#  - يرسل:
#       NORMAL → NEXUS_FLEET_COMMAND
#       RISKY  → HORUS_SMART_ENTRY
#
#  NOTE:
#   لا يقوم بأي تنفيذ — التنفيذ حصرياً عبر:
#       • Fleet Executor
#       • Smart Entry Engine
#
# ================================================================

import asyncio
import json
import logging
from datetime import datetime
import redis.asyncio as redis

from core.treasury import Treasury     # للحصول على عملاء النظام ومفاتيحهم
from settings.settings_manager import SettingsManager  # لأخذ allocation
# يمكن لاحقاً إضافة دوال حساب Equity لو تحب

log = logging.getLogger("Brain")


class BrainEngine:

    def __init__(self):
        self.redis_url = "redis://localhost:6379"
        self.r = None
    
    async def connect(self):
        self.r = await redis.from_url(self.redis_url, decode_responses=True)
        log.info("🧠 Brain Connected to Redis")

    # ============================================================
    # RECEIVE SIGNAL FROM CAPTAIN or UI
    # ============================================================

    async def handle_signal(self, signal):
        """
        signal = {
            "signal_id": "...",
            "asset": "BTC/USDT",
            "action": "BUY",
            "risk": "RISKY" or "NORMAL"
        }
        """

        asset = signal["asset"]
        action = signal["action"]
        risk = signal.get("risk", "NORMAL").upper()

        log.info(f"\n🧠 BRAIN RECEIVED SIGNAL:\n{signal}")

        # step 1 — احصل على كل العملاء النشطين
        clients = Treasury.get_all_clients()

        if not clients:
            log.warning("⚠️ No clients registered. Aborting signal.")
            return

        # step 2 — نوزع العملاء حسب البورصة
        per_exchange = {
            "okx": {},
            "binance": {},
            "bybit": {}
        }

        total_demand = 0

        for client_id, info in clients.items():
            ex = info["exchange"].lower()
            allocation = SettingsManager.get_allocation(client_id)  # نسبة الدخول
            balance = info.get("balance_usdt", 0)

            usd_to_use = balance * (allocation / 100)
            if usd_to_use <= 0:
                continue

            per_exchange[ex][client_id] = usd_to_use
            total_demand += usd_to_use

        log.info(f"💰 Total Expected Demand = {total_demand}")

        # clean empty exchanges
        per_exchange = {k: v for k, v in per_exchange.items() if v}

        # ============================================================
        # CASE 1: Normal signal — direct fleet execution
        # ============================================================

        if risk == "NORMAL":
            packet = {
                "type": "NORMAL",
                "signal_id": signal["signal_id"],
                "symbol": asset,
                "action": action,
                "per_exchange": per_exchange,
                "timestamp": datetime.utcnow().timestamp()
            }

            await self.r.publish("NEXUS_FLEET_COMMAND", json.dumps(packet))
            log.info("📤 NORMAL Signal Dispatched to Fleet Executor")
            return

        # ============================================================
        # CASE 2: Risky signal — send to Smart Entry Engine
        # ============================================================

        if risk == "RISKY":
            packet = {
                "type": "RISKY",
                "signal_id": signal["signal_id"],
                "symbol": asset,
                "action": action,
                "demand": {
                    ex: {
                        "client_demands": clients_dict,
                        "exchange": ex
                    }
                    for ex, clients_dict in per_exchange.items()
                },
                "timestamp": datetime.utcnow().timestamp()
            }

            await self.r.publish("HORUS_SMART_ENTRY", json.dumps(packet))
            log.info("⚡ RISKY Signal Sent to Smart Entry Engine")
            return

        log.error(f"❌ Unknown risk type: {risk}")


# ============================================================
#  REDIS LISTENER — ENTRY POINT
# ============================================================

async def run_brain():
    brain = BrainEngine()
    await brain.connect()

    # Brain listens for new captain signals
    subscriber = brain.r.pubsub()
    await subscriber.subscribe("HORUS_CAPTAIN_SIGNALS")

    log.info("🧠 Brain Engine ONLINE — Listening for signals...")

    async for message in subscriber.listen():
        if message["type"] != "message":
            continue

        try:
            signal = json.loads(message["data"])
            await brain.handle_signal(signal)
        except Exception as e:
            log.error(f"❌ Brain failed processing signal: {e}")


if __name__ == "__main__":
    asyncio.run(run_brain())

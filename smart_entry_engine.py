# ================================================================
# HORUS SMART ENTRY ENGINE  (Async)
# ================================================================
#  هذا المحرك يتعامل فقط مع:
#       • RISKY signals
#       • حساب السيولة
#       • WCF
#       • waves
#       • توزيع الحمل على العملاء
#
#  التنفيذ الفعلي يقوم به:
#       • Fleet Executor
# ================================================================

import aiohttp
import asyncio
import json
import logging
from datetime import datetime
import redis.asyncio as redis

log = logging.getLogger("SmartEntry")


# ================================================================
# ORDERBOOK FETCHERS
# ================================================================

async def fetch_okx(symbol):
    url = f"https://www.okx.com/api/v5/market/books?instId={symbol}&sz=40"
    async with aiohttp.ClientSession() as s:
        async with s.get(url) as r:
            js = await r.json()
            try:
                return js["data"][0]
            except:
                return None


async def fetch_binance(symbol):
    url = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit=40"
    async with aiohttp.ClientSession() as s:
        async with s.get(url) as r:
            try:
                js = await r.json()
                return {"asks": js["asks"]}
            except:
                return None


async def fetch_bybit(symbol):
    url = f"https://api.bybit.com/v5/market/orderbook?category=spot&symbol={symbol}"
    async with aiohttp.ClientSession() as s:
        async with s.get(url) as r:
            try:
                js = await r.json()
                return {"asks": js["result"]["a"]}
            except:
                return None


# ================================================================
# LIQUIDITY MODEL
# ================================================================

def compute_liquidity(asks):
    """
    يعيد:
        price0, liquidity_1%, liquidity_3%
    """
    if not asks:
        return None, 0, 0

    best = float(asks[0][0])
    up1 = best * 1.01
    up3 = best * 1.03

    l1 = 0
    l3 = 0

    for p, a in asks:
        p = float(p)
        a = float(a)
        val = p * a
        if p <= up1:
            l1 += val
        if p <= up3:
            l3 += val

    return best, l1, l3


def wcf(total_demand, liq1):
    if liq1 <= 0:
        return float("inf")
    return total_demand / liq1


def wave_count(WCF):
    if WCF <= 0.6:
        return 1
    elif WCF <= 1.1:
        return 2
    elif WCF <= 1.6:
        return 3
    elif WCF <= 2.2:
        return 4
    return 4


def wave_distribution(n):
    if n == 1: return [1.0]
    if n == 2: return [0.6, 0.4]
    if n == 3: return [0.4, 0.35, 0.25]
    if n == 4: return [0.35, 0.30, 0.20, 0.15]
    return [1.0]


# ================================================================
# ENGINE CLASS
# ================================================================

class SmartEntryEngine:

    def __init__(self):
        self.redis_url = "redis://localhost:6379"
        self.r = None

    async def connect(self):
        self.r = await redis.from_url(self.redis_url, decode_responses=True)
        log.info("🧠 Smart Entry Engine connected to Redis")

    # ------------------------------------------------------------

    async def process_signal(self, packet):
        """
        packet = {
            "signal_id": "uuid",
            "symbol": "BTC/USDT",
            "action": "BUY",
            "demand": {
                 "okx": {"client_demands": {u1:100, u2:50}},
                 "binance": {...},
                 "bybit": {...}
            }
        }
        """

        symbol_input = packet["symbol"]
        action = packet["action"]
        signal_id = packet["signal_id"]

        log.info(f"\n⚡ SMART ENTRY PROCESSING:\n{packet}")

        # ========================================================
        # STEP 1 — Fetch liquidity from all exchanges
        # ========================================================

        tasks = [
            fetch_okx(symbol_input.replace("/", "-")),
            fetch_binance(symbol_input.replace("/", "")),
            fetch_bybit(symbol_input.replace("/", ""))
        ]
        okx_ob, bin_ob, byb_ob = await asyncio.gather(*tasks)

        books = {}

        if okx_ob:
            p, l1, l3 = compute_liquidity(okx_ob["asks"])
            books["okx"] = {"price": p, "liq1": l1, "liq3": l3}

        if bin_ob:
            p, l1, l3 = compute_liquidity(bin_ob["asks"])
            books["binance"] = {"price": p, "liq1": l1, "liq3": l3}

        if byb_ob:
            p, l1, l3 = compute_liquidity(byb_ob["asks"])
            books["bybit"] = {"price": p, "liq1": l1, "liq3": l3}

        log.info(f"📊 ORDERBOOKS:\n{books}")

        # ========================================================
        # STEP 2 — For each exchange, build waves
        # ========================================================

        all_waves = []

        for ex, ex_data in packet["demand"].items():

            if ex not in books:
                log.warning(f"⚠️ No book for {ex}")
                continue

            liq1 = books[ex]["liq1"]
            client_demands = ex_data["client_demands"]
            total_ex_demand = sum(client_demands.values())

            WCF = wcf(total_ex_demand, liq1)
            n_waves = wave_count(WCF)
            weights = wave_distribution(n_waves)

            # reduction factor لو الطلب أكبر من السيولة
            reduction = min(1.0, liq1 / total_ex_demand) if liq1 > 0 else 0

            # apply reduction
            final_client_amounts = {
                cid: usd * reduction
                for cid, usd in client_demands.items()
            }

            log.info(f"🌊 {ex}: waves={n_waves} | reduction={reduction:.3f} | WCF={WCF:.3f}")

            # build wave packets
            for idx in range(n_waves):
                wave_id = idx + 1
                wave_clients = {
                    cid: amt * weights[idx]
                    for cid, amt in final_client_amounts.items()
                }

                wave_packet = {
                    "type": "SMART_WAVE",
                    "signal_id": f"{signal_id}_wave{wave_id}_{ex}",
                    "parent": signal_id,
                    "symbol": symbol_input,
                    "action": action,
                    "exchange": ex,
                    "wave": wave_id,
                    "per_client_amount_usd": wave_clients,
                    "timestamp": datetime.utcnow().timestamp()
                }

                all_waves.append(wave_packet)

        # ========================================================
        # STEP 3 — Dispatch waves to Fleet Executor
        # ========================================================

        for wave in all_waves:
            await self.r.publish("NEXUS_FLEET_COMMAND", json.dumps(wave))

        log.info(f"🚀 {len(all_waves)} SMART WAVES DISPATCHED.")


# ================================================================
# ENTRY POINT
# ================================================================

async def run_engine():
    engine = SmartEntryEngine()
    await engine.connect()

    # Subscribe to RISKY signals from Brain
    sub = engine.r.pubsub()
    await sub.subscribe("HORUS_SMART_ENTRY")

    log.info("🧠 Smart Entry Engine ONLINE — Listening for risky signals...")

    async for msg in sub.listen():
        if msg["type"] != "message":
            continue
        
        try:
            packet = json.loads(msg["data"])
            await engine.process_signal(packet)
        except Exception as e:
            log.error(f"❌ Smart Entry Error: {e}")


if __name__ == "__main__":
    asyncio.run(run_engine())

# ================================================================
# HORUS CAPTAIN EYE  (Async)
# ================================================================
#  وظيفة Eye:
#     - مراقبة حساب الكابتن الحقيقي على البورصة
#     - اكتشاف أي صفقة جديدة (Buy/Sell)
#     - تحويلها إلى إشارة رسمية
#     - إرسال الإشارة إلى Brain عبر HORUS_CAPTAIN_SIGNALS
#
#  لا يقوم Eye بأي تنفيذ داخل البورصة.
#  فقط "يراقب → يبلّغ".
# ================================================================

import aiohttp
import asyncio
import time
import json
import logging
import redis.asyncio as redis

from core.treasury import Treasury  # لجلب مفاتيح الكابتن

log = logging.getLogger("Eye")


# ---------------------------------------------------------------
#  FETCH DEALS PER EXCHANGE
# ---------------------------------------------------------------

async def fetch_okx_recent(api_key, secret, passphrase):
    """
    إحضار صفقات Spot حديثة للكابتن من OKX
    """
    url = "https://www.okx.com/api/v5/trade/fills?instType=SPOT"
    headers = {
        "OK-ACCESS-KEY": api_key,
        "OK-ACCESS-PASSPHRASE": passphrase
    }
    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers=headers) as r:
            js = await r.json()
            return js.get("data", [])


async def fetch_binance_fills(api_key):
    """
    Binance Spot user trades (simple version)
    """
    url = "https://api.binance.com/api/v3/myTrades?symbol=BTCUSDT"  # placeholder symbol
    headers = {"X-MBX-APIKEY": api_key}

    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers=headers) as r:
            try:
                return await r.json()
            except:
                return []


async def fetch_bybit_fills(api_key):
    """Bybit Spot fills (simplified placeholder)"""
    return []


# ---------------------------------------------------------------
#  MAIN EYE CLASS
# ---------------------------------------------------------------

class CaptainEye:

    def __init__(self, captain_id):
        self.captain_id = captain_id
        self.redis_url = "redis://localhost:6379"
        self.r = None

        self.last_seen_ids = set()  # لتجنب تكرار نفس الصفقة

    async def connect(self):
        self.r = await redis.from_url(self.redis_url, decode_responses=True)
        log.info("👁️ Eye Connected to Redis")

    # -----------------------------------------------------------
    #  CAPTAIN MONITOR LOOP
    # -----------------------------------------------------------

    async def monitor(self):
        """
        مراقبة حساب الكابتن بإعادة جلب الصفقات الحديثة كل X ثواني.
        لو ظهرت صفقة جديدة → يرسل Signal للـ Brain.
        """

        keys = Treasury.get_keys(self.captain_id, "okx")
        api_key = keys["api_key"]
        secret = keys["secret"]
        passphrase = keys["passphrase"]

        log.info(f"👁️ Eye ACTIVE — Watching captain {self.captain_id}")

        while True:
            try:
                # ----------------------------
                # FETCH LATEST TRADES
                # ----------------------------
                fills = await fetch_okx_recent(api_key, secret, passphrase)

                for fill in fills:

                    trade_id = fill.get("tradeId")

                    # ignore old trades
                    if trade_id in self.last_seen_ids:
                        continue

                    self.last_seen_ids.add(trade_id)

                    side = fill["side"].upper()
                    inst = fill["instId"]           # مثل: BTC-USDT
                    price = float(fill["fillPx"])

                    symbol = inst.replace("-", "/")  # تحويل BTC-USDT → BTC/USDT

                    # ----------------------------
                    # BUILD SIGNAL PACKET
                    # ----------------------------

                    signal = {
                        "signal_id": f"captain_{trade_id}",
                        "source": "CAPTAIN_EYE",
                        "symbol": symbol,
                        "action": "BUY" if side == "BUY" else "SELL",
                        "risk": "NORMAL",   # كابتن لا يرسل RISKY من هنا
                        "timestamp": time.time()
                    }

                    # ----------------------------
                    # SEND TO BRAIN
                    # ----------------------------

                    await self.r.publish("HORUS_CAPTAIN_SIGNALS", json.dumps(signal))

                    log.info(f"📤 Captain Signal Sent → {signal}")

            except Exception as e:
                log.error(f"❌ EYE ERROR: {e}")

            await asyncio.sleep(4)  # زمن المراقبة

# ---------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------

async def run_eye():
    eye = CaptainEye(captain_id="master")
    await eye.connect()
    await eye.monitor()


if __name__ == "__main__":
    asyncio.run(run_eye())

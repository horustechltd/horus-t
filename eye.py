# ================================================================
# HORUS CAPTAIN EYE — OKX WEBSOCKET (REAL-TIME)
# ================================================================
# هذا هو الإصدار الحقيقي من عين حورس.
# يعتمد على WebSocket مباشر من OKX:
#
#   • الحساب ينفّذ صفقة → OKX ترسل Fill event فوراً
#   • Eye يستقبلها خلال أقل من 100ms
#   • Eye يبني Signal جاهز
#   • يرسلها إلى Brain عبر HORUS_CAPTAIN_SIGNALS
#
# ================================================================

import asyncio
import json
import time
import hmac
import base64
import logging
import redis.asyncio as redis
import websockets

from core.treasury import Treasury

log = logging.getLogger("EyeWS")

OKX_WS_URL = "wss://ws.okx.com:8443/ws/v5/private"


# ------------------ SIGNATURE FUNCTION ------------------

def okx_sign(ts, method, path, body, secret):
    msg = f"{ts}{method}{path}{body}"
    return base64.b64encode(
        hmac.new(secret.encode(), msg.encode(), digestmod='sha256').digest()
    ).decode()


# ================================================================
# CAPTAIN EYE CLASS
# ================================================================

class CaptainEyeWS:

    def __init__(self, captain_id="master"):
        self.captain_id = captain_id
        self.redis_url = "redis://localhost:6379"
        self.r = None
        self.ws = None

    async def connect_redis(self):
        self.r = await redis.from_url(self.redis_url, decode_responses=True)
        log.info("👁️ EyeWS connected to Redis")

    # ------------------------------------------------------------
    # CONNECT TO OKX WEBSOCKET
    # ------------------------------------------------------------

    async def connect_okx(self):
        keys = Treasury.get_keys(self.captain_id, "okx")

        api_key = keys["api_key"]
        secret = keys["secret"]
        passphrase = keys["passphrase"]

        log.info("🔌 Connecting to OKX WebSocket...")

        self.ws = await websockets.connect(OKX_WS_URL)

        # auth message

        ts = str(time.time())
        sign = okx_sign(ts, "GET", "/users/self/verify", "", secret)

        auth_msg = {
            "op": "login",
            "args": [{
                "apiKey": api_key,
                "passphrase": passphrase,
                "timestamp": ts,
                "sign": sign
            }]
        }

        await self.ws.send(json.dumps(auth_msg))
        res = json.loads(await self.ws.recv())

        if res.get("code") != "0":
            raise Exception(f"❌ WebSocket Login failed: {res}")

        log.info("🔐 OKX WS Authenticated Successfully")

        # subscribe to fills
        sub_msg = {
            "op": "subscribe",
            "args": [{"channel": "orders"}]
        }

        await self.ws.send(json.dumps(sub_msg))
        log.info("📡 Subscribed to OKX orders channel")

    # ------------------------------------------------------------
    # LISTEN LOOP
    # ------------------------------------------------------------

    async def listen(self):
        """
        يستقبل كل Fill event من الكابتن.
        """

        while True:
            try:
                msg = await self.ws.recv()
                data = json.loads(msg)

                if "data" not in data:
                    continue

                for order in data["data"]:
                    if order.get("fillSz") is None:
                        continue  # مش صفقة

                    # استخراج بيانات الصفقة
                    inst = order["instId"]           # BTC-USDT
                    side = order["side"].upper()     # buy/sell
                    fill_price = float(order["fillPx"])

                    symbol = inst.replace("-", "/")  # BTC/USDT

                    # ----------------------------
                    # BUILD SIGNAL
                    # ----------------------------

                    signal = {
                        "signal_id": f"captain_{order['ordId']}",
                        "source": "CAPTAIN_EYE",
                        "symbol": symbol,
                        "action": "BUY" if side == "BUY" else "SELL",
                        "risk": "NORMAL",
                        "price": fill_price,
                        "timestamp": time.time()
                    }

                    # ----------------------------
                    # SEND TO BRAIN
                    # ----------------------------

                    await self.r.publish("HORUS_CAPTAIN_SIGNALS", json.dumps(signal))

                    log.info(f"📤 REAL-TIME CAPTAIN SIGNAL → {signal}")

            except Exception as e:
                log.error(f"❌ WS Error: {e}")
                log.info("🔄 Reconnecting in 3 seconds...")
                await asyncio.sleep(3)
                await self.connect_okx()

    # ------------------------------------------------------------
    # RUNNER
    # ------------------------------------------------------------

    async def run(self):
        await self.connect_redis()
        await self.connect_okx()
        await self.listen()


# ================================================================
# ENTRY POINT
# ================================================================

if __name__ == "__main__":
    asyncio.run(CaptainEyeWS().run())

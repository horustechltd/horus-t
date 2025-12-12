# ================================================================
#  HORUS GATE - Unified Exchange Execution Layer (Async)
# ================================================================
#  • هذا الملف هو نقطة التنفيذ الوحيدة للنظام
#  • الجنود Soldiers تستدعي Gate فقط
#  • العقل Brain / SmartEntryEngine لا يقومان بأي تنفيذ مباشر
#  • يدعم: OKX - Binance - Bybit
#  • يتطلب: Treasurer للحصول على API Keys
# ================================================================

import aiohttp
import asyncio
import time
import hmac
import hashlib
import base64
import json

from core.treasury import Treasury   # لجلب مفاتيح العملاء


# ================================================================
#  UTIL
# ================================================================

async def _http_post(session, url, headers, payload):
    async with session.post(url, headers=headers, data=json.dumps(payload)) as r:
        return await r.json()

async def _http_get(session, url, headers=None):
    async with session.get(url, headers=headers) as r:
        return await r.json()


# ================================================================
#  OKX CLIENT
# ================================================================

class OKXClient:
    BASE = "https://www.okx.com"

    def __init__(self, api_key, secret_key, passphrase):
        self.key = api_key
        self.secret = secret_key
        self.passphrase = passphrase

    # --------------------- SIGNATURE -----------------------------

    def _sign(self, method, path, body=""):
        ts = str(time.time())
        msg = f"{ts}{method}{path}{body}"
        sign = base64.b64encode(
            hmac.new(self.secret.encode(), msg.encode(), hashlib.sha256).digest()
        ).decode()
        return ts, sign

    # --------------------- MARKET BUY -----------------------------

    async def market_buy(self, symbol, usd):
        """
        شراء Market بقيمة USD
        """
        path = "/api/v5/trade/order"
        url = self.BASE + path

        body = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "market",
            "sz": str(usd)   # OKX تسمح بـ sz كقيمة بالدولار
        }
        body_str = json.dumps(body)

        ts, sign = self._sign("POST", path, body_str)

        headers = {
            "OK-ACCESS-KEY": self.key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": ts,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            return await _http_post(session, url, headers, body)

    # --------------------- MARKET SELL -----------------------------

    async def market_sell(self, symbol, usd):
        path = "/api/v5/trade/order"
        url = self.BASE + path

        body = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "sell",
            "ordType": "market",
            "sz": str(usd)
        }
        body_str = json.dumps(body)

        ts, sign = self._sign("POST", path, body_str)

        headers = {
            "OK-ACCESS-KEY": self.key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": ts,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            return await _http_post(session, url, headers, body)

    # --------------------- CLOSE -----------------------------

    async def close_position(self, symbol):
        """
        إغلاق أي مراكز مفتوحة على العملة
        (Spot = بيع كامل balance)
        """
        # step 1 – get balance
        async with aiohttp.ClientSession() as session:
            bal = await _http_get(
                session,
                f"{self.BASE}/api/v5/account/balance?ccy={symbol.split('-')[0]}"
            )

        amount = bal.get("data", [{}])[0].get("details", [{}])[0].get("cashBal", "0")
        if float(amount) <= 0:
            return {"msg": "nothing_to_close"}

        # execute full sell
        return await self.market_sell(symbol, amount)


# ================================================================
#  BINANCE CLIENT
# ================================================================

class BinanceClient:
    BASE = "https://api.binance.com"

    def __init__(self, api_key, secret_key):
        self.key = api_key
        self.secret = secret_key

    def _sign(self, query):
        return hmac.new(self.secret.encode(), query.encode(), hashlib.sha256).hexdigest()

    async def market_buy(self, symbol, usd):
        """
        شراء بقيمة USD (نحسب الكمية باستخدام السعر الحالي)
        """
        # step 1 – fetch price
        async with aiohttp.ClientSession() as session:
            tick = await _http_get(session, f"{self.BASE}/api/v3/ticker/price?symbol={symbol}")
            price = float(tick["price"])

        qty = round(usd / price, 6)

        ts = int(time.time() * 1000)
        query = f"symbol={symbol}&side=BUY&type=MARKET&quantity={qty}&timestamp={ts}"
        signature = self._sign(query)

        async with aiohttp.ClientSession() as session:
            return await _http_post(
                session,
                f"{self.BASE}/api/v3/order",
                {
                    "X-MBX-APIKEY": self.key
                },
                {
                    "symbol": symbol,
                    "side": "BUY",
                    "type": "MARKET",
                    "quantity": qty,
                    "timestamp": ts,
                    "signature": signature
                }
            )

    async def market_sell(self, symbol, usd):
        async with aiohttp.ClientSession() as session:
            tick = await _http_get(session, f"{self.BASE}/api/v3/ticker/price?symbol={symbol}")
            price = float(tick["price"])

        qty = round(usd / price, 6)

        ts = int(time.time() * 1000)
        query = f"symbol={symbol}&side=SELL&type=MARKET&quantity={qty}&timestamp={ts}"
        signature = self._sign(query)

        async with aiohttp.ClientSession() as session:
            return await _http_post(
                session,
                f"{self.BASE}/api/v3/order",
                {
                    "X-MBX-APIKEY": self.key
                },
                {
                    "symbol": symbol,
                    "side": "SELL",
                    "type": "MARKET",
                    "quantity": qty,
                    "timestamp": ts,
                    "signature": signature
                }
            )

    async def close_position(self, symbol):
        # get total coin balance
        async with aiohttp.ClientSession() as session:
            acc = await _http_get(session, f"{self.BASE}/api/v3/account")
        for x in acc["balances"]:
            if x["asset"] == symbol.replace("USDT", ""):
                bal = float(x["free"])
                break
        else:
            return {"msg": "nothing_to_close"}

        ts = int(time.time() * 1000)
        query = f"symbol={symbol}&side=SELL&type=MARKET&quantity={bal}&timestamp={ts}"
        signature = self._sign(query)

        async with aiohttp.ClientSession() as session:
            return await _http_post(
                session,
                f"{self.BASE}/api/v3/order",
                {
                    "X-MBX-APIKEY": self.key
                },
                {
                    "symbol": symbol,
                    "side": "SELL",
                    "type": "MARKET",
                    "quantity": bal,
                    "timestamp": ts,
                    "signature": signature
                }
            )


# ================================================================
#  BYBIT CLIENT (SPOT)
# ================================================================

class BybitClient:
    BASE = "https://api.bybit.com"

    def __init__(self, api_key, secret_key):
        self.key = api_key
        self.secret = secret_key

    def _sign(self, payload):
        return hmac.new(self.secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

    async def market_buy(self, symbol, usd):
        # fetch price
        async with aiohttp.ClientSession() as s:
            tick = await _http_get(s, f"{self.BASE}/v5/market/tickers?category=spot&symbol={symbol}")
            price = float(tick["result"]["list"][0]["lastPrice"])

        qty = usd / price

        ts = int(time.time() * 1000)
        body = {
            "category": "spot",
            "symbol": symbol,
            "side": "Buy",
            "orderType": "Market",
            "qty": str(qty),
            "timestamp": ts
        }
        sign = self._sign(json.dumps(body))

        async with aiohttp.ClientSession() as s:
            return await _http_post(
                s,
                f"{self.BASE}/v5/order/create",
                {"X-BAPI-API-KEY": self.key, "X-BAPI-SIGN": sign},
                body
            )

    async def market_sell(self, symbol, usd):
        # fetch price
        async with aiohttp.ClientSession() as s:
            tick = await _http_get(s, f"{self.BASE}/v5/market/tickers?category=spot&symbol={symbol}")
            price = float(tick["result"]["list"][0]["lastPrice"])

        qty = usd / price

        ts = int(time.time() * 1000)
        body = {
            "category": "spot",
            "symbol": symbol,
            "side": "Sell",
            "orderType": "Market",
            "qty": str(qty),
            "timestamp": ts
        }
        sign = self._sign(json.dumps(body))

        async with aiohttp.ClientSession() as s:
            return await _http_post(
                s,
                f"{self.BASE}/v5/order/create",
                {"X-BAPI-API-KEY": self.key, "X-BAPI-SIGN": sign},
                body
            )

    async def close_position(self, symbol):
        # spot only: find balance and sell all
        asset = symbol.replace("USDT", "")

        async with aiohttp.ClientSession() as s:
            bal = await _http_get(s, f"{self.BASE}/v5/asset/transfer/query-asset-info?accountType=SPOT")

        for coin in bal["result"]["spot"]:
            if coin["coin"] == asset:
                amt = float(coin["free"])
                break
        else:
            return {"msg": "nothing_to_close"}

        return await self.market_sell(symbol, amt)


# ================================================================
#  UNIFIED GATE
# ================================================================

class Gate:

    async def _get_client(self, user_id, exchange_type):
        """
        استدعاء مفاتيح العميل من Treasury ثم اختيار الـ client الصحيح
        """
        keys = Treasury.get_keys(user_id, exchange_type)

        if exchange_type == "okx":
            return OKXClient(keys["api_key"], keys["secret"], keys["passphrase"])

        if exchange_type == "binance":
            return BinanceClient(keys["api_key"], keys["secret"])

        if exchange_type == "bybit":
            return BybitClient(keys["api_key"], keys["secret"])

        raise Exception(f"Unknown exchange type: {exchange_type}")

    # -------------------- BUY -------------------------

    async def market_buy(self, user_id, symbol, usd, exchange="okx"):
        client = await self._get_client(user_id, exchange)
        return await client.market_buy(symbol, usd)

    # -------------------- SELL -------------------------

    async def market_sell(self, user_id, symbol, usd, exchange="okx"):
        client = await self._get_client(user_id, exchange)
        return await client.market_sell(symbol, usd)

    # -------------------- CLOSE POSITION ----------------

    async def close_position(self, user_id, symbol, exchange="okx"):
        client = await self._get_client(user_id, exchange)
        return await client.close_position(symbol)

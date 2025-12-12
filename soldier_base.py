# ================================================================
# HORUS SOLDIER BASE (Async)
# ================================================================
# الجنود هم المنفّذون الفعليون للأوامر
# جميعهم يرث من هذا الكلاس
# Gate هو الوحيد الذي يتعامل مباشرة مع API البورصات
# ================================================================

import asyncio
import logging
import traceback
from gate.gate import Gate

log = logging.getLogger("SoldierBase")


class SoldierBase:
    """
    SoldierBase هو العمود الفقري لكل الجنود.
    يقدّم وظائف:
        - execute_buy
        - execute_sell
        - execute_close
    ويضمن:
        - تنفيذ آمن
        - إدارة الأخطاء
        - Logging موحد
    """

    def __init__(self, user_id, exchange):
        self.user_id = user_id
        self.exchange = exchange.lower()
        self.gate = Gate()

    # ============================================================
    # BUY
    # ============================================================

    async def execute_buy(self, symbol, usd):
        """
        تنفيذ أمر شراء Market بقيمة USD
        """
        try:
            log.info(f"⚔️ BUY | User={self.user_id} | Ex={self.exchange} | {symbol} | USD={usd}")

            result = await self.gate.market_buy(
                user_id=self.user_id,
                symbol=symbol,
                usd=usd,
                exchange=self.exchange
            )

            log.info(f"✅ BUY EXECUTED | {result}")
            return {"status": "success", "data": result}

        except Exception as e:
            log.error(f"❌ BUY FAILED | {self.user_id} | {symbol} | {e}")
            traceback.print_exc()
            return {"status": "error", "error": str(e)}

    # ============================================================
    # SELL
    # ============================================================

    async def execute_sell(self, symbol, usd):
        """
        تنفيذ بيع Market بقيمة USD
        """
        try:
            log.info(f"⚔️ SELL | User={self.user_id} | Ex={self.exchange} | {symbol} | USD={usd}")

            result = await self.gate.market_sell(
                user_id=self.user_id,
                symbol=symbol,
                usd=usd,
                exchange=self.exchange
            )

            log.info(f"✅ SELL EXECUTED | {result}")
            return {"status": "success", "data": result}

        except Exception as e:
            log.error(f"❌ SELL FAILED | {self.user_id} | {symbol} | {e}")
            traceback.print_exc()
            return {"status": "error", "error": str(e)}

    # ============================================================
    # CLOSE ANY POSITION
    # ============================================================

    async def execute_close(self, symbol):
        """
        إغلاق أي مركز مفتوح على العملة
        """
        try:
            log.info(f"⚔️ CLOSE | User={self.user_id} | Ex={self.exchange} | {symbol}")

            result = await self.gate.close_position(
                user_id=self.user_id,
                symbol=symbol,
                exchange=self.exchange
            )

            log.info(f"✅ CLOSE EXECUTED | {result}")
            return {"status": "success", "data": result}

        except Exception as e:
            log.error(f"❌ CLOSE FAILED | {self.user_id} | {symbol} | {e}")
            traceback.print_exc()
            return {"status": "error", "error": str(e)}

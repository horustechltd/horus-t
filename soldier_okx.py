# ================================================================
# HORUS OKX SOLDIER (Async)
# ================================================================
#  الجندي الخاص ببورصة OKX
#  يرث من SoldierBase
#  ويضيف فقط تحويل صيغة الرموز (symbol mapping)
# ================================================================

from soldiers.soldier_base import SoldierBase
import logging

log = logging.getLogger("SoldierOKX")


class SoldierOKX(SoldierBase):
    """
    Soldier for OKX customers.
    وظيفته:
      - توحيد symbol format من BTC/USDT ← BTC-USDT
      - استدعاء تنفيذ BUY/SELL/CLOSE من SoldierBase
    """

    def __init__(self, user_id):
        super().__init__(user_id, exchange="okx")

    # ============================
    # SYMBOL NORMALIZATION
    # ============================

    def normalize(self, symbol):
        """
        تحويل BTC/USDT → BTC-USDT
        """
        return symbol.replace("/", "-").upper()

    # ============================
    # EXECUTE BUY
    # ============================

    async def buy(self, symbol, usd):
        symbol = self.normalize(symbol)
        return await self.execute_buy(symbol, usd)

    # ============================
    # EXECUTE SELL
    # ============================

    async def sell(self, symbol, usd):
        symbol = self.normalize(symbol)
        return await self.execute_sell(symbol, usd)

    # ============================
    # CLOSE POSITION
    # ============================

    async def close(self, symbol):
        symbol = self.normalize(symbol)
        return await self.execute_close(symbol)

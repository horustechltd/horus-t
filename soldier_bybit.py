# ================================================================
# HORUS BYBIT SOLDIER (Async)
# ================================================================
#  الجندي الخاص ببورصة BYBIT
#  يرث من SoldierBase
#  ويضيف symbol mapping حسب تنسيق BYBIT
# ================================================================

from soldiers.soldier_base import SoldierBase
import logging

log = logging.getLogger("SoldierBybit")


class SoldierBybit(SoldierBase):
    """
    Soldier for Bybit customers.
    Bybit spot format:
        BTCUSDT (مثل Binance)
    """

    def __init__(self, user_id):
        super().__init__(user_id, exchange="bybit")

    # ============================
    # SYMBOL NORMALIZATION
    # ============================

    def normalize(self, symbol):
        """
        تحويل BTC/USDT → BTCUSDT
        نفس Binance format
        """
        return symbol.replace("/", "").upper()

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

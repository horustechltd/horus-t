# ============================================================
# HORUS CLIENT SERVICE BOT (User_Interface.py)
# Arabic Edition - Telegram Bot
# ============================================================

import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardMarkup, InlineKeyboardButton

from core.database import AsyncSessionLocal
from core.models import Client, ExecutionLog
from config.config import USER_BOT_TOKEN

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("Horus-UserBot")

bot = Bot(USER_BOT_TOKEN)
dp = Dispatcher()


# ============================================================
# HELPERS
# ============================================================

async def get_or_create_client(session, tg_id):
    """اضافة مستخدم جديد أو ارجاع الموجود"""
    user = await session.get(Client, str(tg_id))
    if not user:
        new_user = Client(
            client_id=str(tg_id),
            exchange="",
            active=False,
            approved=False
        )
        session.add(new_user)
        await session.commit()
        return new_user
    return user


def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 تفعيل / تعديل API", callback_data="cfg_api")],
            [InlineKeyboardButton(text="📊 حالة الحساب", callback_data="acc_status")],
            [InlineKeyboardButton(text="📈 صفقاتى", callback_data="my_trades")],
            [InlineKeyboardButton(text="🚫 إيقاف الخدمة", callback_data="disable_srv")],
        ]
    )


# ============================================================
# START COMMAND
# ============================================================

@dp.message(Command("start"))
async def start_cmd(msg: types.Message):
    async with AsyncSessionLocal() as session:
        client = await get_or_create_client(session, msg.from_user.id)

    welcome = (
        "👋 أهلاً بك في *نظام حورس للعملاء*\n\n"
        "هذا البوت يسمح لك:\n"
        "• تفعيل مفاتيح API\n"
        "• متابعة صفقاتك\n"
        "• معرفة سبب عدم دخولك صفقة\n"
        "• إيقاف وتشغيل الخدمة\n\n"
        "اضغط على القائمة ↓"
    )

    await msg.answer(welcome, reply_markup=main_menu(), parse_mode="Markdown")


# ============================================================
# CALLBACK HANDLERS
# ============================================================

@dp.callback_query(lambda c: c.data == "cfg_api")
async def cb_cfg_api(cb: types.CallbackQuery):
    msg = (
        "🔧 *إعدادات API*\n\n"
        "أرسل المفاتيح بالشكل التالي:\n"
        "`BINANCE:API_KEY:SECRET`\n"
        "`OKX:API_KEY:SECRET:PASSPHRASE`\n"
        "`BYBIT:API_KEY:SECRET`\n"
    )
    await cb.message.edit_text(msg, parse_mode="Markdown")
    await cb.answer()


@dp.callback_query(lambda c: c.data == "acc_status")
async def cb_acc_status(cb: types.CallbackQuery):
    async with AsyncSessionLocal() as session:
        user = await session.get(Client, str(cb.from_user.id))

        if not user:
            await cb.message.edit_text("❌ لم يتم العثور على بياناتك.")
            return

        txt = (
            f"🧾 *بيانات حسابك*\n"
            f"- حالة الخدمة: {'مفعلة ✅' if user.active else 'متوقفة ❌'}\n"
            f"- حالة الموافقة: {'✔ موافق عليه' if user.approved else '⏳ بانتظار الموافقة'}\n"
            f"- البورصة: {user.exchange or 'غير محددة'}\n"
            f"- الرصيد المسجل: {user.balance_usdt} USDT\n"
            f"- نسبة الدخول: {user.allocation}%\n"
            f"- حد السبريد: {user.spread_limit}%\n"
        )

        await cb.message.edit_text(txt, reply_markup=main_menu(), parse_mode="Markdown")
        await cb.answer()


@dp.callback_query(lambda c: c.data == "my_trades")
async def cb_trades(cb: types.CallbackQuery):
    async with AsyncSessionLocal() as session:
        rows = await session.execute(
            ExecutionLog.__table__.select().where(
                ExecutionLog.client_id == str(cb.from_user.id)
            ).order_by(ExecutionLog.time.desc()).limit(20)
        )
        logs = rows.fetchall()

    if not logs:
        await cb.message.edit_text("لا توجد صفقات مسجلة حتى الآن.")
        return

    lines = ["📈 *آخر صفقاتك:* \n"]
    for log_row in logs:
        log = log_row[0] if isinstance(log_row, tuple) else log_row
        lines.append(
            f"{log.symbol} — {log.amount} USDT — {log.price}\n"
            f"المنصة: {log.exchange} — {log.status}\n"
        )

    await cb.message.edit_text("\n".join(lines), parse_mode="Markdown")
    await cb.answer()


@dp.callback_query(lambda c: c.data == "disable_srv")
async def cb_disable(cb: types.CallbackQuery):
    async with AsyncSessionLocal() as session:
        client = await session.get(Client, str(cb.from_user.id))
        client.active = False
        await session.commit()

    await cb.message.edit_text("❌ تم إيقاف الخدمة. يمكنك إعادة تفعيلها من خلال /start")
    await cb.answer()


# ============================================================
# HANDLE API INPUT
# ============================================================

@dp.message()
async def handle_api_input(msg: types.Message):
    """
    العميل يرسل صيغة المفاتيح:
    BINANCE:KEY:SECRET
    """
    parts = msg.text.split(":")
    if len(parts) not in (3, 4):
        await msg.answer("❌ صيغة غير صحيحة.")
        return

    exchange = parts[0].upper()
    if exchange not in ("BINANCE", "OKX", "BYBIT"):
        await msg.answer("❌ اسم منصة غير صحيح.")
        return

    async with AsyncSessionLocal() as session:
        client = await get_or_create_client(session, msg.from_user.id)
        client.exchange = exchange
        client.api_key = parts[1]
        client.api_secret = parts[2]
        client.extra_password = parts[3] if len(parts) == 4 else None
        client.approved = True
        client.active = True

        await session.commit()

    await msg.answer("✅ تم تسجيل مفاتيحك وتفعيل الخدمة.\n\nاكتب /start لعرض القائمة.")

# ============================================================
# LAUNCH
# ============================================================

async def main():
    log.info("🤖 User Bot Online")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

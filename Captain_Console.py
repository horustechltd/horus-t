# ================================================================
# HORUS - CAPTAIN CONSOLE (Telegram Bot)
# النسخة الاحترافية - عربي بالكامل
# ================================================================

import asyncio
import logging
import json
import time
import os
import subprocess

from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CallbackQueryHandler,
    CommandHandler, MessageHandler, ContextTypes, filters
)

import redis.asyncio as redis
from motor.motor_asyncio import AsyncIOMotorClient


# ================================================================
# الإعدادات العامة
# ================================================================

TELEGRAM_TOKEN = os.getenv("CAPTAIN_BOT_TOKEN")  # ضع التوكن في البيئة
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://127.0.0.1:27017")
DB_NAME = "HorusDB"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("CaptainConsole")

# Redis
r = redis.from_url(REDIS_URL, decode_responses=True)

# Mongo
mc = AsyncIOMotorClient(MONGO_URL)
db = mc[DB_NAME]

# حالة انتظار إدخال من الكابتن
pending_input = {}  # { user_id : {"mode": "...", "extra": "..."} }


# ================================================================
# رسائل الواجهة
# ================================================================

MAIN_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("📊 إرسال إشارة", callback_data="menu_signals")],
    [InlineKeyboardButton("⚙️ إعدادات الكابتن", callback_data="menu_settings")],
    [InlineKeyboardButton("👥 إدارة العملاء", callback_data="menu_clients")],
    [InlineKeyboardButton("🔑 مفاتيح API", callback_data="menu_keys")],
    [InlineKeyboardButton("📈 التقارير", callback_data="menu_reports")],
    [InlineKeyboardButton("👁️ التحكم في عين الكابتن", callback_data="menu_eye")],
    [InlineKeyboardButton("🛠️ إعادة تشغيل الخدمات", callback_data="menu_restart")]
])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحباً بك يا كابتن 👑\n\nاختر من القائمة التالية:",
        reply_markup=MAIN_MENU
    )
# ================================================================
# قسم إرسال الإشارات
# ================================================================

SIGNAL_MENU = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🟢 شراء (BUY)", callback_data="sig_buy"),
        InlineKeyboardButton("🔴 بيع (SELL)", callback_data="sig_sell")
    ],
    [
        InlineKeyboardButton("⚡ شراء خطير (RISKY BUY)", callback_data="sig_risky")
    ],
    [
        InlineKeyboardButton("🔁 إغلاق الصفقة (CLOSE)", callback_data="sig_close"),
        InlineKeyboardButton("⛔ إلغاء الأمر (CANCEL)", callback_data="sig_cancel")
    ],
    [InlineKeyboardButton("⬅️ رجوع", callback_data="back_main")]
])


async def handle_menu_signals(update: Update, context):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "اختر نوع الإشارة:",
        reply_markup=SIGNAL_MENU
    )


# ------------------------------------------------------------
# مرحلة طلب إدخال البيانات من الكابتن
# ------------------------------------------------------------

async def ask_signal_input(update: Update, context, mode):
    query = update.callback_query
    await query.answer()

    pending_input[query.from_user.id] = {"mode": mode}

    await query.edit_message_text(
        "💬 أدخل الإشارة بهذا الشكل:\n\n"
        "**العملة ثم المسافة ثم المبلغ بالدولار**\n\n"
        "مثال:\n`BTC/USDT 150`\n\n"
        "⬅️ أرسل الآن:",
        parse_mode="Markdown"
    )


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return

    user_id = update.message.from_user.id

    if user_id not in pending_input:
        return  # مش منتظر إدخال من الكابتن

    mode = pending_input[user_id]["mode"]
    del pending_input[user_id]

    try:
        parts = update.message.text.split()
        symbol = parts[0].upper()
        usd = float(parts[1])
    except:
        await update.message.reply_text("❌ صيغة غير صحيحة. اكتب مثلاً:\n`BTC/USDT 100`")
        return

    # تجهيز الإشارة
    signal = {
        "signal_id": f"captain_{int(time.time())}",
        "symbol": symbol,
        "usd": usd,
        "timestamp": time.time(),
        "source": "CAPTAIN"
    }

    if mode == "buy":
        signal["action"] = "BUY"
        signal["risk"] = "NORMAL"

    elif mode == "sell":
        signal["action"] = "SELL"
        signal["risk"] = "NORMAL"

    elif mode == "risky":
        signal["action"] = "BUY"
        signal["risk"] = "RISKY"  # يذهب للـ Smart Entry Engine

    elif mode == "close":
        signal["action"] = "CLOSE"

    elif mode == "cancel":
        signal["action"] = "CANCEL"

    # إرسال إلى Brain
    await r.publish("HORUS_BRAIN_SIGNALS", json.dumps(signal))

    await update.message.reply_text(
        f"✅ **تم إرسال الإشارة بنجاح**\n\n"
        f"العملية: {signal['action']}\n"
        f"العملة: {signal['symbol']}\n"
        f"المبلغ: {signal.get('usd','-')}\n"
        f"الخطورة: {signal.get('risk','-')}",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU
    )


# ------------------------------------------------------------
# أزرار تنفيذ الإشارات: BUY / SELL / RISKY / CLOSE / CANCEL
# ------------------------------------------------------------

async def handle_signal_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    event = query.data

    if event == "sig_buy":
        return await ask_signal_input(update, context, "buy")

    elif event == "sig_sell":
        return await ask_signal_input(update, context, "sell")

    elif event == "sig_risky":
        return await ask_signal_input(update, context, "risky")

    elif event == "sig_close":
        return await ask_signal_input(update, context, "close")

    elif event == "sig_cancel":
        return await ask_signal_input(update, context, "cancel")
# ================================================================
# قسم إعدادات الكابتن (العمولة – السبريد – Smart Entry – التنبيهات)
# ================================================================

SETTINGS_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("💰 تعديل نسبة العمولة", callback_data="set_commission")],
    [InlineKeyboardButton("📉 تعديل نسبة السبريد", callback_data="set_spread")],
    [InlineKeyboardButton("⚡ تشغيل/إيقاف Smart Entry", callback_data="toggle_smart")],
    [InlineKeyboardButton("🔔 تشغيل/إيقاف التنبيهات", callback_data="toggle_notifications")],
    [InlineKeyboardButton("⚠️ وضع العملات الخطرة", callback_data="toggle_risk_mode")],
    [InlineKeyboardButton("⬅️ رجوع", callback_data="back_main")]
])


async def handle_menu_settings(update: Update, context):
    query = update.callback_query
    await query.answer()

    # قراءة الإعدادات الحالية
    s = await db.captain_settings.find_one({"captain_id": "master"}) or {}

    txt = (
        "⚙️ **إعدادات الكابتن الحالية**\n\n"
        f"💰 العمولة: {s.get('commission_percent', 0)}%\n"
        f"📉 حد السبريد: {s.get('spread_limit', 1.0)}%\n"
        f"⚡ Smart Entry: {'مفعل' if s.get('smart_entry', True) else 'مغلق'}\n"
        f"🔔 التنبيهات: {'مفعلة' if s.get('notifications', True) else 'مغلقة'}\n"
        f"⚠️ العملات الخطرة: {'مسموحة' if s.get('risky_mode', True) else 'ممنوعة'}\n"
    )

    await query.edit_message_text(
        txt,
        parse_mode="Markdown",
        reply_markup=SETTINGS_MENU
    )


# ------------------------------------------------------------
# 👑 طلب إدخال قيمة جديدة لإعداد معين
# ------------------------------------------------------------

async def ask_setting_input(update: Update, context, mode, arabic_name):
    query = update.callback_query
    await query.answer()

    pending_input[query.from_user.id] = {
        "mode": mode,
    }

    await query.edit_message_text(
        f"📝 أدخل قيمة **{arabic_name}** الجديدة:",
        parse_mode="Markdown"
    )


# ------------------------------------------------------------
# تحديث إعداد معين
# ------------------------------------------------------------

async def update_setting(user_id, mode, value, message):
    update_data = {mode: value}

    await db.captain_settings.update_one(
        {"captain_id": "master"},
        {"$set": update_data},
        upsert=True
    )

    return await message.reply_text(
        f"✅ تم تحديث الإعداد:\n**{mode} = {value}**",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU
    )


# ------------------------------------------------------------
# استقبال الإدخال من الكابتن لو في وضع "Pending"
# ------------------------------------------------------------

async def handle_setting_input(update: Update, context):
    user_id = update.message.from_user.id

    if user_id not in pending_input:
        return False

    mode = pending_input[user_id]["mode"]
    del pending_input[user_id]

    try:
        number = float(update.message.text)
    except:
        await update.message.reply_text("❌ أدخل رقم صحيح.")
        return True

    if mode == "commission":
        await update_setting(user_id, "commission_percent", number, update.message)

    elif mode == "spread":
        await update_setting(user_id, "spread_limit", number, update.message)

    return True


# ------------------------------------------------------------
# أزرار إعدادات الكابتن
# ------------------------------------------------------------

async def handle_settings_button(update: Update, context):
    query = update.callback_query
    await query.answer()

    event = query.data

    # طلب إدخال نسبة العمولة
    if event == "set_commission":
        return await ask_setting_input(update, context, "commission", "نسبة العمولة")

    # طلب إدخال نسبة السبريد
    elif event == "set_spread":
        return await ask_setting_input(update, context, "spread", "نسبة السبريد")

    # تفعيل/إيقاف Smart Entry
    elif event == "toggle_smart":
        s = await db.captain_settings.find_one({"captain_id": "master"}) or {}
        new_value = not s.get("smart_entry", True)

        await db.captain_settings.update_one(
            {"captain_id": "master"}, {"$set": {"smart_entry": new_value}}, upsert=True
        )

        return await query.edit_message_text(
            f"⚡ Smart Entry الآن: **{'مفعل' if new_value else 'مغلق'}**",
            parse_mode="Markdown",
            reply_markup=SETTINGS_MENU
        )

    # تفعيل/إيقاف التنبيهات
    elif event == "toggle_notifications":
        s = await db.captain_settings.find_one({"captain_id": "master"}) or {}
        new_value = not s.get("notifications", True)

        await db.captain_settings.update_one(
            {"captain_id": "master"}, {"$set": {"notifications": new_value}}, upsert=True
        )

        return await query.edit_message_text(
            f"🔔 التنبيهات الآن: **{'مفعلة' if new_value else 'مغلقة'}**",
            parse_mode="Markdown",
            reply_markup=SETTINGS_MENU
        )

    # تفعيل/إيقاف وضع العملات الخطرة
    elif event == "toggle_risk_mode":
        s = await db.captain_settings.find_one({"captain_id": "master"}) or {}
        new_value = not s.get("risky_mode", True)

        await db.captain_settings.update_one(
            {"captain_id": "master"}, {"$set": {"risky_mode": new_value}}, upsert=True
        )

        return await query.edit_message_text(
            f"⚠️ وضع العملات الخطرة الآن: **{'مسموحة' if new_value else 'ممنوعة'}**",
            parse_mode="Markdown",
            reply_markup=SETTINGS_MENU
        )

# ================================================================
# 📌 إدارة العملاء – Client Management
# ================================================================

CLIENT_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("➕ إضافة عميل جديد", callback_data="client_add")],
    [InlineKeyboardButton("📝 تعديل بيانات عميل", callback_data="client_edit")],
    [InlineKeyboardButton("📊 تقرير عميل", callback_data="client_report")],
    [InlineKeyboardButton("🚫 إيقاف / تفعيل عميل", callback_data="client_toggle")],
    [InlineKeyboardButton("🗑 حذف عميل", callback_data="client_delete")],
    [InlineKeyboardButton("👥 قائمة العملاء", callback_data="client_list")],
    [InlineKeyboardButton("⬅️ رجوع", callback_data="back_main")]
])


async def handle_menu_clients(update: Update, context):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "👥 **إدارة العملاء**\n\nاختر العملية المطلوبة:",
        parse_mode="Markdown",
        reply_markup=CLIENT_MENU
    )


# -------------------------------------------------------------
# 🔹 إضافة عميل جديد - طلب ID
# -------------------------------------------------------------

async def ask_new_client_id(update: Update, context):
    query = update.callback_query
    await query.answer()

    pending_input[query.from_user.id] = {"mode": "new_client_id"}

    await query.edit_message_text(
        "🆔 أدخل **معرف العميل Client ID** الجديد:",
        parse_mode="Markdown"
    )


# استقبال Client ID ثم حفظه
async def handle_new_client_id(update: Update, context):
    cid = update.message.text.strip()
    user_id = update.message.from_user.id

    await db.clients.update_one(
        {"client_id": cid},
        {
            "$set": {
                "client_id": cid,
                "active": False,
                "approved": False,
                "balance_usdt": 0,
                "allocation": 10,
                "spread_limit": 1.0,
                "created_at": datetime.utcnow(),
            }
        },
        upsert=True
    )

    del pending_input[user_id]

    await update.message.reply_text(
        f"✅ تم إضافة العميل:\n**{cid}**\n\n⚠️ العميل غير مفعل وغير مقبول حتى الآن.",
        parse_mode="Markdown",
        reply_markup=CLIENT_MENU
    )


# -------------------------------------------------------------
# 🔹 تعديل بيانات عميل
# -------------------------------------------------------------

CLIENT_EDIT_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("💵 تعديل الرصيد", callback_data="edit_balance")],
    [InlineKeyboardButton("📈 تعديل نسبة الدخول Allocation", callback_data="edit_alloc")],
    [InlineKeyboardButton("📉 تعديل حد السبريد", callback_data="edit_spread")],
    [InlineKeyboardButton("⬅️ رجوع", callback_data="client_menu")]
])


async def ask_edit_client(update: Update, context):
    query = update.callback_query
    await query.answer()

    pending_input[query.from_user.id] = {"mode": "edit_client_select"}

    await query.edit_message_text(
        "🆔 أدخل **Client ID** المراد تعديل بياناته:",
        parse_mode="Markdown"
    )


async def handle_edit_client_select(update: Update, context):
    cid = update.message.text.strip()
    user_id = update.message.from_user.id

    client = await db.clients.find_one({"client_id": cid})

    if not client:
        return await update.message.reply_text("❌ العميل غير موجود.")

    pending_input[user_id] = {"mode": "edit_client_menu", "cid": cid}

    await update.message.reply_text(
        f"📝 تعديل بيانات العميل **{cid}**",
        parse_mode="Markdown",
        reply_markup=CLIENT_EDIT_MENU
    )


# -------------------------------------------------------------
# 🔹 تعديل الرصيد
# -------------------------------------------------------------

async def ask_edit_balance(update: Update, context):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    cid = pending_input[uid]["cid"]

    pending_input[uid] = {"mode": "set_balance", "cid": cid}

    await query.edit_message_text(
        f"💵 أدخل الرصيد الجديد للعميل **{cid}** (بالدولار):",
        parse_mode="Markdown"
    )


async def handle_set_balance(update: Update, context):
    uid = update.message.from_user.id
    cid = pending_input[uid]["cid"]
    del pending_input[uid]

    try:
        balance = float(update.message.text)
    except:
        return await update.message.reply_text("❌ أدخل رقم صحيح.")

    await db.clients.update_one(
        {"client_id": cid},
        {"$set": {"balance_usdt": balance}}
    )

    await update.message.reply_text(
        f"✅ تم تحديث رصيد العميل **{cid}** إلى {balance}$",
        parse_mode="Markdown",
        reply_markup=CLIENT_MENU
    )


# -------------------------------------------------------------
# 🔹 تعديل Allocation
# -------------------------------------------------------------

async def ask_edit_alloc(update: Update, context):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    cid = pending_input[uid]["cid"]

    pending_input[uid] = {"mode": "set_alloc", "cid": cid}

    await query.edit_message_text(
        f"📈 أدخل نسبة الدخول الجديدة **Allocation%** للعميل {cid}:",
        parse_mode="Markdown"
    )


async def handle_set_alloc(update: Update, context):
    uid = update.message.from_user.id
    cid = pending_input[uid]["cid"]
    del pending_input[uid]

    try:
        alloc = float(update.message.text)
    except:
        return await update.message.reply_text("❌ أدخل رقم صحيح.")

    await db.clients.update_one(
        {"client_id": cid},
        {"$set": {"allocation": alloc}}
    )

    await update.message.reply_text(
        f"📈 تم تعديل نسبة الدخول للعميل **{cid}** إلى {alloc}%",
        parse_mode="Markdown",
        reply_markup=CLIENT_MENU
    )


# -------------------------------------------------------------
# 🔹 تعديل حد السبريد
# -------------------------------------------------------------

async def ask_edit_spread(update: Update, context):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    cid = pending_input[uid]["cid"]

    pending_input[uid] = {"mode": "set_client_spread", "cid": cid}

    await query.edit_message_text(
        f"📉 أدخل حد السبريد الجديد للعميل {cid}:",
        parse_mode="Markdown"
    )


async def handle_set_client_spread(update: Update, context):
    uid = update.message.from_user.id
    cid = pending_input[uid]["cid"]
    del pending_input[uid]

    try:
        spread = float(update.message.text)
    except:
        return await update.message.reply_text("❌ أدخل رقم صحيح.")

    await db.clients.update_one(
        {"client_id": cid},
        {"$set": {"spread_limit": spread}}
    )

    await update.message.reply_text(
        f"📉 تم تعديل حد السبريد للعميل **{cid}** إلى {spread}%",
        parse_mode="Markdown",
        reply_markup=CLIENT_MENU
    )


# -------------------------------------------------------------
# 🔹 إيقاف / تفعيل عميل
# -------------------------------------------------------------

async def ask_toggle_client(update: Update, context):
    query = update.callback_query
    await query.answer()

    pending_input[query.from_user.id] = {"mode": "toggle_client"}

    await query.edit_message_text(
        "🆔 أدخل Client ID لإيقافه أو تفعيله:",
        parse_mode="Markdown"
    )


async def handle_toggle_client(update: Update, context):
    cid = update.message.text.strip()
    uid = update.message.from_user.id
    del pending_input[uid]

    client = await db.clients.find_one({"client_id": cid})

    if not client:
        return await update.message.reply_text("❌ العميل غير موجود.")

    new_state = not client.get("active", False)

    await db.clients.update_one(
        {"client_id": cid},
        {"$set": {"active": new_state}}
    )

    await update.message.reply_text(
        f"🔁 حالة العميل **{cid}** أصبحت: {'🟢 مفعل' if new_state else '🔴 متوقف'}",
        parse_mode="Markdown",
        reply_markup=CLIENT_MENU
    )


# -------------------------------------------------------------
# 🔹 حذف عميل
# -------------------------------------------------------------

async def ask_delete_client(update: Update, context):
    query = update.callback_query
    await query.answer()

    pending_input[query.from_user.id] = {"mode": "delete_client"}

    await query.edit_message_text(
        "🗑 أدخل Client ID لحذفه:",
        parse_mode="Markdown"
    )


async def handle_delete_client(update: Update, context):
    cid = update.message.text.strip()
    uid = update.message.from_user.id
    del pending_input[uid]

    await db.clients.delete_one({"client_id": cid})

    await update.message.reply_text(
        f"🗑 تم حذف العميل **{cid}** بنجاح.",
        parse_mode="Markdown",
        reply_markup=CLIENT_MENU
    )


# -------------------------------------------------------------
# 🔹 تقرير العميل
# -------------------------------------------------------------

async def ask_client_report(update: Update, context):
    query = update.callback_query
    await query.answer()

    pending_input[query.from_user.id] = {"mode": "client_report"}

    await query.edit_message_text(
        "📊 أدخل Client ID لعرض تقريره:",
        parse_mode="Markdown"
    )


async def handle_client_report(update: Update, context):
    cid = update.message.text.strip()
    uid = update.message.from_user.id
    del pending_input[uid]

    client = await db.clients.find_one({"client_id": cid})

    if not client:
        return await update.message.reply_text("❌ العميل غير موجود.")

    txt = (
        f"📊 **تقرير العميل {cid}**\n\n"
        f"🟢 مفعل: {client.get('active')}\n"
        f"💰 الرصيد: {client.get('balance_usdt')}$\n"
        f"📈 Allocation: {client.get('allocation')}%\n"
        f"📉 Spread: {client.get('spread_limit')}%\n"
        f"📆 تاريخ الإضافة: {client.get('created_at')}\n"
    )

    await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=CLIENT_MENU)


# -------------------------------------------------------------
# 🔹 قائمة العملاء
# -------------------------------------------------------------

async def handle_client_list(update: Update, context):
    query = update.callback_query
    await query.answer()

    clients = await db.clients.find().to_list(length=None)

    if not clients:
        return await query.edit_message_text("❌ لا يوجد عملاء.", reply_markup=CLIENT_MENU)

    txt = "👥 **قائمة العملاء:**\n\n"

    for c in clients:
        txt += (
            f"• {c['client_id']} — "
            f"{'🟢' if c.get('active') else '🔴'} — "
            f"{c.get('balance_usdt', 0)}$\n"
        )

    await query.edit_message_text(txt, parse_mode="Markdown", reply_markup=CLIENT_MENU)
# ================================================================
# 🔔 نظام التنبيهات Alerts & Notifications
# ================================================================

ALERTS_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("🚀 تنبيه عند دخول العملاء", callback_data="alert_entry")],
    [InlineKeyboardButton("❌ تنبيه فشل الدخول", callback_data="alert_fail")],
    [InlineKeyboardButton("📉 تنبيه السبريد العالي", callback_data="alert_spread")],
    [InlineKeyboardButton("⚡ تنبيه Smart Entry", callback_data="alert_smart")],
    [InlineKeyboardButton("🌊 تنبيه Waves", callback_data="alert_wave")],
    [InlineKeyboardButton("👤 تنبيه عميل جديد", callback_data="alert_new_client")],
    [InlineKeyboardButton("⚠️ تنبيه توقف عميل", callback_data="alert_client_stop")],
    [InlineKeyboardButton("⬅️ رجوع", callback_data="back_main")]
])


async def handle_menu_alerts(update: Update, context):
    query = update.callback_query
    await query.answer()

    s = await db.captain_settings.find_one({"captain_id": "master"}) or {}

    txt = (
        "🔔 **إعدادات نظام التنبيهات**\n\n"
        f"🚀 دخول العملاء: { 'مفعل' if s.get('alert_entry', True) else 'مغلق'}\n"
        f"❌ فشل الدخول: { 'مفعل' if s.get('alert_fail', True) else 'مغلق'}\n"
        f"📉 تنبيه سبريد: { 'مفعل' if s.get('alert_spread', True) else 'مغلق'}\n"
        f"⚡ Smart Entry: { 'مفعل' if s.get('alert_smart', True) else 'مغلق'}\n"
        f"🌊 تنبيه Waves: { 'مفعل' if s.get('alert_wave', True) else 'مغلق'}\n"
        f"👤 عميل جديد: { 'مفعل' if s.get('alert_new_client', True) else 'مغلق'}\n"
        f"⚠️ توقف عميل: { 'مفعل' if s.get('alert_client_stop', True) else 'مغلق'}\n"
    )

    await query.edit_message_text(
        txt,
        parse_mode="Markdown",
        reply_markup=ALERTS_MENU
    )


# -------------------------------------------------------------
# 🔧 دالة عامة لتبديل حالة أي تنبيه
# -------------------------------------------------------------

async def toggle_alert(query, alert_key):
    s = await db.captain_settings.find_one({"captain_id": "master"}) or {}
    new = not s.get(alert_key, True)

    await db.captain_settings.update_one(
        {"captain_id": "master"},
        {"$set": {alert_key: new}},
        upsert=True
    )

    await query.edit_message_text(
        f"🔧 تم تغيير حالة التنبيه **{alert_key}** إلى: "
        f"{'مفعل' if new else 'مغلق'}",
        parse_mode="Markdown",
        reply_markup=ALERTS_MENU
    )


# -------------------------------------------------------------
# ⛔ حالات التنبيهات التي يرسلها الـ Brain / Soldiers
# -------------------------------------------------------------

async def send_alert(alert_type, data):
    """
    alert_type: entry, fail, spread, smart, wave, new_client, client_stop
    data: dict يحتوي على تفاصيل الحدث
    """

    s = await db.captain_settings.find_one({"captain_id": "master"}) or {}
    if not s.get(f"alert_{alert_type}", True):
        return  # التنبيه مغلق

    msg = ""

    if alert_type == "entry":
        msg = (
            f"🚀 **دخول الصفقة**\n"
            f"العميل: `{data['client']}`\n"
            f"العملة: {data['symbol']}\n"
            f"القيمة: {data['amount']} USDT\n"
            f"السعر: {data['price']}"
        )

    elif alert_type == "fail":
        msg = (
            f"❌ **فشل دخول الصفقة**!\n"
            f"العميل: `{data['client']}`\n"
            f"العملة: {data['symbol']}\n"
            f"السبب: {data['reason']}"
        )

    elif alert_type == "spread":
        msg = (
            f"📉 **سبريد مرتفع**!\n"
            f"العميل: `{data['client']}`\n"
            f"العملة: {data['symbol']}\n"
            f"السبريد: {data['spread']}%"
        )

    elif alert_type == "smart":
        msg = (
            f"⚡ **Smart Entry Plan جاهزة**\n"
            f"العملة: {data['symbol']}\n"
            f"عدد الموجات: {data['waves']}\n"
            f"عامل WCF: {data['wcf']:.2f}"
        )

    elif alert_type == "wave":
        msg = (
            f"🌊 **تنفيذ موجة**\n"
            f"Wave رقم: {data['wave']}\n"
            f"Exchange: {data['ex']}"
        )

    elif alert_type == "new_client":
        msg = (
            f"👤 **عميل جديد انضم للنظام**\n"
            f"Client ID: {data['client']}"
        )

    elif alert_type == "client_stop":
        msg = (
            f"⚠️ **تم إيقاف عميل**\n"
            f"Client ID: {data['client']}"
        )

    try:
        await bot.send_message(CAPTAIN_ID, msg, parse_mode="Markdown")
    except:
        pass


# -------------------------------------------------------------
# أزرار التحكم في التنبيهات
# -------------------------------------------------------------

async def handle_alert_buttons(update: Update, context):
    query = update.callback_query
    await query.answer()

    key = query.data

    if key == "alert_entry":
        return await toggle_alert(query, "alert_entry")

    if key == "alert_fail":
        return await toggle_alert(query, "alert_fail")

    if key == "alert_spread":
        return await toggle_alert(query, "alert_spread")

    if key == "alert_smart":
        return await toggle_alert(query, "alert_smart")

    if key == "alert_wave":
        return await toggle_alert(query, "alert_wave")

    if key == "alert_new_client":
        return await toggle_alert(query, "alert_new_client")

    if key == "alert_client_stop":
        return await toggle_alert(query, "alert_client_stop")
# ================================================================
# 💼 مركز التقارير تقارير الكابتن (Reports Center)
# ================================================================

REPORTS_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("📊 تقرير آخر عملية", callback_data="rep_last_action")],
    [InlineKeyboardButton("👥 تقرير دخول العملاء", callback_data="rep_client_entry")],
    [InlineKeyboardButton("❌ تقرير فشل العملاء", callback_data="rep_client_fail")],
    [InlineKeyboardButton("🌊 تقرير موجات Smart Entry", callback_data="rep_waves")],
    [InlineKeyboardButton("🧮 ملخص الأرباح", callback_data="rep_profit")],
    [InlineKeyboardButton("📘 آخر 100 Log", callback_data="rep_logs")],
    [InlineKeyboardButton("⬅️ رجوع", callback_data="back_main")]
])


async def handle_menu_reports(update: Update, context):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "💼 **مركز التقارير**\n\nاختر التقرير المطلوب:",
        parse_mode="Markdown",
        reply_markup=REPORTS_MENU
    )


# -------------------------------------------------------------
# 📌 تقرير آخر عملية للكابتن
# -------------------------------------------------------------

async def report_last_action(query):
    action = await db.actions.find().sort("timestamp", -1).limit(1).to_list(length=1)

    if not action:
        return await query.edit_message_text("❌ لا توجد عمليات.", reply_markup=REPORTS_MENU)

    act = action[0]

    txt = (
        "📊 **آخر عملية قام بها الكابتن**\n\n"
        f"العملة: {act['symbol']}\n"
        f"نوع العملية: {act['action']}\n"
        f"السعر: {act['price']}\n"
        f"التاريخ: {act['timestamp']}\n"
    )

    await query.edit_message_text(txt, parse_mode="Markdown", reply_markup=REPORTS_MENU)


# -------------------------------------------------------------
# 👥 تقرير دخول العملاء
# -------------------------------------------------------------

async def report_client_entry(query):
    logs = await db.execution_logs.find({"status": "executed"}).sort("time", -1).limit(25).to_list(length=None)

    if not logs:
        return await query.edit_message_text("❌ لا يوجد دخول عملاء.", reply_markup=REPORTS_MENU)

    txt = "👥 **آخر دخول للعملاء**\n\n"

    for l in logs:
        txt += (
            f"• `{l['client']}` — {l['symbol']} — {l['amount']} USDT — "
            f"سعر: {l['price']}\n"
        )

    await query.edit_message_text(txt, parse_mode="Markdown", reply_markup=REPORTS_MENU)


# -------------------------------------------------------------
# ❌ تقرير فشل العملاء
# -------------------------------------------------------------

async def report_client_fail(query):
    logs = await db.execution_logs.find({"status": "failed"}).sort("time", -1).limit(25).to_list(length=None)

    if not logs:
        return await query.edit_message_text("✔ لا يوجد فشل.", reply_markup=REPORTS_MENU)

    txt = "❌ **آخر حالات الفشل للعملاء**\n\n"

    for l in logs:
        txt += (
            f"• `{l['client']}` — {l['symbol']} — السبب: {l['reason']}\n"
        )

    await query.edit_message_text(txt, parse_mode="Markdown", reply_markup=REPORTS_MENU)


# -------------------------------------------------------------
# 🌊 تقرير موجات Smart Entry
# -------------------------------------------------------------

async def report_waves(query):
    waves = await db.wave_logs.find().sort("time", -1).limit(25).to_list(length=None)

    if not waves:
        return await query.edit_message_text("❌ لا توجد بيانات موجات.", reply_markup=REPORTS_MENU)

    txt = "🌊 **آخر موجات Smart Entry**\n\n"

    for w in waves:
        txt += (
            f"• Wave {w['wave']} — {w['exchange']} — {w['symbol']}\n"
            f"  حالة: {w['status']}\n"
        )

    await query.edit_message_text(txt, parse_mode="Markdown", reply_markup=REPORTS_MENU)


# -------------------------------------------------------------
# 🧮 ملخص الأرباح
# -------------------------------------------------------------

async def report_profit(query):
    trades = await db.trades.find().to_list(length=None)

    if not trades:
        return await query.edit_message_text("لا توجد بيانات أرباح.", reply_markup=REPORTS_MENU)

    total_profit = 0
    count = 0

    for t in trades:
        pnl = float(t.get("pnl", 0))
        total_profit += pnl
        count += 1

    txt = (
        "🧮 **ملخص الأرباح**\n\n"
        f"عدد الصفقات: {count}\n"
        f"إجمالي الأرباح: {total_profit:.2f} USDT\n"
    )

    await query.edit_message_text(txt, parse_mode="Markdown", reply_markup=REPORTS_MENU)


# -------------------------------------------------------------
# 📘 آخر 100 Log
# -------------------------------------------------------------

async def report_logs(query):
    logs = await db.system_logs.find().sort("time", -1).limit(100).to_list(length=None)

    if not logs:
        return await query.edit_message_text("لا يوجد Logs.", reply_markup=REPORTS_MENU)

    txt = "📘 **آخر 100 Log**\n\n"

    for l in logs[:40]:  # نعرض أول 40 فقط علشان تيليجرام
        txt += f"{l['time']} — {l['msg']}\n"

    await query.edit_message_text(txt, parse_mode="Markdown", reply_markup=REPORTS_MENU)


# -------------------------------------------------------------
# 🎛 موجه التقارير
# -------------------------------------------------------------

async def handle_report_buttons(update: Update, context):
    query = update.callback_query
    await query.answer()

    key = query.data

    if key == "rep_last_action":
        return await report_last_action(query)

    if key == "rep_client_entry":
        return await report_client_entry(query)

    if key == "rep_client_fail":
        return await report_client_fail(query)

    if key == "rep_waves":
        return await report_waves(query)

    if key == "rep_profit":
        return await report_profit(query)

    if key == "rep_logs":
        return await report_logs(query)

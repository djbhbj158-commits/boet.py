#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
بوت تمويل متكامل لتليجرام
الإصدار: 1.0
المطور: System
"""

import os
import json
import asyncio
import logging
import random
import string
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import aiofiles
from collections import defaultdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
from telegram.constants import ParseMode

# ==================== التهيئة والإعدادات الأساسية ====================

# تفعيل التسجيل للأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# توكن البوت
BOT_TOKEN = "8699966374:AAGCCGehxTQzGbEkBxIe7L3vecLPcvzGrHg"

# ايدي المديرين
ADMIN_IDS = [6615860762, 6130994941]

# حالات المحادثة
(
    MAIN_MENU,
    ADDING_POINTS,
    DEDUCTING_POINTS,
    ADDING_NUMBERS_FILE,
    DELETING_NUMBERS_FILE,
    ADDING_SUPPORT_USER,
    ADDING_CHANNEL_LINK,
    BANNING_USER,
    UNBANNING_USER,
    CHANGING_INVITE_REWARD,
    CHANGING_MEMBER_PRICE,
    ADDING_MANDATORY_CHANNEL,
    DELETING_MANDATORY_CHANNEL,
    CHANGING_WELCOME_MESSAGE,
    WAITING_FOR_MEMBERS_COUNT,
    WAITING_FOR_CHANNEL_LINK,
) = range(16)

# ==================== إدارة البيانات ====================

class DataManager:
    """إدارة جميع بيانات البوت"""
    
    def __init__(self):
        self.data_dir = Path("bot_data")
        self.data_dir.mkdir(exist_ok=True)
        
        # ملفات البيانات
        self.users_file = self.data_dir / "users.json"
        self.channels_file = self.data_dir / "channels.json"
        self.numbers_file = self.data_dir / "numbers.json"
        self.settings_file = self.data_dir / "settings.json"
        self.financing_file = self.data_dir / "financing.json"
        self.banned_users_file = self.data_dir / "banned_users.json"
        self.mandatory_channels_file = self.data_dir / "mandatory_channels.json"
        self.referrals_file = self.data_dir / "referrals.json"
        
        # تحميل البيانات
        self.users = self._load_data(self.users_file, {})
        self.channels = self._load_data(self.channels_file, {})
        self.numbers = self._load_data(self.numbers_file, {"numbers": [], "files": []})
        self.settings = self._load_data(self.settings_file, self._default_settings())
        self.financing = self._load_data(self.financing_file, {})
        self.banned_users = self._load_data(self.banned_users_file, [])
        self.mandatory_channels = self._load_data(self.mandatory_channels_file, [])
        self.referrals = self._load_data(self.referrals_file, {})
        
    def _default_settings(self):
        """الإعدادات الافتراضية"""
        return {
            "invite_reward": 10,
            "member_price": 8,
            "welcome_message": "مرحباً بك في بوت التمويل 🚀\nيمكنك تجميع النقاط وتمويل قنواتك",
            "support_username": "support_bot",
            "channel_link": "https://t.me/your_channel"
        }
    
    def _load_data(self, file_path, default):
        """تحميل البيانات من ملف JSON"""
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"خطأ في تحميل {file_path}: {e}")
        return default
    
    async def _save_data(self, file_path, data):
        """حفظ البيانات في ملف JSON"""
        try:
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"خطأ في حفظ {file_path}: {e}")
    
    async def save_all(self):
        """حفظ جميع البيانات"""
        await self._save_data(self.users_file, self.users)
        await self._save_data(self.channels_file, self.channels)
        await self._save_data(self.numbers_file, self.numbers)
        await self._save_data(self.settings_file, self.settings)
        await self._save_data(self.financing_file, self.financing)
        await self._save_data(self.banned_users_file, self.banned_users)
        await self._save_data(self.mandatory_channels_file, self.mandatory_channels)
        await self._save_data(self.referrals_file, self.referrals)
    
    # ========== إدارة المستخدمين ==========
    
    def get_user(self, user_id: int) -> Dict:
        """الحصول على بيانات مستخدم"""
        user_id = str(user_id)
        if user_id not in self.users:
            self.users[user_id] = {
                "points": 0,
                "referrals": 0,
                "referral_link": self._generate_referral_code(),
                "joined_date": datetime.now().isoformat(),
                "financing_count": 0,
                "total_spent_points": 0
            }
        return self.users[user_id]
    
    def _generate_referral_code(self) -> str:
        """توليد كود دعوة فريد"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    
    # ========== إدارة النقاط ==========
    
    def add_points(self, user_id: int, points: int) -> bool:
        """إضافة نقاط لمستخدم"""
        user_id = str(user_id)
        user = self.get_user(user_id)
        user["points"] += points
        return True
    
    def deduct_points(self, user_id: int, points: int) -> bool:
        """خصم نقاط من مستخدم"""
        user_id = str(user_id)
        user = self.get_user(user_id)
        if user["points"] >= points:
            user["points"] -= points
            return True
        return False
    
    # ========== إدارة الأرقام ==========
    
    def add_numbers_file(self, filename: str, numbers: List[str]) -> None:
        """إضافة ملف أرقام جديد"""
        self.numbers["files"].append({
            "name": filename,
            "count": len(numbers),
            "added_date": datetime.now().isoformat()
        })
        self.numbers["numbers"].extend(numbers)
    
    def get_available_numbers(self, count: int) -> List[str]:
        """الحصول على أرقام متاحة للتمويل"""
        if len(self.numbers["numbers"]) >= count:
            return [self.numbers["numbers"].pop(0) for _ in range(count)]
        return []
    
    def delete_numbers_file(self, filename: str) -> bool:
        """حذف ملف أرقام"""
        for i, file_info in enumerate(self.numbers["files"]):
            if file_info["name"] == filename:
                self.numbers["files"].pop(i)
                # ملاحظة: الأرقام تبقى لكن الملف يحذف من القائمة
                return True
        return False
    
    # ========== إدارة التمويل ==========
    
    def create_financing(self, user_id: int, channel_link: str, members_count: int, cost: int) -> str:
        """إنشاء عملية تمويل جديدة"""
        finance_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        user_id = str(user_id)
        
        self.financing[finance_id] = {
            "user_id": user_id,
            "channel_link": channel_link,
            "total_members": members_count,
            "added_members": 0,
            "status": "pending",
            "cost": cost,
            "created_at": datetime.now().isoformat(),
            "last_update": datetime.now().isoformat()
        }
        
        # تحديث إحصائيات المستخدم
        user = self.get_user(user_id)
        user["financing_count"] += 1
        user["total_spent_points"] += cost
        
        return finance_id
    
    def update_financing(self, finance_id: str, added: int = 1) -> Dict:
        """تحديث عملية تمويل"""
        if finance_id in self.financing:
            finance = self.financing[finance_id]
            finance["added_members"] += added
            finance["last_update"] = datetime.now().isoformat()
            
            if finance["added_members"] >= finance["total_members"]:
                finance["status"] = "completed"
            
            return finance
        return None
    
    def get_user_financing(self, user_id: int) -> List[Dict]:
        """الحصول على تمويلات مستخدم"""
        user_id = str(user_id)
        return [
            {**finance, "id": fid}
            for fid, finance in self.financing.items()
            if finance["user_id"] == user_id
        ]
    
    # ========== إدارة الحظر ==========
    
    def is_banned(self, user_id: int) -> bool:
        """التحقق من حظر المستخدم"""
        return str(user_id) in self.banned_users
    
    def ban_user(self, user_id: int, reason: str = "") -> None:
        """حظر مستخدم"""
        user_id = str(user_id)
        if user_id not in ADMIN_IDS:  # لا يمكن حظر المديرين
            self.banned_users.append({
                "user_id": user_id,
                "reason": reason,
                "banned_at": datetime.now().isoformat()
            })
    
    def unban_user(self, user_id: int) -> bool:
        """رفع الحظر عن مستخدم"""
        user_id = str(user_id)
        for i, banned in enumerate(self.banned_users):
            if banned["user_id"] == user_id:
                self.banned_users.pop(i)
                return True
        return False

# إنشاء كائن مدير البيانات
data_manager = DataManager()

# ==================== دوال التحقق من الاشتراك الإجباري ====================

async def check_mandatory_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> Tuple[bool, List[str]]:
    """التحقق من اشتراك المستخدم في القنوات الإجبارية"""
    if not data_manager.mandatory_channels:
        return True, []
    
    not_joined = []
    for channel in data_manager.mandatory_channels:
        try:
            member = await context.bot.get_chat_member(chat_id=channel["chat_id"], user_id=user_id)
            if member.status in ["left", "kicked"]:
                not_joined.append(channel)
        except:
            not_joined.append(channel)
    
    return len(not_joined) == 0, not_joined

async def get_mandatory_channels_keyboard() -> InlineKeyboardMarkup:
    """الحصول على كيبورد القنوات الإجبارية"""
    keyboard = []
    for channel in data_manager.mandatory_channels:
        keyboard.append([InlineKeyboardButton(
            text=f"اشترك في {channel['name']}",
            url=channel["link"]
        )])
    keyboard.append([InlineKeyboardButton(
        text="✅ تحقق من الاشتراك",
        callback_data="check_subscription"
    )])
    return InlineKeyboardMarkup(keyboard)

# ==================== دوال مساعدة ====================

def get_main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """الحصول على لوحة المفاتيح الرئيسية للمستخدم"""
    user = data_manager.get_user(user_id)
    
    keyboard = [
        [InlineKeyboardButton("💰 تجميع النقاط", callback_data="collect_points")],
        [InlineKeyboardButton("🚀 تمويل مشتركين", callback_data="finance_members")],
        [InlineKeyboardButton("📊 تمويلاتي", callback_data="my_financing")],
        [InlineKeyboardButton("📈 احصائياتي", callback_data="my_stats")],
        [InlineKeyboardButton("🆘 الدعم الفني", url=f"https://t.me/{data_manager.settings['support_username']}")],
        [InlineKeyboardButton("📢 قناة البوت", url=data_manager.settings["channel_link"])]
    ]
    
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """الحصول على لوحة تحكم المدير"""
    keyboard = [
        [InlineKeyboardButton("📊 احصائيات البوت", callback_data="admin_stats")],
        [InlineKeyboardButton("💰 شحن رصيد", callback_data="admin_add_points")],
        [InlineKeyboardButton("💸 خصم رصيد", callback_data="admin_deduct_points")],
        [InlineKeyboardButton("📁 اضافة ملف ارقام", callback_data="admin_add_numbers")],
        [InlineKeyboardButton("🗑 حذف ملف ارقام", callback_data="admin_delete_numbers")],
        [InlineKeyboardButton("👤 اضافة حساب دعم", callback_data="admin_add_support")],
        [InlineKeyboardButton("🔗 اضافة رابط قناة", callback_data="admin_add_channel")],
        [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban")],
        [InlineKeyboardButton("✅ رفع حظر", callback_data="admin_unban")],
        [InlineKeyboardButton("🎁 تغيير مكافأة الدعوة", callback_data="admin_change_reward")],
        [InlineKeyboardButton("💵 تغيير سعر العضو", callback_data="admin_change_price")],
        [InlineKeyboardButton("📢 اضافة قناة اجبارية", callback_data="admin_add_mandatory")],
        [InlineKeyboardButton("🗑 حذف قناة اجبارية", callback_data="admin_delete_mandatory")],
        [InlineKeyboardButton("✏️ تغيير رسالة الترحيب", callback_data="admin_change_welcome")],
        [InlineKeyboardButton("🔄 تحديث البيانات", callback_data="admin_refresh")]
    ]
    return InlineKeyboardMarkup(keyboard)

def format_number(num: int) -> str:
    """تنسيق الأرقام"""
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    if num >= 1000:
        return f"{num/1000:.1f}K"
    return str(num)

# ==================== أمر البدء ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج أمر البدء"""
    user = update.effective_user
    user_id = user.id
    
    # التحقق من الحظر
    if data_manager.is_banned(user_id):
        await update.message.reply_text("⛔️ أنت محظور من استخدام البوت")
        return ConversationHandler.END
    
    # التحقق من وجود رمز دعوة
    args = context.args
    if args and len(args) > 0:
        referrer_id = None
        for uid, udata in data_manager.users.items():
            if udata.get("referral_link") == args[0]:
                referrer_id = uid
                break
        
        if referrer_id and str(referrer_id) != str(user_id):
            # إضافة نقاط للداعي
            reward = data_manager.settings["invite_reward"]
            data_manager.add_points(int(referrer_id), reward)
            data_manager.get_user(int(referrer_id))["referrals"] += 1
            
            # تسجيل الدعوة
            if referrer_id not in data_manager.referrals:
                data_manager.referrals[referrer_id] = []
            data_manager.referrals[referrer_id].append({
                "user_id": str(user_id),
                "date": datetime.now().isoformat()
            })
            
            await context.bot.send_message(
                chat_id=int(referrer_id),
                text=f"🎉 مستخدم جديد انضم عبر رابط دعوتك!\n➕ تم اضافة {reward} نقطة الى رصيدك"
            )
    
    # التحقق من الاشتراك الإجباري
    is_subscribed, not_joined = await check_mandatory_subscription(user_id, context)
    if not is_subscribed:
        keyboard = await get_mandatory_channels_keyboard()
        await update.message.reply_text(
            "⚠️ يجب الاشتراك في القنوات التالية اولاً:\n"
            "بعد الاشتراك اضغط على زر التحقق",
            reply_markup=keyboard
        )
        return MAIN_MENU
    
    # تسجيل المستخدم
    user_data = data_manager.get_user(user_id)
    await data_manager.save_all()
    
    # رسالة الترحيب
    welcome_text = data_manager.settings["welcome_message"]
    welcome_text += f"\n\n👤 مرحباً {user.first_name}\n"
    welcome_text += f"🆔 ايديك: `{user_id}`\n"
    welcome_text += f"⭐️ نقاطك: {user_data['points']}\n"
    welcome_text += f"👥 عدد من دعوتهم: {user_data['referrals']}"
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard(user_id),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return MAIN_MENU

# ==================== معالج النصوص ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج الرسائل النصية"""
    user = update.effective_user
    user_id = user.id
    text = update.message.text
    
    # التحقق من الحظر
    if data_manager.is_banned(user_id):
        await update.message.reply_text("⛔️ أنت محظور من استخدام البوت")
        return ConversationHandler.END
    
    # التحقق من حالة المحادثة الحالية
    current_state = context.user_data.get("state", MAIN_MENU)
    
    # معالجة حسب الحالة
    if current_state == WAITING_FOR_MEMBERS_COUNT:
        return await handle_members_count(update, context)
    elif current_state == WAITING_FOR_CHANNEL_LINK:
        return await handle_channel_link(update, context)
    
    # إذا كان المستخدم مدير
    if user_id in ADMIN_IDS:
        if text == "🔧 لوحة التحكم":
            await update.message.reply_text(
                "🔧 لوحة تحكم المدير",
                reply_markup=get_admin_keyboard()
            )
            return MAIN_MENU
    
    return MAIN_MENU

# ==================== معالج الأزرار ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج الضغط على الأزرار"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = user.id
    data = query.data
    
    # التحقق من الحظر
    if data_manager.is_banned(user_id) and data != "check_subscription":
        await query.edit_message_text("⛔️ أنت محظور من استخدام البوت")
        return ConversationHandler.END
    
    # التحقق من الاشتراك الإجباري للمستخدمين العاديين
    if user_id not in ADMIN_IDS and data != "check_subscription":
        is_subscribed, not_joined = await check_mandatory_subscription(user_id, context)
        if not is_subscribed:
            keyboard = await get_mandatory_channels_keyboard()
            await query.edit_message_text(
                "⚠️ يجب الاشتراك في القنوات التالية اولاً:",
                reply_markup=keyboard
            )
            return MAIN_MENU
    
    # معالج التحقق من الاشتراك
    if data == "check_subscription":
        is_subscribed, not_joined = await check_mandatory_subscription(user_id, context)
        if is_subscribed:
            user_data = data_manager.get_user(user_id)
            welcome_text = data_manager.settings["welcome_message"]
            welcome_text += f"\n\n👤 مرحباً {user.first_name}\n"
            welcome_text += f"🆔 ايديك: `{user_id}`\n"
            welcome_text += f"⭐️ نقاطك: {user_data['points']}\n"
            welcome_text += f"👥 عدد من دعوتهم: {user_data['referrals']}"
            
            await query.edit_message_text(
                welcome_text,
                reply_markup=get_main_keyboard(user_id),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.edit_message_text(
                "❌ لم تشترك في جميع القنوات بعد",
                reply_markup=await get_mandatory_channels_keyboard()
            )
        return MAIN_MENU
    
    # ========== أزرار المستخدمين ==========
    
    if data == "collect_points":
        user_data = data_manager.get_user(user_id)
        referral_link = f"https://t.me/{(await context.bot.get_me()).username}?start={user_data['referral_link']}"
        
        text = (
            "🎁 **تجميع النقاط**\n\n"
            "شارك رابط الدعوة التالي مع اصدقائك\n"
            "عند دخول كل صديق عبر رابطك تحصل على نقاط\n\n"
            f"🏆 رصيد نقاطك الحالي: {user_data['points']}\n"
            f"👥 عدد من دعوتهم: {user_data['referrals']}\n"
            f"💰 مكافأة كل دعوة: {data_manager.settings['invite_reward']} نقطة\n\n"
            f"🔗 رابط الدعوة الخاص بك:\n`{referral_link}`\n\n"
            "شارك الرابط الآن وابدأ بجمع النقاط!"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]]
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return MAIN_MENU
    
    elif data == "finance_members":
        user_data = data_manager.get_user(user_id)
        member_price = data_manager.settings["member_price"]
        
        text = (
            "🚀 **تمويل مشتركين**\n\n"
            f"⭐️ رصيدك الحالي: {user_data['points']} نقطة\n"
            f"💵 سعر العضو الواحد: {member_price} نقطة\n\n"
            "ارسل الآن عدد الاعضاء الذي تريد تمويلهم\n"
            "مثال: 100\n\n"
            "⚠️ ملاحظة: يجب ان يكون البوت ادمن في قناتك"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]]
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        context.user_data["state"] = WAITING_FOR_MEMBERS_COUNT
        return WAITING_FOR_MEMBERS_COUNT
    
    elif data == "my_financing":
        finances = data_manager.get_user_financing(user_id)
        
        if not finances:
            text = "📊 لا يوجد لديك تمويلات حالية"
        else:
            text = "📊 **تمويلاتك**\n\n"
            for finance in finances[-5:]:  # آخر 5 تمويلات
                status_emoji = "✅" if finance["status"] == "completed" else "🔄"
                text += f"{status_emoji} القناة: {finance['channel_link'][:30]}...\n"
                text += f"   الاعضاء: {finance['added_members']}/{finance['total_members']}\n"
                text += f"   الحالة: {finance['status']}\n"
                text += f"   التكلفة: {finance['cost']} نقطة\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]]
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return MAIN_MENU
    
    elif data == "my_stats":
        user_data = data_manager.get_user(user_id)
        
        text = (
            "📈 **احصائياتك الشخصية**\n\n"
            f"🆔 الايدي: `{user_id}`\n"
            f"👤 اسم المستخدم: {user.first_name}\n"
            f"⭐️ رصيد النقاط: {user_data['points']}\n"
            f"👥 عدد الدعوات: {user_data['referrals']}\n"
            f"🚀 عدد عمليات التمويل: {user_data['financing_count']}\n"
            f"💸 اجمالي النقاط المنفقة: {user_data['total_spent_points']}\n"
            f"📅 تاريخ الانضمام: {user_data['joined_date'][:10]}"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]]
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return MAIN_MENU
    
    elif data == "back_to_main":
        user_data = data_manager.get_user(user_id)
        welcome_text = data_manager.settings["welcome_message"]
        welcome_text += f"\n\n👤 مرحباً {user.first_name}\n"
        welcome_text += f"🆔 ايديك: `{user_id}`\n"
        welcome_text += f"⭐️ نقاطك: {user_data['points']}\n"
        welcome_text += f"👥 عدد من دعوتهم: {user_data['referrals']}"
        
        await query.edit_message_text(
            welcome_text,
            reply_markup=get_main_keyboard(user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data["state"] = MAIN_MENU
        return MAIN_MENU
    
    # ========== أزرار المدير ==========
    
    if user_id in ADMIN_IDS:
        
        if data == "admin_stats":
            # احصائيات البوت
            total_users = len(data_manager.users)
            total_points = sum(u["points"] for u in data_manager.users.values())
            total_financing = len(data_manager.financing)
            total_numbers = len(data_manager.numbers["numbers"])
            total_files = len(data_manager.numbers["files"])
            
            text = (
                "📊 **احصائيات البوت**\n\n"
                f"👥 اجمالي المستخدمين: {total_users}\n"
                f"⭐️ اجمالي النقاط: {total_points}\n"
                f"🚀 عدد عمليات التمويل: {total_financing}\n"
                f"📁 عدد ملفات الارقام: {total_files}\n"
                f"📞 عدد الارقام المتاحة: {total_numbers}\n"
                f"🚫 عدد المحظورين: {len(data_manager.banned_users)}\n"
                f"📢 عدد القنوات الاجبارية: {len(data_manager.mandatory_channels)}"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=get_admin_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return MAIN_MENU
        
        elif data == "admin_add_points":
            context.user_data["admin_action"] = "add_points"
            await query.edit_message_text(
                "💰 **شحن رصيد مستخدم**\n\n"
                "ارسل ايدي المستخدم ثم المبلغ\n"
                "مثال:\n`123456789 100`\n\n"
                "او ارسل الغاء للالغاء",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")
                ]])
            )
            return ADDING_POINTS
        
        elif data == "admin_deduct_points":
            context.user_data["admin_action"] = "deduct_points"
            await query.edit_message_text(
                "💸 **خصم رصيد مستخدم**\n\n"
                "ارسل ايدي المستخدم ثم المبلغ\n"
                "مثال:\n`123456789 50`\n\n"
                "او ارسل الغاء للالغاء",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")
                ]])
            )
            return DEDUCTING_POINTS
        
        elif data == "admin_add_numbers":
            context.user_data["admin_action"] = "add_numbers"
            await query.edit_message_text(
                "📁 **اضافة ملف ارقام**\n\n"
                "ارسل ملف txt يحتوي على ارقام التليجرام\n"
                "كل رقم في سطر منفصل\n\n"
                "✅ الصيغة المقبولة: .txt فقط\n"
                "⚠️ الملف يجب ان يحتوي على ارقام فقط\n\n"
                "او ارسل الغاء للالغاء",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")
                ]])
            )
            return ADDING_NUMBERS_FILE
        
        elif data == "admin_delete_numbers":
            files = data_manager.numbers["files"]
            if not files:
                await query.edit_message_text(
                    "❌ لا يوجد ملفات ارقام لحذفها",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")
                    ]])
                )
                return MAIN_MENU
            
            keyboard = []
            for file in files:
                keyboard.append([InlineKeyboardButton(
                    f"🗑 {file['name']} ({file['count']} رقم)",
                    callback_data=f"delete_file_{file['name']}"
                )])
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")])
            
            await query.edit_message_text(
                "🗑 **اختر الملف المراد حذفه**",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
            return DELETING_NUMBERS_FILE
        
        elif data.startswith("delete_file_"):
            filename = data.replace("delete_file_", "")
            if data_manager.delete_numbers_file(filename):
                await query.edit_message_text(
                    f"✅ تم حذف الملف {filename} بنجاح",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")
                    ]])
                )
            else:
                await query.edit_message_text(
                    f"❌ فشل حذف الملف {filename}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")
                    ]])
                )
            return MAIN_MENU
        
        elif data == "admin_add_support":
            context.user_data["admin_action"] = "add_support"
            await query.edit_message_text(
                "👤 **اضافة حساب دعم**\n\n"
                "ارسل يوزر حساب الدعم الجديد\n"
                "مثال: @support_username\n\n"
                "او ارسل الغاء للالغاء",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")
                ]])
            )
            return ADDING_SUPPORT_USER
        
        elif data == "admin_add_channel":
            context.user_data["admin_action"] = "add_channel"
            await query.edit_message_text(
                "🔗 **اضافة رابط قناة البوت**\n\n"
                "ارسل رابط القناة الجديد\n"
                "مثال: https://t.me/your_channel\n\n"
                "او ارسل الغاء للالغاء",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")
                ]])
            )
            return ADDING_CHANNEL_LINK
        
        elif data == "admin_ban":
            context.user_data["admin_action"] = "ban"
            await query.edit_message_text(
                "🚫 **حظر مستخدم**\n\n"
                "ارسل ايدي المستخدم المراد حظره\n"
                "مثال: 123456789\n\n"
                "يمكنك اضافة سبب بعد الايدي\n"
                "مثال: 123456789  سبب الحظر\n\n"
                "او ارسل الغاء للالغاء",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")
                ]])
            )
            return BANNING_USER
        
        elif data == "admin_unban":
            context.user_data["admin_action"] = "unban"
            await query.edit_message_text(
                "✅ **رفع حظر عن مستخدم**\n\n"
                "ارسل ايدي المستخدم المراد رفع الحظر عنه\n"
                "مثال: 123456789\n\n"
                "او ارسل الغاء للالغاء",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")
                ]])
            )
            return UNBANNING_USER
        
        elif data == "admin_change_reward":
            context.user_data["admin_action"] = "change_reward"
            current = data_manager.settings["invite_reward"]
            await query.edit_message_text(
                f"🎁 **تغيير مكافأة الدعوة**\n\n"
                f"المكافأة الحالية: {current} نقطة\n\n"
                "ارسل القيمة الجديدة (رقم فقط)\n"
                "مثال: 15\n\n"
                "او ارسل الغاء للالغاء",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")
                ]])
            )
            return CHANGING_INVITE_REWARD
        
        elif data == "admin_change_price":
            context.user_data["admin_action"] = "change_price"
            current = data_manager.settings["member_price"]
            await query.edit_message_text(
                f"💵 **تغيير سعر العضو**\n\n"
                f"السعر الحالي: {current} نقطة للعضو الواحد\n\n"
                "ارسل القيمة الجديدة (رقم فقط)\n"
                "مثال: 10\n\n"
                "او ارسل الغاء للالغاء",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")
                ]])
            )
            return CHANGING_MEMBER_PRICE
        
        elif data == "admin_add_mandatory":
            context.user_data["admin_action"] = "add_mandatory"
            await query.edit_message_text(
                "📢 **اضافة قناة اجبارية**\n\n"
                "ارسل معلومات القناة بهذا التنسيق:\n"
                "اسم القناة | رابط القناة | ايدي القناة\n\n"
                "مثال:\n"
                "قناتي | https://t.me/my_channel | -100123456789\n\n"
                "او ارسل الغاء للالغاء",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")
                ]])
            )
            return ADDING_MANDATORY_CHANNEL
        
        elif data == "admin_delete_mandatory":
            if not data_manager.mandatory_channels:
                await query.edit_message_text(
                    "❌ لا يوجد قنوات اجبارية",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")
                    ]])
                )
                return MAIN_MENU
            
            keyboard = []
            for channel in data_manager.mandatory_channels:
                keyboard.append([InlineKeyboardButton(
                    f"🗑 {channel['name']}",
                    callback_data=f"delete_mandatory_{channel['chat_id']}"
                )])
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")])
            
            await query.edit_message_text(
                "🗑 **اختر القناة المراد حذفها**",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
            return DELETING_MANDATORY_CHANNEL
        
        elif data.startswith("delete_mandatory_"):
            chat_id = data.replace("delete_mandatory_", "")
            for i, channel in enumerate(data_manager.mandatory_channels):
                if str(channel["chat_id"]) == str(chat_id):
                    data_manager.mandatory_channels.pop(i)
                    await data_manager.save_all()
                    await query.edit_message_text(
                        "✅ تم حذف القناة الاجبارية بنجاح",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")
                        ]])
                    )
                    return MAIN_MENU
            
            await query.edit_message_text(
                "❌ لم يتم العثور على القناة",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")
                ]])
            )
            return MAIN_MENU
        
        elif data == "admin_change_welcome":
            context.user_data["admin_action"] = "change_welcome"
            current = data_manager.settings["welcome_message"]
            await query.edit_message_text(
                "✏️ **تغيير رسالة الترحيب**\n\n"
                f"الرسالة الحالية:\n{current}\n\n"
                "ارسل الرسالة الجديدة\n"
                "يمكنك استخدام Markdown للتنسيق\n\n"
                "او ارسل الغاء للالغاء",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")
                ]])
            )
            return CHANGING_WELCOME_MESSAGE
        
        elif data == "admin_refresh":
            await query.edit_message_text(
                "🔄 تم تحديث البيانات",
                reply_markup=get_admin_keyboard()
            )
            return MAIN_MENU
        
        elif data == "back_to_admin":
            await query.edit_message_text(
                "🔧 لوحة تحكم المدير",
                reply_markup=get_admin_keyboard()
            )
            context.user_data["state"] = MAIN_MENU
            return MAIN_MENU
    
    return MAIN_MENU

# ==================== معالج عدد الاعضاء ====================

async def handle_members_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج استلام عدد الاعضاء للتمويل"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if text.lower() == "الغاء":
        await update.message.reply_text(
            "✅ تم الغاء العملية",
            reply_markup=get_main_keyboard(user_id)
        )
        context.user_data["state"] = MAIN_MENU
        return MAIN_MENU
    
    try:
        count = int(text)
        if count <= 0 or count > 1000:
            await update.message.reply_text("❌ الرجاء ادخال عدد صحيح بين 1 و 1000")
            return WAITING_FOR_MEMBERS_COUNT
        
        user_data = data_manager.get_user(user_id)
        member_price = data_manager.settings["member_price"]
        total_cost = count * member_price
        
        if user_data["points"] < total_cost:
            await update.message.reply_text(
                f"❌ رصيدك غير كافي\n"
                f"المطلوب: {total_cost} نقطة\n"
                f"رصيدك: {user_data['points']} نقطة"
            )
            context.user_data["state"] = MAIN_MENU
            return MAIN_MENU
        
        context.user_data["finance"] = {
            "count": count,
            "cost": total_cost
        }
        
        await update.message.reply_text(
            f"✅ تم حساب التكلفة\n"
            f"عدد الاعضاء: {count}\n"
            f"التكلفة: {total_cost} نقطة\n"
            f"رصيدك المتبقي: {user_data['points'] - total_cost} نقطة\n\n"
            "الان ارسل رابط قناتك (تأكد ان البوت ادمن في القناة)"
        )
        
        context.user_data["state"] = WAITING_FOR_CHANNEL_LINK
        return WAITING_FOR_CHANNEL_LINK
        
    except ValueError:
        await update.message.reply_text("❌ الرجاء ادخال رقم صحيح")
        return WAITING_FOR_MEMBERS_COUNT

# ==================== معالج رابط القناة ====================

async def handle_channel_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج استلام رابط القناة للتمويل"""
    user_id = update.effective_user.id
    channel_link = update.message.text
    
    if "t.me/" not in channel_link and "telegram.me/" not in channel_link:
        await update.message.reply_text("❌ الرجاء ارسال رابط قناة صحيح")
        return WAITING_FOR_CHANNEL_LINK
    
    finance_data = context.user_data.get("finance")
    if not finance_data:
        await update.message.reply_text("❌ حدث خطأ، الرجاء المحاولة مرة اخرى")
        context.user_data["state"] = MAIN_MENU
        return MAIN_MENU
    
    # خصم النقاط
    if not data_manager.deduct_points(user_id, finance_data["cost"]):
        await update.message.reply_text("❌ فشل خصم النقاط")
        context.user_data["state"] = MAIN_MENU
        return MAIN_MENU
    
    # انشاء عملية تمويل
    finance_id = data_manager.create_financing(
        user_id,
        channel_link,
        finance_data["count"],
        finance_data["cost"]
    )
    
    await data_manager.save_all()
    
    # بدء التمويل
    await update.message.reply_text(
        f"✅ **تم بدء التمويل بنجاح**\n\n"
        f"📊 معلومات التمويل:\n"
        f"عدد الاعضاء: {finance_data['count']}\n"
        f"التكلفة: {finance_data['cost']} نقطة\n"
        f"الحالة: جاري التمويل...\n\n"
        f"سيتم اعلامك عند اضافة كل عضو",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # اشعار الادارة
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"🚀 **تمويل جديد**\n\n"
                f"👤 المستخدم: `{user_id}`\n"
                f"🔗 القناة: {channel_link}\n"
                f"👥 العدد: {finance_data['count']}\n"
                f"💰 التكلفة: {finance_data['cost']}\n"
                f"🆔 معرف التمويل: `{finance_id}`",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
    
    # بدء عملية التمويل في الخلفية
    asyncio.create_task(process_financing(update.get_bot(), finance_id))
    
    # عرض القائمة الرئيسية
    user_data = data_manager.get_user(user_id)
    welcome_text = data_manager.settings["welcome_message"]
    welcome_text += f"\n\n👤 مرحباً {update.effective_user.first_name}\n"
    welcome_text += f"🆔 ايديك: `{user_id}`\n"
    welcome_text += f"⭐️ نقاطك: {user_data['points']}\n"
    welcome_text += f"👥 عدد من دعوتهم: {user_data['referrals']}"
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard(user_id),
        parse_mode=ParseMode.MARKDOWN
    )
    
    context.user_data["state"] = MAIN_MENU
    return MAIN_MENU

# ==================== عملية التمويل ====================

async def process_financing(bot, finance_id: str):
    """معالجة عملية التمويل في الخلفية"""
    finance = data_manager.financing.get(finance_id)
    if not finance:
        return
    
    user_id = int(finance["user_id"])
    remaining = finance["total_members"] - finance["added_members"]
    
    for i in range(remaining):
        # الحصول على رقم من القائمة
        numbers = data_manager.get_available_numbers(1)
        if not numbers:
            # لا يوجد ارقام كافية
            await bot.send_message(
                user_id,
                "⚠️ نفذت الارقام المتاحة للتمويل\n"
                "سيتم اكمال التمويل لاحقاً عند توفر ارقام جديدة"
            )
            for admin_id in ADMIN_IDS:
                await bot.send_message(
                    admin_id,
                    f"⚠️ نفذت الارقام في عملية التمويل {finance_id}"
                )
            break
        
        # محاولة اضافة العضو
        try:
            # هنا يتم استخدام الارقام لاضافة الاعضاء
            # هذه محاكاة للعملية
            await asyncio.sleep(2)  # محاكاة وقت الاضافة
            
            finance = data_manager.update_financing(finance_id)
            
            # ارسال اشعار للمستخدم
            await bot.send_message(
                user_id,
                f"✅ تم اضافة عضو جديد في قناتك\n"
                f"تقدم التمويل: {finance['added_members']}/{finance['total_members']}"
            )
            
            await data_manager.save_all()
            
        except Exception as e:
            logger.error(f"خطأ في اضافة العضو: {e}")
            continue
    
    if finance["added_members"] >= finance["total_members"]:
        await bot.send_message(
            user_id,
            f"✅ **اكتمل التمويل بنجاح**\n\n"
            f"تم اضافة {finance['total_members']} عضو الى قناتك",
            parse_mode=ParseMode.MARKDOWN
        )

# ==================== معالج ملفات الارقام ====================

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج استلام الملفات"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ هذه الخاصية للمديرين فقط")
        return MAIN_MENU
    
    current_state = context.user_data.get("state", MAIN_MENU)
    
    if current_state != ADDING_NUMBERS_FILE:
        await update.message.reply_text("❌ انت غير في وضع اضافة ملفات")
        return MAIN_MENU
    
    document = update.message.document
    
    # التحقق من صيغة الملف
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ فقط ملفات txt مسموحة")
        return ADDING_NUMBERS_FILE
    
    # تحميل الملف
    file = await context.bot.get_file(document.file_id)
    file_content = await file.download_as_bytearray()
    
    try:
        # قراءة الارقام من الملف
        content = file_content.decode('utf-8')
        numbers = [line.strip() for line in content.split('\n') if line.strip()]
        
        # التحقق من صحة الارقام
        valid_numbers = []
        for num in numbers:
            # التحقق من ان الرقم يبدأ بـ 00963 او +963 او 963
            if num.startswith(('00963', '+963', '963')):
                valid_numbers.append(num)
        
        if not valid_numbers:
            await update.message.reply_text("❌ لم يتم العثور على ارقام صالحة في الملف")
            return ADDING_NUMBERS_FILE
        
        # حفظ الارقام
        data_manager.add_numbers_file(document.file_name, valid_numbers)
        await data_manager.save_all()
        
        await update.message.reply_text(
            f"✅ تم اضافة الملف بنجاح\n\n"
            f"اسم الملف: {document.file_name}\n"
            f"عدد الارقام الصالحة: {len(valid_numbers)}\n"
            f"اجمالي الارقام المتاحة: {len(data_manager.numbers['numbers'])}"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في قراءة الملف: {str(e)}")
    
    context.user_data["state"] = MAIN_MENU
    return MAIN_MENU

# ==================== معالج النصوص للمدير ====================

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE, current_state: int) -> int:
    """معالج النصوص للمديرين"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if text.lower() == "الغاء":
        await update.message.reply_text(
            "✅ تم الغاء العملية",
            reply_markup=get_admin_keyboard()
        )
        context.user_data["state"] = MAIN_MENU
        return MAIN_MENU
    
    if current_state == ADDING_POINTS:
        # شحن رصيد
        try:
            parts = text.split()
            if len(parts) != 2:
                await update.message.reply_text("❌ التنسيق خطأ. استخدم: ايدي المستخدم المبلغ")
                return ADDING_POINTS
            
            target_id = int(parts[0])
            points = int(parts[1])
            
            if points <= 0:
                await update.message.reply_text("❌ المبلغ يجب ان يكون اكبر من 0")
                return ADDING_POINTS
            
            data_manager.add_points(target_id, points)
            await data_manager.save_all()
            
            await update.message.reply_text(f"✅ تم اضافة {points} نقطة للمستخدم {target_id}")
            
            # اعلام المستخدم
            try:
                await context.bot.send_message(
                    target_id,
                    f"💰 تم شحن رصيدك ب {points} نقطة"
                )
            except:
                pass
            
        except ValueError:
            await update.message.reply_text("❌ الرجاء ادخال ارقام صحيحة")
            return ADDING_POINTS
    
    elif current_state == DEDUCTING_POINTS:
        # خصم رصيد
        try:
            parts = text.split()
            if len(parts) != 2:
                await update.message.reply_text("❌ التنسيق خطأ. استخدم: ايدي المستخدم المبلغ")
                return DEDUCTING_POINTS
            
            target_id = int(parts[0])
            points = int(parts[1])
            
            if points <= 0:
                await update.message.reply_text("❌ المبلغ يجب ان يكون اكبر من 0")
                return DEDUCTING_POINTS
            
            if data_manager.deduct_points(target_id, points):
                await data_manager.save_all()
                await update.message.reply_text(f"✅ تم خصم {points} نقطة من المستخدم {target_id}")
                
                # اعلام المستخدم
                try:
                    await context.bot.send_message(
                        target_id,
                        f"💸 تم خصم {points} نقطة من رصيدك"
                    )
                except:
                    pass
            else:
                await update.message.reply_text(f"❌ رصيد المستخدم غير كافي")
            
        except ValueError:
            await update.message.reply_text("❌ الرجاء ادخال ارقام صحيحة")
            return DEDUCTING_POINTS
    
    elif current_state == ADDING_SUPPORT_USER:
        # اضافة حساب دعم
        username = text.strip()
        if username.startswith('@'):
            username = username[1:]
        
        data_manager.settings["support_username"] = username
        await data_manager.save_all()
        
        await update.message.reply_text(f"✅ تم تعيين حساب الدعم: @{username}")
    
    elif current_state == ADDING_CHANNEL_LINK:
        # اضافة رابط قناة
        link = text.strip()
        if not link.startswith(('https://t.me/', 'http://t.me/')):
            link = f"https://t.me/{link}"
        
        data_manager.settings["channel_link"] = link
        await data_manager.save_all()
        
        await update.message.reply_text(f"✅ تم تعيين رابط القناة: {link}")
    
    elif current_state == BANNING_USER:
        # حظر مستخدم
        try:
            parts = text.split(maxsplit=1)
            target_id = int(parts[0])
            reason = parts[1] if len(parts) > 1 else ""
            
            if target_id in ADMIN_IDS:
                await update.message.reply_text("❌ لا يمكن حظر مدير")
                return BANNING_USER
            
            data_manager.ban_user(target_id, reason)
            await data_manager.save_all()
            
            await update.message.reply_text(f"✅ تم حظر المستخدم {target_id}")
            
        except ValueError:
            await update.message.reply_text("❌ ايدي المستخدم غير صحيح")
            return BANNING_USER
    
    elif current_state == UNBANNING_USER:
        # رفع حظر
        try:
            target_id = int(text)
            
            if data_manager.unban_user(target_id):
                await data_manager.save_all()
                await update.message.reply_text(f"✅ تم رفع الحظر عن المستخدم {target_id}")
            else:
                await update.message.reply_text(f"❌ المستخدم غير موجود في قائمة المحظورين")
            
        except ValueError:
            await update.message.reply_text("❌ ايدي المستخدم غير صحيح")
            return UNBANNING_USER
    
    elif current_state == CHANGING_INVITE_REWARD:
        # تغيير مكافأة الدعوة
        try:
            reward = int(text)
            if reward <= 0:
                await update.message.reply_text("❌ المكافأة يجب ان تكون اكبر من 0")
                return CHANGING_INVITE_REWARD
            
            data_manager.settings["invite_reward"] = reward
            await data_manager.save_all()
            
            await update.message.reply_text(f"✅ تم تغيير مكافأة الدعوة الى {reward} نقطة")
            
        except ValueError:
            await update.message.reply_text("❌ الرجاء ادخال رقم صحيح")
            return CHANGING_INVITE_REWARD
    
    elif current_state == CHANGING_MEMBER_PRICE:
        # تغيير سعر العضو
        try:
            price = int(text)
            if price <= 0:
                await update.message.reply_text("❌ السعر يجب ان يكون اكبر من 0")
                return CHANGING_MEMBER_PRICE
            
            data_manager.settings["member_price"] = price
            await data_manager.save_all()
            
            await update.message.reply_text(f"✅ تم تغيير سعر العضو الى {price} نقطة")
            
        except ValueError:
            await update.message.reply_text("❌ الرجاء ادخال رقم صحيح")
            return CHANGING_MEMBER_PRICE
    
    elif current_state == ADDING_MANDATORY_CHANNEL:
        # اضافة قناة اجبارية
        try:
            parts = [p.strip() for p in text.split('|')]
            if len(parts) != 3:
                await update.message.reply_text("❌ التنسيق خطأ. استخدم: الاسم | الرابط | الايدي")
                return ADDING_MANDATORY_CHANNEL
            
            name, link, chat_id = parts
            
            data_manager.mandatory_channels.append({
                "name": name,
                "link": link,
                "chat_id": chat_id
            })
            await data_manager.save_all()
            
            await update.message.reply_text(f"✅ تم اضافة القناة الاجبارية: {name}")
            
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {str(e)}")
            return ADDING_MANDATORY_CHANNEL
    
    elif current_state == CHANGING_WELCOME_MESSAGE:
        # تغيير رسالة الترحيب
        data_manager.settings["welcome_message"] = text
        await data_manager.save_all()
        
        await update.message.reply_text("✅ تم تغيير رسالة الترحيب بنجاح")
    
    # بعد الانتهاء من العملية، نعرض لوحة التحكم
    await update.message.reply_text(
        "🔧 لوحة تحكم المدير",
        reply_markup=get_admin_keyboard()
    )
    
    context.user_data["state"] = MAIN_MENU
    return MAIN_MENU

# ==================== المعالج الرئيسي للرسائل ====================

async def main_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """المعالج الرئيسي لجميع الرسائل"""
    user_id = update.effective_user.id
    
    # التحقق من الحظر
    if data_manager.is_banned(user_id):
        await update.message.reply_text("⛔️ أنت محظور من استخدام البوت")
        return ConversationHandler.END
    
    current_state = context.user_data.get("state", MAIN_MENU)
    
    # معالجة الملفات
    if update.message.document:
        return await handle_document(update, context)
    
    # معالجة نصوص المديرين
    if user_id in ADMIN_IDS and current_state != MAIN_MENU:
        return await handle_admin_text(update, context, current_state)
    
    # معالجة الرسائل العادية حسب الحالة
    if current_state == WAITING_FOR_MEMBERS_COUNT:
        return await handle_members_count(update, context)
    elif current_state == WAITING_FOR_CHANNEL_LINK:
        return await handle_channel_link(update, context)
    
    # رسالة غير معروفة
    await update.message.reply_text(
        "❌ امر غير معروف. استخدم /start للبدء"
    )
    
    return MAIN_MENU

# ==================== دالة الخطأ ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج الاخطاء"""
    logger.error(f"حدث خطأ: {context.error}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ عذراً، حدث خطأ غير متوقع. الرجاء المحاولة لاحقاً"
            )
    except:
        pass

# ==================== الدالة الرئيسية ====================

def main() -> None:
    """الدالة الرئيسية لتشغيل البوت"""
    
    # انشاء التطبيق
    application = Application.builder().token(BOT_TOKEN).build()
    
    # اضافة معالج المحادثة
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(button_callback),
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_message_handler),
                MessageHandler(filters.Document.ALL, handle_document),
            ],
            ADDING_POINTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_message_handler),
            ],
            DEDUCTING_POINTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_message_handler),
            ],
            ADDING_NUMBERS_FILE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_message_handler),
                MessageHandler(filters.Document.ALL, handle_document),
            ],
            DELETING_NUMBERS_FILE: [
                CallbackQueryHandler(button_callback),
            ],
            ADDING_SUPPORT_USER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_message_handler),
            ],
            ADDING_CHANNEL_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_message_handler),
            ],
            BANNING_USER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_message_handler),
            ],
            UNBANNING_USER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_message_handler),
            ],
            CHANGING_INVITE_REWARD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_message_handler),
            ],
            CHANGING_MEMBER_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_message_handler),
            ],
            ADDING_MANDATORY_CHANNEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_message_handler),
            ],
            DELETING_MANDATORY_CHANNEL: [
                CallbackQueryHandler(button_callback),
            ],
            CHANGING_WELCOME_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_message_handler),
            ],
            WAITING_FOR_MEMBERS_COUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_message_handler),
            ],
            WAITING_FOR_CHANNEL_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_message_handler),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
        per_message=False,
    )
    
    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)
    
    # تشغيل البوت
    print("✅ البوت يعمل بنجاح...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

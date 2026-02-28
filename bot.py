#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
بوت تمويل متكامل لتليجرام - النسخة النهائية المصححة
الإصدار: 4.0
المطور: System
"""

import os
import sys
import json
import asyncio
import logging
import random
import string
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import traceback

import aiofiles
from colorama import init, Fore

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
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
from telegram.error import BadRequest

init(autoreset=True)

# ==================== التهيئة الأساسية ====================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8699966374:AAGCCGehxTQzGbEkBxIe7L3vecLPcvzGrHg"
ADMIN_IDS = [6615860762, 6130994941]

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# ==================== حالات المحادثة ====================

MAIN_MENU, WAITING_COUNT, WAITING_LINK = range(3)
ADMIN_ADD_POINTS, ADMIN_DEDUCT_POINTS, ADMIN_ADD_NUMBERS, ADMIN_ADD_SUPPORT = range(100, 104)
ADMIN_ADD_CHANNEL, ADMIN_BAN_USER, ADMIN_UNBAN_USER, ADMIN_CHANGE_REWARD = range(104, 108)
ADMIN_CHANGE_PRICE, ADMIN_ADD_MANDATORY, ADMIN_CHANGE_WELCOME, ADMIN_BROADCAST = range(108, 112)

# ==================== قاعدة البيانات ====================

class Database:
    def __init__(self):
        self.users_file = DATA_DIR / "users.json"
        self.numbers_file = DATA_DIR / "numbers.json"
        self.settings_file = DATA_DIR / "settings.json"
        self.financing_file = DATA_DIR / "financing.json"
        self.banned_file = DATA_DIR / "banned.json"
        self.mandatory_file = DATA_DIR / "mandatory.json"
        self.referrals_file = DATA_DIR / "referrals.json"
        
        self.users = self._load_json(self.users_file, {})
        self.numbers = self._load_json(self.numbers_file, {"numbers": [], "files": [], "used": []})
        self.settings = self._load_json(self.settings_file, self._default_settings())
        self.financing = self._load_json(self.financing_file, {})
        self.banned = self._load_json(self.banned_file, [])
        self.mandatory = self._load_json(self.mandatory_file, [])
        self.referrals = self._load_json(self.referrals_file, {})
        
        logger.info(f"{Fore.GREEN}تم تحميل قاعدة البيانات بنجاح{Fore.RESET}")
    
    def _default_settings(self):
        return {
            "invite_reward": 10,
            "member_price": 8,
            "welcome_message": "مرحباً بك في بوت التمويل",
            "support_username": "support",
            "channel_link": "https://t.me/your_channel",
            "min_financing": 10,
            "max_financing": 1000,
            "daily_bonus": 5
        }
    
    def _load_json(self, file_path, default):
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"خطأ في تحميل {file_path}: {e}")
        return default
    
    async def _save_json(self, file_path, data):
        try:
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=2))
            return True
        except Exception as e:
            logger.error(f"خطأ في حفظ {file_path}: {e}")
            return False
    
    async def save_all(self):
        tasks = [
            self._save_json(self.users_file, self.users),
            self._save_json(self.numbers_file, self.numbers),
            self._save_json(self.settings_file, self.settings),
            self._save_json(self.financing_file, self.financing),
            self._save_json(self.banned_file, self.banned),
            self._save_json(self.mandatory_file, self.mandatory),
            self._save_json(self.referrals_file, self.referrals)
        ]
        await asyncio.gather(*tasks)
    
    def get_user(self, user_id):
        user_id = str(user_id)
        if user_id not in self.users:
            self.users[user_id] = {
                "points": 0,
                "referrals": 0,
                "referral_code": self._generate_code(),
                "financing_count": 0,
                "total_spent": 0,
                "total_earned": 0,
                "joined_date": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "last_daily": None,
                "username": None,
                "first_name": None
            }
        self.users[user_id]["last_active"] = datetime.now().isoformat()
        return self.users[user_id]
    
    def _generate_code(self, length=8):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    def add_points(self, user_id, points):
        user_id = str(user_id)
        user = self.get_user(int(user_id))
        user["points"] += points
        user["total_earned"] += points
        return True
    
    def deduct_points(self, user_id, points):
        user_id = str(user_id)
        user = self.get_user(int(user_id))
        if user["points"] >= points:
            user["points"] -= points
            user["total_spent"] += points
            return True
        return False
    
    def process_referral(self, referrer_id, new_user_id):
        referrer_id = str(referrer_id)
        new_user_id = str(new_user_id)
        
        if referrer_id == new_user_id:
            return False
        
        if referrer_id not in self.referrals:
            self.referrals[referrer_id] = []
        
        if new_user_id in self.referrals[referrer_id]:
            return False
        
        self.referrals[referrer_id].append(new_user_id)
        reward = self.settings["invite_reward"]
        self.add_points(int(referrer_id), reward)
        
        referrer = self.get_user(int(referrer_id))
        referrer["referrals"] += 1
        return True
    
    def get_referral_link(self, user_id, bot_username):
        user = self.get_user(user_id)
        return f"https://t.me/{bot_username}?start={user['referral_code']}"
    
    def get_top_referrers(self, limit=3):
        referrers = []
        for user_id, ref_list in self.referrals.items():
            referrers.append({
                "user_id": user_id,
                "count": len(ref_list)
            })
        referrers.sort(key=lambda x: x["count"], reverse=True)
        return referrers[:limit]
    
    def add_numbers_file(self, filename, numbers):
        valid_numbers = []
        invalid_count = 0
        
        for num in numbers:
            num = num.strip()
            if not num:
                continue
            
            cleaned = re.sub(r'[^0-9+]', '', num)
            if re.match(r'^(00963|\+963|963)\d{8,9}$', cleaned):
                if cleaned.startswith('00963'):
                    cleaned = '+' + cleaned[1:]
                elif cleaned.startswith('963') and not cleaned.startswith('+'):
                    cleaned = '+' + cleaned
                valid_numbers.append(cleaned)
            else:
                invalid_count += 1
        
        file_info = {
            "name": filename,
            "count": len(valid_numbers),
            "invalid": invalid_count,
            "added_date": datetime.now().isoformat()
        }
        
        self.numbers["files"].append(file_info)
        self.numbers["numbers"].extend(valid_numbers)
        return file_info
    
    def get_available_numbers(self, count):
        available = []
        for _ in range(min(count, len(self.numbers["numbers"]))):
            if self.numbers["numbers"]:
                num = self.numbers["numbers"].pop(0)
                available.append(num)
                self.numbers["used"].append({
                    "number": num,
                    "used_at": datetime.now().isoformat()
                })
        return available
    
    def get_numbers_stats(self):
        return {
            "available": len(self.numbers["numbers"]),
            "used": len(self.numbers["used"]),
            "files": len(self.numbers["files"])
        }
    
    def create_financing(self, user_id, channel_link, members_count, cost):
        finance_id = self._generate_code(12)
        user_id = str(user_id)
        
        self.financing[finance_id] = {
            "id": finance_id,
            "user_id": user_id,
            "channel_link": channel_link,
            "total_members": members_count,
            "added_members": 0,
            "status": "pending",
            "cost": cost,
            "created_at": datetime.now().isoformat()
        }
        
        user = self.get_user(int(user_id))
        user["financing_count"] += 1
        return finance_id
    
    def update_financing(self, finance_id, added=1):
        finance = self.financing.get(finance_id)
        if not finance:
            return None
        
        finance["added_members"] += added
        if finance["added_members"] >= finance["total_members"]:
            finance["status"] = "completed"
        return finance
    
    def get_user_financing(self, user_id):
        user_id = str(user_id)
        return [
            {**finance, "id": fid}
            for fid, finance in self.financing.items()
            if finance["user_id"] == user_id
        ]
    
    def is_banned(self, user_id):
        return str(user_id) in self.banned
    
    def ban_user(self, user_id, reason=""):
        user_id = str(user_id)
        if int(user_id) in ADMIN_IDS:
            return False
        
        if user_id not in self.banned:
            self.banned.append({
                "user_id": user_id,
                "reason": reason,
                "banned_at": datetime.now().isoformat()
            })
            return True
        return False
    
    def unban_user(self, user_id):
        user_id = str(user_id)
        for i, banned in enumerate(self.banned):
            if banned["user_id"] == user_id:
                self.banned.pop(i)
                return True
        return False
    
    def add_mandatory_channel(self, name, link, chat_id):
        channel = {
            "name": name,
            "link": link,
            "chat_id": chat_id,
            "added_at": datetime.now().isoformat()
        }
        self.mandatory.append(channel)
        return channel
    
    def remove_mandatory_channel(self, chat_id):
        for i, channel in enumerate(self.mandatory):
            if str(channel["chat_id"]) == str(chat_id):
                self.mandatory.pop(i)
                return True
        return False
    
    def get_bot_stats(self):
        today = datetime.now().strftime("%Y-%m-%d")
        
        active_today = 0
        for user_data in self.users.values():
            last_active = user_data.get("last_active", "")
            if last_active and last_active.startswith(today):
                active_today += 1
        
        total_points = sum(u.get("points", 0) for u in self.users.values())
        
        return {
            "total_users": len(self.users),
            "active_today": active_today,
            "total_points": total_points,
            "total_financing": len(self.financing),
            "completed_financing": sum(1 for f in self.financing.values() if f["status"] == "completed"),
            "banned_count": len(self.banned),
            "numbers": self.get_numbers_stats(),
            "mandatory_channels": len(self.mandatory)
        }

db = Database()

# ==================== الأدوات المساعدة ====================

class Helpers:
    @staticmethod
    def format_number(num):
        if num >= 1000000:
            return f"{num/1000000:.1f}M"
        if num >= 1000:
            return f"{num/1000:.1f}K"
        return str(num)
    
    @staticmethod
    def is_valid_link(link):
        link = link.strip()
        patterns = [
            r'^https?://t\.me/[a-zA-Z0-9_]+$',
            r'^https?://telegram\.me/[a-zA-Z0-9_]+$',
            r'^@[a-zA-Z0-9_]+$',
            r'^[a-zA-Z0-9_]+$'
        ]
        for pattern in patterns:
            if re.match(pattern, link):
                return True
        return False
    
    @staticmethod
    async def safe_edit_message(query, text, reply_markup=None):
        try:
            await query.edit_message_text(text=text, reply_markup=reply_markup)
            return True
        except BadRequest as e:
            if "Message is not modified" in str(e):
                await query.answer()
                return False
            logger.warning(f"خطأ في تعديل الرسالة: {e}")
            return False
        except Exception as e:
            logger.warning(f"خطأ في تعديل الرسالة: {e}")
            return False
    
    @staticmethod
    async def safe_send_message(bot, chat_id, text):
        try:
            await bot.send_message(chat_id=chat_id, text=text)
            return True
        except:
            return False

helpers = Helpers()

# ==================== لوحات المفاتيح ====================

class Keyboards:
    @staticmethod
    def main_menu(user_id):
        user = db.get_user(user_id)
        keyboard = [
            [InlineKeyboardButton("💰 تجميع النقاط", callback_data="collect_points"),
             InlineKeyboardButton("🚀 تمويل مشتركين", callback_data="finance_members")],
            [InlineKeyboardButton("📊 تمويلاتي", callback_data="my_financing"),
             InlineKeyboardButton("📈 احصائياتي", callback_data="my_stats")],
            [InlineKeyboardButton("🎁 المكافأة اليومية", callback_data="daily_bonus"),
             InlineKeyboardButton("👥 دعوة صديق", callback_data="invite_friend")],
            [InlineKeyboardButton("🆘 الدعم الفني", url=f"https://t.me/{db.settings['support_username']}"),
             InlineKeyboardButton("📢 قناة البوت", url=db.settings["channel_link"])],
            [InlineKeyboardButton("🔄 تحديث", callback_data="refresh")]
        ]
        if user_id in ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("⚙️ لوحة التحكم", callback_data="admin_panel")])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def admin_panel():
        keyboard = [
            [InlineKeyboardButton("📊 احصائيات البوت", callback_data="admin_stats")],
            [InlineKeyboardButton("💰 شحن رصيد", callback_data="admin_add_points"),
             InlineKeyboardButton("💸 خصم رصيد", callback_data="admin_deduct_points")],
            [InlineKeyboardButton("📁 اضافة ملف ارقام", callback_data="admin_add_numbers"),
             InlineKeyboardButton("📞 احصائيات الارقام", callback_data="admin_numbers_stats")],
            [InlineKeyboardButton("👤 تغيير حساب الدعم", callback_data="admin_add_support"),
             InlineKeyboardButton("🔗 تغيير رابط القناة", callback_data="admin_add_channel")],
            [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban"),
             InlineKeyboardButton("✅ رفع حظر", callback_data="admin_unban")],
            [InlineKeyboardButton("🎁 تغيير مكافأة الدعوة", callback_data="admin_change_reward"),
             InlineKeyboardButton("💵 تغيير سعر العضو", callback_data="admin_change_price")],
            [InlineKeyboardButton("📢 اضافة قناة اجبارية", callback_data="admin_add_mandatory"),
             InlineKeyboardButton("📋 عرض القنوات", callback_data="admin_view_mandatory")],
            [InlineKeyboardButton("✏️ تغيير رسالة الترحيب", callback_data="admin_change_welcome"),
             InlineKeyboardButton("📨 رسالة جماعية", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def back_button(callback_data="back_to_main"):
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data=callback_data)]])
    
    @staticmethod
    def cancel_button():
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]])

# ==================== معالج البداية ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    logger.info(f"مستخدم جديد: {user_id} - {user.first_name}")
    
    if db.is_banned(user_id):
        await update.message.reply_text("⛔️ أنت محظور من استخدام البوت")
        return MAIN_MENU
    
    args = context.args
    if args and len(args) > 0:
        referral_code = args[0]
        for uid, u_data in db.users.items():
            if u_data.get("referral_code") == referral_code and str(uid) != str(user_id):
                if db.process_referral(int(uid), user_id):
                    await helpers.safe_send_message(
                        context.bot,
                        int(uid),
                        f"🎉 مستخدم جديد انضم عبر رابطك\n💰 تم اضافة {db.settings['invite_reward']} نقطة"
                    )
                break
    
    user_data = db.get_user(user_id)
    db.get_user(user_id)["username"] = user.username
    db.get_user(user_id)["first_name"] = user.first_name
    await db.save_all()
    
    text = (
        f"{db.settings['welcome_message']}\n\n"
        f"👤 مرحباً {user.first_name}\n"
        f"🆔 ايديك: {user_id}\n"
        f"⭐️ نقاطك: {user_data['points']}\n"
        f"👥 دعواتك: {user_data['referrals']}"
    )
    
    await update.message.reply_text(text, reply_markup=Keyboards.main_menu(user_id))
    return MAIN_MENU

# ==================== معالج أزرار المستخدم ====================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    logger.info(f"زر: {data} من {user_id}")
    
    if db.is_banned(user_id) and data != "check_subscription":
        await query.edit_message_text("⛔️ أنت محظور من استخدام البوت")
        return MAIN_MENU
    
    # ========== تجميع النقاط ==========
    if data == "collect_points":
        user_data = db.get_user(user_id)
        bot_info = await context.bot.get_me()
        link = db.get_referral_link(user_id, bot_info.username)
        top = db.get_top_referrers(3)
        
        text = (
            "💰 تجميع النقاط\n\n"
            "شارك الرابط التالي مع اصدقائك\n"
            "عند دخول كل صديق تحصل على نقاط\n\n"
            f"رصيدك: {user_data['points']} نقطة\n"
            f"دعواتك: {user_data['referrals']}\n"
            f"مكافأة كل دعوة: {db.settings['invite_reward']} نقطة\n\n"
            f"رابط الدعوة:\n{link}\n"
        )
        
        if top:
            text += "\nأفضل الداعين:\n"
            for i, ref in enumerate(top, 1):
                text += f"{i}. ايدي {ref['user_id']} - {ref['count']} دعوة\n"
        
        keyboard = [
            [InlineKeyboardButton("📋 نسخ الرابط", callback_data="copy_link")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
        ]
        await helpers.safe_edit_message(query, text, InlineKeyboardMarkup(keyboard))
    
    # ========== نسخ الرابط ==========
    elif data == "copy_link":
        bot_info = await context.bot.get_me()
        link = db.get_referral_link(user_id, bot_info.username)
        await query.answer(f"✅ تم نسخ الرابط: {link}", show_alert=True)
    
    # ========== تمويل مشتركين ==========
    elif data == "finance_members":
        user_data = db.get_user(user_id)
        text = (
            "🚀 تمويل مشتركين\n\n"
            f"رصيدك: {user_data['points']} نقطة\n"
            f"سعر العضو: {db.settings['member_price']} نقطة\n"
            f"الحد الأدنى: {db.settings['min_financing']}\n"
            f"الحد الأقصى: {db.settings['max_financing']}\n"
            f"الارقام المتاحة: {len(db.numbers['numbers'])}\n\n"
            "ارسل عدد الاعضاء الآن:"
        )
        await helpers.safe_edit_message(query, text, Keyboards.cancel_button())
        return WAITING_COUNT
    
    # ========== تمويلاتي ==========
    elif data == "my_financing":
        finances = db.get_user_financing(user_id)
        if not finances:
            text = "📊 لا يوجد لديك تمويلات"
        else:
            text = "📊 تمويلاتك:\n\n"
            for f in finances[-5:]:
                status = "✅" if f["status"] == "completed" else "⏳"
                text += f"{status} تقدم: {f['added_members']}/{f['total_members']}\n"
                text += f"تكلفة: {f['cost']} نقطة\n"
                text += f"تاريخ: {f['created_at'][:10]}\n\n"
        await helpers.safe_edit_message(query, text, Keyboards.back_button())
    
    # ========== احصائياتي ==========
    elif data == "my_stats":
        user_data = db.get_user(user_id)
        completed = sum(1 for f in db.financing.values() 
                       if f["user_id"] == str(user_id) and f["status"] == "completed")
        rate = (completed / user_data['financing_count'] * 100) if user_data['financing_count'] > 0 else 0
        
        text = (
            "📈 احصائياتك:\n\n"
            f"ايديك: {user_id}\n"
            f"اسمك: {query.from_user.first_name}\n"
            f"نقاطك: {user_data['points']}\n"
            f"دعواتك: {user_data['referrals']}\n"
            f"تمويلاتك: {user_data['financing_count']}\n"
            f"المنفق: {user_data['total_spent']} نقطة\n"
            f"المكتسب: {user_data['total_earned']} نقطة\n"
            f"نسبة النجاح: {rate:.1f}%\n"
            f"تاريخ الانضمام: {user_data['joined_date'][:10]}"
        )
        await helpers.safe_edit_message(query, text, Keyboards.back_button())
    
    # ========== المكافأة اليومية ==========
    elif data == "daily_bonus":
        user_data = db.get_user(user_id)
        now = datetime.now()
        last = user_data.get("last_daily")
        
        if last:
            last_date = datetime.fromisoformat(last)
            if (now - last_date) < timedelta(hours=24):
                remaining = timedelta(hours=24) - (now - last_date)
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60
                await query.answer(f"⏳ انتظر {hours} ساعة {minutes} دقيقة", show_alert=True)
                return MAIN_MENU
        
        bonus = db.settings["daily_bonus"]
        db.add_points(user_id, bonus)
        db.get_user(user_id)["last_daily"] = now.isoformat()
        await db.save_all()
        
        await query.answer(f"✅ تم اضافة {bonus} نقطة", show_alert=True)
        user_data = db.get_user(user_id)
        text = (
            f"{db.settings['welcome_message']}\n\n"
            f"👤 مرحباً {query.from_user.first_name}\n"
            f"🆔 ايديك: {user_id}\n"
            f"⭐️ نقاطك: {user_data['points']}\n"
            f"👥 دعواتك: {user_data['referrals']}"
        )
        await helpers.safe_edit_message(query, text, Keyboards.main_menu(user_id))
    
    # ========== دعوة صديق ==========
    elif data == "invite_friend":
        bot_info = await context.bot.get_me()
        link = db.get_referral_link(user_id, bot_info.username)
        user_data = db.get_user(user_id)
        top = db.get_top_referrers(3)
        
        text = (
            "👥 دعوة صديق\n\n"
            f"مكافأة كل دعوة: {db.settings['invite_reward']} نقطة\n"
            f"دعواتك: {user_data['referrals']}\n"
            f"رابط الدعوة:\n{link}\n"
        )
        
        if top:
            text += "\nأفضل الداعين:\n"
            for i, ref in enumerate(top, 1):
                text += f"{i}. ايدي {ref['user_id']} - {ref['count']} دعوة\n"
        
        keyboard = [
            [InlineKeyboardButton("📱 مشاركة", switch_inline_query=f"انضم الي هنا\n{link}")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
        ]
        await helpers.safe_edit_message(query, text, InlineKeyboardMarkup(keyboard))
    
    # ========== تحديث ==========
    elif data == "refresh":
        user_data = db.get_user(user_id)
        text = (
            f"{db.settings['welcome_message']}\n\n"
            f"👤 مرحباً {query.from_user.first_name}\n"
            f"🆔 ايديك: {user_id}\n"
            f"⭐️ نقاطك: {user_data['points']}\n"
            f"👥 دعواتك: {user_data['referrals']}"
        )
        await helpers.safe_edit_message(query, text, Keyboards.main_menu(user_id))
    
    # ========== رجوع ==========
    elif data == "back_to_main":
        user_data = db.get_user(user_id)
        text = (
            f"{db.settings['welcome_message']}\n\n"
            f"👤 مرحباً {query.from_user.first_name}\n"
            f"🆔 ايديك: {user_id}\n"
            f"⭐️ نقاطك: {user_data['points']}\n"
            f"👥 دعواتك: {user_data['referrals']}"
        )
        await helpers.safe_edit_message(query, text, Keyboards.main_menu(user_id))
        context.user_data.clear()
    
    # ========== إلغاء ==========
    elif data == "cancel":
        user_data = db.get_user(user_id)
        text = (
            f"{db.settings['welcome_message']}\n\n"
            f"👤 مرحباً {query.from_user.first_name}\n"
            f"🆔 ايديك: {user_id}\n"
            f"⭐️ نقاطك: {user_data['points']}\n"
            f"👥 دعواتك: {user_data['referrals']}"
        )
        await helpers.safe_edit_message(query, text, Keyboards.main_menu(user_id))
        context.user_data.clear()
    
    # ========== لوحة التحكم ==========
    elif data == "admin_panel" and user_id in ADMIN_IDS:
        await helpers.safe_edit_message(query, "⚙️ لوحة التحكم", Keyboards.admin_panel())
    
    # ========== أزرار المدير ==========
    elif data.startswith("admin_") and user_id in ADMIN_IDS:
        return await admin_button_handler(query, context, user_id, data)
    
    await db.save_all()
    return MAIN_MENU

# ==================== معالج أزرار المدير ====================

async def admin_button_handler(query, context, user_id, data):
    
    # ========== احصائيات البوت ==========
    if data == "admin_stats":
        stats = db.get_bot_stats()
        text = (
            "📊 احصائيات البوت\n\n"
            f"اجمالي المستخدمين: {stats['total_users']}\n"
            f"نشط اليوم: {stats['active_today']}\n"
            f"محظورين: {stats['banned_count']}\n"
            f"اجمالي النقاط: {stats['total_points']}\n"
            f"اجمالي التمويلات: {stats['total_financing']}\n"
            f"التمويلات المكتملة: {stats['completed_financing']}\n"
            f"الارقام المتاحة: {stats['numbers']['available']}\n"
            f"الارقام المستخدمة: {stats['numbers']['used']}\n"
            f"عدد الملفات: {stats['numbers']['files']}\n"
            f"القنوات الاجبارية: {stats['mandatory_channels']}"
        )
        await helpers.safe_edit_message(query, text, Keyboards.admin_panel())
    
    # ========== اضافة ملف ارقام ==========
    elif data == "admin_add_numbers":
        await helpers.safe_edit_message(
            query,
            "📁 اضافة ملف ارقام\n\n"
            "ارسل ملف txt يحتوي على ارقام تليجرام\n"
            "كل رقم في سطر منفصل\n"
            "الارقام يجب ان تبدأ بـ 00963 او +963",
            Keyboards.cancel_button()
        )
        context.user_data["admin_action"] = "add_numbers"
        return ADMIN_ADD_NUMBERS
    
    # ========== احصائيات الارقام ==========
    elif data == "admin_numbers_stats":
        stats = db.get_numbers_stats()
        text = (
            "📞 احصائيات الارقام\n\n"
            f"متاح للاستخدام: {stats['available']}\n"
            f"مستخدم: {stats['used']}\n"
            f"عدد الملفات: {stats['files']}"
        )
        await helpers.safe_edit_message(query, text, Keyboards.back_button("back_to_admin"))
    
    # ========== شحن رصيد ==========
    elif data == "admin_add_points":
        await helpers.safe_edit_message(
            query,
            "💰 شحن رصيد مستخدم\n\n"
            "ارسل: ايدي المستخدم المبلغ\n"
            "مثال: 123456789 100",
            Keyboards.cancel_button()
        )
        context.user_data["admin_action"] = "add_points"
        return ADMIN_ADD_POINTS
    
    # ========== خصم رصيد ==========
    elif data == "admin_deduct_points":
        await helpers.safe_edit_message(
            query,
            "💸 خصم رصيد مستخدم\n\n"
            "ارسل: ايدي المستخدم المبلغ\n"
            "مثال: 123456789 50",
            Keyboards.cancel_button()
        )
        context.user_data["admin_action"] = "deduct_points"
        return ADMIN_DEDUCT_POINTS
    
    # ========== تغيير حساب الدعم ==========
    elif data == "admin_add_support":
        current = db.settings['support_username']
        await helpers.safe_edit_message(
            query,
            f"👤 تغيير حساب الدعم\n\n"
            f"الحالي: @{current}\n\n"
            "ارسل اليوزر الجديد:",
            Keyboards.cancel_button()
        )
        context.user_data["admin_action"] = "add_support"
        return ADMIN_ADD_SUPPORT
    
    # ========== تغيير رابط القناة ==========
    elif data == "admin_add_channel":
        current = db.settings['channel_link']
        await helpers.safe_edit_message(
            query,
            f"🔗 تغيير رابط القناة\n\n"
            f"الحالي: {current}\n\n"
            "ارسل الرابط الجديد:",
            Keyboards.cancel_button()
        )
        context.user_data["admin_action"] = "add_channel"
        return ADMIN_ADD_CHANNEL
    
    # ========== حظر مستخدم ==========
    elif data == "admin_ban":
        await helpers.safe_edit_message(
            query,
            "🚫 حظر مستخدم\n\n"
            "ارسل ايدي المستخدم\n"
            "مثال: 123456789",
            Keyboards.cancel_button()
        )
        context.user_data["admin_action"] = "ban"
        return ADMIN_BAN_USER
    
    # ========== رفع حظر ==========
    elif data == "admin_unban":
        await helpers.safe_edit_message(
            query,
            "✅ رفع حظر\n\n"
            "ارسل ايدي المستخدم\n"
            "مثال: 123456789",
            Keyboards.cancel_button()
        )
        context.user_data["admin_action"] = "unban"
        return ADMIN_UNBAN_USER
    
    # ========== تغيير مكافأة الدعوة ==========
    elif data == "admin_change_reward":
        current = db.settings['invite_reward']
        await helpers.safe_edit_message(
            query,
            f"🎁 تغيير مكافأة الدعوة\n\n"
            f"الحالية: {current} نقطة\n\n"
            "ارسل القيمة الجديدة:",
            Keyboards.cancel_button()
        )
        context.user_data["admin_action"] = "change_reward"
        return ADMIN_CHANGE_REWARD
    
    # ========== تغيير سعر العضو ==========
    elif data == "admin_change_price":
        current = db.settings['member_price']
        await helpers.safe_edit_message(
            query,
            f"💵 تغيير سعر العضو\n\n"
            f"الحالي: {current} نقطة\n\n"
            "ارسل السعر الجديد:",
            Keyboards.cancel_button()
        )
        context.user_data["admin_action"] = "change_price"
        return ADMIN_CHANGE_PRICE
    
    # ========== اضافة قناة اجبارية ==========
    elif data == "admin_add_mandatory":
        await helpers.safe_edit_message(
            query,
            "📢 اضافة قناة اجبارية\n\n"
            "ارسل: الاسم | الرابط | ايدي القناة\n\n"
            "مثال:\n"
            "قناتي | https://t.me/my_channel | -100123456789",
            Keyboards.cancel_button()
        )
        context.user_data["admin_action"] = "add_mandatory"
        return ADMIN_ADD_MANDATORY
    
    # ========== عرض القنوات الاجبارية ==========
    elif data == "admin_view_mandatory":
        if not db.mandatory:
            text = "📢 لا يوجد قنوات اجبارية"
        else:
            text = "📢 القنوات الاجبارية:\n\n"
            for i, ch in enumerate(db.mandatory, 1):
                text += f"{i}. {ch['name']}\n   {ch['link']}\n\n"
        await helpers.safe_edit_message(query, text, Keyboards.back_button("back_to_admin"))
    
    # ========== تغيير رسالة الترحيب ==========
    elif data == "admin_change_welcome":
        current = db.settings['welcome_message']
        await helpers.safe_edit_message(
            query,
            f"✏️ تغيير رسالة الترحيب\n\n"
            f"الحالية:\n{current}\n\n"
            "ارسل الرسالة الجديدة:",
            Keyboards.cancel_button()
        )
        context.user_data["admin_action"] = "change_welcome"
        return ADMIN_CHANGE_WELCOME
    
    # ========== رسالة جماعية ==========
    elif data == "admin_broadcast":
        await helpers.safe_edit_message(
            query,
            "📨 رسالة جماعية\n\n"
            "ارسل الرسالة التي تريد ارسالها للجميع:",
            Keyboards.cancel_button()
        )
        context.user_data["admin_action"] = "broadcast"
        return ADMIN_BROADCAST
    
    # ========== رجوع ==========
    elif data == "back_to_admin":
        await helpers.safe_edit_message(query, "⚙️ لوحة التحكم", Keyboards.admin_panel())
    
    return MAIN_MENU

# ==================== معالج عدد الاعضاء ====================

async def handle_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if text.lower() in ["الغاء", "cancel"]:
        await update.message.reply_text("✅ تم الغاء", reply_markup=Keyboards.main_menu(user_id))
        context.user_data.clear()
        return MAIN_MENU
    
    try:
        count = int(text)
        if count < db.settings["min_financing"]:
            await update.message.reply_text(f"❌ الحد الأدنى {db.settings['min_financing']}")
            return WAITING_COUNT
        if count > db.settings["max_financing"]:
            await update.message.reply_text(f"❌ الحد الأقصى {db.settings['max_financing']}")
            return WAITING_COUNT
        
        if len(db.numbers["numbers"]) < count:
            await update.message.reply_text(f"❌ المتوفر {len(db.numbers['numbers'])} رقم فقط")
            context.user_data.clear()
            return MAIN_MENU
        
        user_data = db.get_user(user_id)
        cost = count * db.settings["member_price"]
        
        if user_data["points"] < cost:
            await update.message.reply_text(f"❌ رصيدك غير كافي\nالمطلوب {cost} - رصيدك {user_data['points']}")
            context.user_data.clear()
            return MAIN_MENU
        
        context.user_data["finance"] = {"count": count, "cost": cost}
        await update.message.reply_text(
            f"✅ التكلفة {cost} نقطة\nرصيدك المتبقي {user_data['points'] - cost}\n\nارسل رابط قناتك الآن:",
            reply_markup=Keyboards.cancel_button()
        )
        return WAITING_LINK
        
    except ValueError:
        await update.message.reply_text("❌ ارسل رقماً صحيحاً")
        return WAITING_COUNT

# ==================== معالج رابط القناة ====================

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    link = update.message.text.strip()
    
    if link.lower() in ["الغاء", "cancel"]:
        await update.message.reply_text("✅ تم الغاء", reply_markup=Keyboards.main_menu(user_id))
        context.user_data.clear()
        return MAIN_MENU
    
    if not helpers.is_valid_link(link):
        await update.message.reply_text("❌ رابط غير صالح")
        return WAITING_LINK
    
    if link.startswith('@'):
        clean_link = link
    elif 't.me/' not in link:
        clean_link = f"https://t.me/{link}"
    else:
        clean_link = link
    
    finance_data = context.user_data.get("finance")
    if not finance_data:
        await update.message.reply_text("❌ خطأ، حاول مرة اخرى")
        return MAIN_MENU
    
    if not db.deduct_points(user_id, finance_data["cost"]):
        await update.message.reply_text("❌ فشل خصم النقاط")
        return MAIN_MENU
    
    finance_id = db.create_financing(
        user_id, clean_link, finance_data["count"], finance_data["cost"]
    )
    await db.save_all()
    
    await update.message.reply_text(
        f"✅ تم بدء التمويل\n"
        f"المعرف: {finance_id}\n"
        f"العدد: {finance_data['count']}\n"
        f"التكلفة: {finance_data['cost']}\n\n"
        f"سيتم اعلامك عند الاكتمال"
    )
    
    asyncio.create_task(process_financing(context.bot, finance_id))
    
    user_data = db.get_user(user_id)
    text = (
        f"{db.settings['welcome_message']}\n\n"
        f"👤 مرحباً {update.effective_user.first_name}\n"
        f"🆔 ايديك: {user_id}\n"
        f"⭐️ نقاطك: {user_data['points']}\n"
        f"👥 دعواتك: {user_data['referrals']}"
    )
    await update.message.reply_text(text, reply_markup=Keyboards.main_menu(user_id))
    
    context.user_data.clear()
    return MAIN_MENU

# ==================== معالج التمويل ====================

async def process_financing(bot, finance_id):
    await asyncio.sleep(2)
    finance = db.financing.get(finance_id)
    if not finance:
        return
    
    logger.info(f"بدء تمويل: {finance_id}")
    user_id = int(finance["user_id"])
    
    for i in range(finance["total_members"]):
        numbers = db.get_available_numbers(1)
        if not numbers:
            await helpers.safe_send_message(
                bot, user_id, "⚠️ نفذت الارقام، سيتم اكمال التمويل لاحقاً"
            )
            break
        
        await asyncio.sleep(random.uniform(1, 2))
        finance = db.update_financing(finance_id)
        
        if (i + 1) % 5 == 0 or finance["added_members"] >= finance["total_members"]:
            await helpers.safe_send_message(
                bot, user_id,
                f"✅ تم اضافة {finance['added_members']}/{finance['total_members']}"
            )
        
        await db.save_all()
        
        if finance["added_members"] >= finance["total_members"]:
            await helpers.safe_send_message(
                bot, user_id, "✅ اكتمل التمويل بنجاح"
            )
            break
    
    logger.info(f"انتهاء تمويل: {finance_id}")

# ==================== معالج نصوص المدير ====================

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if text.lower() in ["الغاء", "cancel"]:
        await update.message.reply_text("✅ تم الغاء", reply_markup=Keyboards.admin_panel())
        context.user_data.clear()
        return MAIN_MENU
    
    action = context.user_data.get("admin_action")
    
    # ========== شحن رصيد ==========
    if action == "add_points":
        try:
            parts = text.split()
            if len(parts) != 2:
                await update.message.reply_text("❌ استخدم: ايدي المستخدم المبلغ")
                return ADMIN_ADD_POINTS
            
            target_id = int(parts[0])
            points = int(parts[1])
            
            if points <= 0:
                await update.message.reply_text("❌ المبلغ يجب ان يكون اكبر من 0")
                return ADMIN_ADD_POINTS
            
            db.add_points(target_id, points)
            await db.save_all()
            await update.message.reply_text(f"✅ تم اضافة {points} نقطة للمستخدم {target_id}")
            await helpers.safe_send_message(context.bot, target_id, f"💰 تم شحن رصيدك ب {points} نقطة")
            
        except ValueError:
            await update.message.reply_text("❌ ارقام غير صحيحة")
            return ADMIN_ADD_POINTS
    
    # ========== خصم رصيد ==========
    elif action == "deduct_points":
        try:
            parts = text.split()
            if len(parts) != 2:
                await update.message.reply_text("❌ استخدم: ايدي المستخدم المبلغ")
                return ADMIN_DEDUCT_POINTS
            
            target_id = int(parts[0])
            points = int(parts[1])
            
            if points <= 0:
                await update.message.reply_text("❌ المبلغ يجب ان يكون اكبر من 0")
                return ADMIN_DEDUCT_POINTS
            
            if db.deduct_points(target_id, points):
                await db.save_all()
                await update.message.reply_text(f"✅ تم خصم {points} نقطة من المستخدم {target_id}")
                await helpers.safe_send_message(context.bot, target_id, f"💸 تم خصم {points} نقطة من رصيدك")
            else:
                await update.message.reply_text("❌ رصيد المستخدم غير كافي")
            
        except ValueError:
            await update.message.reply_text("❌ ارقام غير صحيحة")
            return ADMIN_DEDUCT_POINTS
    
    # ========== اضافة حساب دعم ==========
    elif action == "add_support":
        username = text.replace('@', '').strip()
        db.settings["support_username"] = username
        await db.save_all()
        await update.message.reply_text(f"✅ تم تعيين حساب الدعم: @{username}")
    
    # ========== اضافة رابط قناة ==========
    elif action == "add_channel":
        if helpers.is_valid_link(text):
            db.settings["channel_link"] = text
            await db.save_all()
            await update.message.reply_text(f"✅ تم تعيين الرابط: {text}")
        else:
            await update.message.reply_text("❌ رابط غير صالح")
            return ADMIN_ADD_CHANNEL
    
    # ========== حظر مستخدم ==========
    elif action == "ban":
        try:
            target_id = int(text.split()[0])
            reason = text.split(maxsplit=1)[1] if len(text.split()) > 1 else ""
            
            if target_id in ADMIN_IDS:
                await update.message.reply_text("❌ لا يمكن حظر مدير")
                return ADMIN_BAN_USER
            
            if db.ban_user(target_id, reason):
                await db.save_all()
                await update.message.reply_text(f"✅ تم حظر المستخدم {target_id}")
                await helpers.safe_send_message(context.bot, target_id, f"⛔️ تم حظرك من البوت")
            else:
                await update.message.reply_text("❌ المستخدم محظور بالفعل")
            
        except ValueError:
            await update.message.reply_text("❌ ايدي غير صحيح")
            return ADMIN_BAN_USER
    
    # ========== رفع حظر ==========
    elif action == "unban":
        try:
            target_id = int(text)
            
            if db.unban_user(target_id):
                await db.save_all()
                await update.message.reply_text(f"✅ تم رفع الحظر عن المستخدم {target_id}")
                await helpers.safe_send_message(context.bot, target_id, "✅ تم رفع الحظر عنك")
            else:
                await update.message.reply_text("❌ المستخدم غير موجود في المحظورين")
            
        except ValueError:
            await update.message.reply_text("❌ ايدي غير صحيح")
            return ADMIN_UNBAN_USER
    
    # ========== تغيير مكافأة الدعوة ==========
    elif action == "change_reward":
        try:
            reward = int(text)
            if reward <= 0:
                await update.message.reply_text("❌ المكافأة يجب ان تكون اكبر من 0")
                return ADMIN_CHANGE_REWARD
            
            db.settings["invite_reward"] = reward
            await db.save_all()
            await update.message.reply_text(f"✅ تم تغيير المكافأة الى {reward} نقطة")
            
        except ValueError:
            await update.message.reply_text("❌ رقم غير صحيح")
            return ADMIN_CHANGE_REWARD
    
    # ========== تغيير سعر العضو ==========
    elif action == "change_price":
        try:
            price = int(text)
            if price <= 0:
                await update.message.reply_text("❌ السعر يجب ان يكون اكبر من 0")
                return ADMIN_CHANGE_PRICE
            
            db.settings["member_price"] = price
            await db.save_all()
            await update.message.reply_text(f"✅ تم تغيير السعر الى {price} نقطة")
            
        except ValueError:
            await update.message.reply_text("❌ رقم غير صحيح")
            return ADMIN_CHANGE_PRICE
    
    # ========== اضافة قناة اجبارية ==========
    elif action == "add_mandatory":
        try:
            parts = [p.strip() for p in text.split('|')]
            if len(parts) != 3:
                await update.message.reply_text("❌ استخدم: الاسم | الرابط | الايدي")
                return ADMIN_ADD_MANDATORY
            
            name, link, chat_id = parts
            
            if not helpers.is_valid_link(link):
                await update.message.reply_text("❌ رابط غير صالح")
                return ADMIN_ADD_MANDATORY
            
            db.add_mandatory_channel(name, link, chat_id)
            await db.save_all()
            await update.message.reply_text(f"✅ تم اضافة القناة: {name}")
            
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {str(e)}")
            return ADMIN_ADD_MANDATORY
    
    # ========== تغيير رسالة الترحيب ==========
    elif action == "change_welcome":
        db.settings["welcome_message"] = text
        await db.save_all()
        await update.message.reply_text("✅ تم تغيير رسالة الترحيب")
    
    # ========== رسالة جماعية ==========
    elif action == "broadcast":
        await update.message.reply_text("🔄 جاري ارسال الرسالة...")
        
        success = 0
        failed = 0
        
        for uid in db.users.keys():
            try:
                await context.bot.send_message(chat_id=int(uid), text=text)
                success += 1
                await asyncio.sleep(0.05)
            except:
                failed += 1
        
        await update.message.reply_text(f"✅ نجح: {success}\n❌ فشل: {failed}")
    
    await update.message.reply_text("⚙️ لوحة التحكم", reply_markup=Keyboards.admin_panel())
    context.user_data.clear()
    return MAIN_MENU

# ==================== معالج الملفات ====================

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ هذه الخاصية للمدراء فقط")
        return MAIN_MENU
    
    if context.user_data.get("admin_action") != "add_numbers":
        await update.message.reply_text("❌ انت غير في وضع اضافة ملفات")
        return MAIN_MENU
    
    doc = update.message.document
    
    if not doc.file_name.endswith('.txt'):
        await update.message.reply_text("❌ فقط ملفات txt مسموحة")
        return ADMIN_ADD_NUMBERS
    
    wait = await update.message.reply_text("🔄 جاري المعالجة...")
    
    try:
        file = await context.bot.get_file(doc.file_id)
        content = await file.download_as_bytearray()
        lines = content.decode('utf-8').split('\n')
        lines = [l.strip() for l in lines if l.strip()]
        
        if not lines:
            await wait.edit_text("❌ الملف فارغ")
            return ADMIN_ADD_NUMBERS
        
        info = db.add_numbers_file(doc.file_name, lines)
        await db.save_all()
        
        await wait.edit_text(
            f"✅ تم رفع الملف\n"
            f"الملف: {doc.file_name}\n"
            f"الصالح: {info['count']}\n"
            f"غير الصالح: {info['invalid']}\n"
            f"المتاح الآن: {len(db.numbers['numbers'])}"
        )
        
    except Exception as e:
        await wait.edit_text(f"❌ خطأ: {str(e)}")
    
    await update.message.reply_text("⚙️ لوحة التحكم", reply_markup=Keyboards.admin_panel())
    context.user_data.clear()
    return MAIN_MENU

# ==================== معالج النصوص العام ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if db.is_banned(user_id):
        await update.message.reply_text("⛔️ أنت محظور")
        return MAIN_MENU
    
    state = context.user_data.get("state", MAIN_MENU)
    
    if state == WAITING_COUNT:
        return await handle_count(update, context)
    elif state == WAITING_LINK:
        return await handle_link(update, context)
    
    if user_id in ADMIN_IDS and state in [ADMIN_ADD_POINTS, ADMIN_DEDUCT_POINTS, ADMIN_ADD_SUPPORT,
                                          ADMIN_ADD_CHANNEL, ADMIN_BAN_USER, ADMIN_UNBAN_USER,
                                          ADMIN_CHANGE_REWARD, ADMIN_CHANGE_PRICE, ADMIN_ADD_MANDATORY,
                                          ADMIN_CHANGE_WELCOME, ADMIN_BROADCAST]:
        return await handle_admin_text(update, context)
    
    await update.message.reply_text("❌ استخدم /start")
    return MAIN_MENU

# ==================== معالج الاخطاء ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"خطأ: {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text("❌ حدث خطأ غير متوقع")
    except:
        pass

# ==================== الدالة الرئيسية ====================

async def post_init(application: Application):
    await application.bot.set_my_commands([BotCommand("start", "بدء استخدام البوت")])
    logger.info("تم اعداد اوامر البوت")

def main():
    print(f"{Fore.CYAN}{'='*60}{Fore.RESET}")
    print(f"{Fore.GREEN}بوت التمويل المتكامل v4.0{Fore.RESET}")
    print(f"{Fore.YELLOW}المطور: System{Fore.RESET}")
    print(f"{Fore.CYAN}{'='*60}{Fore.RESET}")
    
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(button_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                MessageHandler(filters.Document.ALL, handle_document),
            ],
            WAITING_COUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(button_handler),
            ],
            WAITING_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(button_handler),
            ],
            ADMIN_ADD_POINTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            ADMIN_DEDUCT_POINTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            ADMIN_ADD_NUMBERS: [MessageHandler(filters.Document.ALL, handle_document)],
            ADMIN_ADD_SUPPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            ADMIN_ADD_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            ADMIN_BAN_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            ADMIN_UNBAN_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            ADMIN_CHANGE_REWARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            ADMIN_CHANGE_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            ADMIN_ADD_MANDATORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            ADMIN_CHANGE_WELCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    app.add_handler(conv)
    app.add_error_handler(error_handler)
    
    print(f"{Fore.GREEN}✅ البوت يعمل بنجاح{Fore.RESET}")
    print(f"{Fore.CYAN}{'='*60}{Fore.RESET}")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}تم ايقاف البوت{Fore.RESET}")
    except Exception as e:
        print(f"{Fore.RED}خطأ فادح: {e}{Fore.RESET}")
        traceback.print_exc()

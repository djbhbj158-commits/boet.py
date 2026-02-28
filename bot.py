#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
بوت تمويل متكامل لتليجرام - النسخة النهائية المصححة
الإصدار: 3.0
المطور: System
تاريخ التحديث: 2024
"""

import os
import sys
import json
import asyncio
import logging
import random
import string
import time
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
from collections import defaultdict
from enum import Enum
import traceback
from functools import wraps

import aiofiles
from colorama import init, Fore, Style
import pytz

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
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.error import TelegramError, BadRequest, Forbidden, RetryAfter

# تهيئة colorama
init(autoreset=True)

# ==================== التهيئة والإعدادات الأساسية ====================

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# توكن البوت
BOT_TOKEN = "8699966374:AAGCCGehxTQzGbEkBxIe7L3vecLPcvzGrHg"

# ايدي المديرين
ADMIN_IDS = [6615860762, 6130994941]

# مسار المجلدات
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
TEMP_DIR = BASE_DIR / "temp"

# إنشاء المجلدات إذا لم تكن موجودة
for dir_path in [DATA_DIR, LOGS_DIR, TEMP_DIR]:
    dir_path.mkdir(exist_ok=True)

# ==================== تعريف حالات المحادثة ====================

class States(Enum):
    """حالات المحادثة"""
    MAIN_MENU = 0
    WAITING_FOR_MEMBERS_COUNT = 1
    WAITING_FOR_CHANNEL_LINK = 2
    WAITING_FOR_CONFIRMATION = 3
    
    # حالات المدير
    ADMIN_ADD_POINTS = 100
    ADMIN_DEDUCT_POINTS = 101
    ADMIN_ADD_NUMBERS = 102
    ADMIN_ADD_SUPPORT = 103
    ADMIN_ADD_CHANNEL = 104
    ADMIN_BAN_USER = 105
    ADMIN_UNBAN_USER = 106
    ADMIN_CHANGE_REWARD = 107
    ADMIN_CHANGE_PRICE = 108
    ADMIN_ADD_MANDATORY = 109
    ADMIN_CHANGE_WELCOME = 110
    ADMIN_BROADCAST = 111

# ==================== قاعدة البيانات ====================

class Database:
    """قاعدة بيانات البوت"""
    
    def __init__(self):
        self.data_dir = DATA_DIR
        
        # ملفات البيانات
        self.users_file = self.data_dir / "users.json"
        self.numbers_file = self.data_dir / "numbers.json"
        self.settings_file = self.data_dir / "settings.json"
        self.financing_file = self.data_dir / "financing.json"
        self.banned_file = self.data_dir / "banned.json"
        self.mandatory_file = self.data_dir / "mandatory.json"
        self.referrals_file = self.data_dir / "referrals.json"
        self.stats_file = self.data_dir / "stats.json"
        
        # تحميل البيانات
        self.users = self._load_json(self.users_file, {})
        self.numbers = self._load_json(self.numbers_file, self._default_numbers())
        self.settings = self._load_json(self.settings_file, self._default_settings())
        self.financing = self._load_json(self.financing_file, {})
        self.banned = self._load_json(self.banned_file, [])
        self.mandatory = self._load_json(self.mandatory_file, [])
        self.referrals = self._load_json(self.referrals_file, {})
        self.stats = self._load_json(self.stats_file, self._default_stats())
        
        # قفل للكتابة المتزامنة
        self._lock = asyncio.Lock()
        
        logger.info(f"{Fore.GREEN}✅ تم تحميل قاعدة البيانات بنجاح{Fore.RESET}")
    
    def _default_settings(self):
        """الإعدادات الافتراضية"""
        return {
            "invite_reward": 10,
            "member_price": 8,
            "welcome_message": "👋 مرحباً بك في بوت التمويل المتكامل\n📍 يمكنك تجميع النقاط وتمويل قنواتك بكل سهولة",
            "support_username": "support",
            "channel_link": "https://t.me/your_channel",
            "min_financing": 10,
            "max_financing": 1000,
            "daily_bonus": 5,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "version": "3.0"
        }
    
    def _default_numbers(self):
        """هيكل ملف الأرقام الافتراضي"""
        return {
            "numbers": [],
            "files": [],
            "used_numbers": [],
            "invalid_numbers": [],
            "total_added": 0,
            "total_used": 0,
            "last_update": datetime.now().isoformat()
        }
    
    def _default_stats(self):
        """الإحصائيات الافتراضية"""
        return {
            "total_users": 0,
            "total_points": 0,
            "total_financing": 0,
            "total_spent": 0,
            "total_referrals": 0,
            "bot_start_time": datetime.now().isoformat(),
            "last_backup": None
        }
    
    def _load_json(self, file_path: Path, default: Any) -> Any:
        """تحميل ملف JSON"""
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"❌ خطأ في تحميل {file_path.name}: {e}")
        return default
    
    async def _save_json(self, file_path: Path, data: Any) -> bool:
        """حفظ ملف JSON مع قفل"""
        async with self._lock:
            try:
                async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(data, ensure_ascii=False, indent=2))
                return True
            except Exception as e:
                logger.error(f"❌ خطأ في حفظ {file_path.name}: {e}")
                return False
    
    async def save_all(self) -> bool:
        """حفظ جميع البيانات"""
        tasks = [
            self._save_json(self.users_file, self.users),
            self._save_json(self.numbers_file, self.numbers),
            self._save_json(self.settings_file, self.settings),
            self._save_json(self.financing_file, self.financing),
            self._save_json(self.banned_file, self.banned),
            self._save_json(self.mandatory_file, self.mandatory),
            self._save_json(self.referrals_file, self.referrals),
            self._save_json(self.stats_file, self.stats)
        ]
        
        results = await asyncio.gather(*tasks)
        return all(results)
    
    # ========== إدارة المستخدمين ==========
    
    def get_user(self, user_id: int) -> Dict:
        """الحصول على بيانات مستخدم"""
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
            self.stats["total_users"] = len(self.users)
        
        self.users[user_id]["last_active"] = datetime.now().isoformat()
        return self.users[user_id]
    
    def _generate_code(self, length: int = 8) -> str:
        """توليد كود عشوائي"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    def update_user_info(self, user_id: int, **kwargs):
        """تحديث معلومات المستخدم"""
        user_id = str(user_id)
        if user_id in self.users:
            self.users[user_id].update(kwargs)
    
    def add_points(self, user_id: int, points: int) -> bool:
        """إضافة نقاط لمستخدم"""
        user_id = str(user_id)
        user = self.get_user(int(user_id))
        user["points"] += points
        user["total_earned"] += points
        self.stats["total_points"] += points
        return True
    
    def deduct_points(self, user_id: int, points: int) -> bool:
        """خصم نقاط من مستخدم"""
        user_id = str(user_id)
        user = self.get_user(int(user_id))
        if user["points"] >= points:
            user["points"] -= points
            user["total_spent"] += points
            self.stats["total_spent"] += points
            return True
        return False
    
    # ========== إدارة الدعوات ==========
    
    def process_referral(self, referrer_id: int, new_user_id: int) -> bool:
        """معالجة دعوة جديدة"""
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
        
        self.stats["total_referrals"] += 1
        return True
    
    def get_referral_link(self, user_id: int, bot_username: str) -> str:
        """الحصول على رابط الدعوة"""
        user = self.get_user(user_id)
        return f"https://t.me/{bot_username}?start={user['referral_code']}"
    
    def get_top_referrers(self, limit: int = 3) -> List[Dict]:
        """الحصول على أفضل الداعين"""
        referrers = []
        for user_id, ref_list in self.referrals.items():
            referrers.append({
                "user_id": user_id,
                "count": len(ref_list),
                "username": self.users.get(user_id, {}).get("username", "Unknown")
            })
        
        referrers.sort(key=lambda x: x["count"], reverse=True)
        return referrers[:limit]
    
    # ========== إدارة الأرقام ==========
    
    def add_numbers_file(self, filename: str, numbers: List[str]) -> Dict:
        """إضافة ملف أرقام جديد"""
        valid_numbers = []
        invalid_numbers = []
        
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
                invalid_numbers.append(num)
        
        file_info = {
            "name": filename,
            "count": len(valid_numbers),
            "valid": len(valid_numbers),
            "invalid": len(invalid_numbers),
            "added_date": datetime.now().isoformat()
        }
        
        self.numbers["files"].append(file_info)
        self.numbers["numbers"].extend(valid_numbers)
        self.numbers["invalid_numbers"].extend(invalid_numbers)
        self.numbers["total_added"] += len(valid_numbers)
        self.numbers["last_update"] = datetime.now().isoformat()
        
        return file_info
    
    def get_available_numbers(self, count: int) -> List[str]:
        """الحصول على أرقام متاحة للتمويل"""
        available = []
        for _ in range(min(count, len(self.numbers["numbers"]))):
            if self.numbers["numbers"]:
                num = self.numbers["numbers"].pop(0)
                available.append(num)
                self.numbers["used_numbers"].append({
                    "number": num,
                    "used_at": datetime.now().isoformat()
                })
        
        self.numbers["total_used"] += len(available)
        return available
    
    def get_numbers_stats(self) -> Dict:
        """إحصائيات الأرقام"""
        return {
            "available": len(self.numbers["numbers"]),
            "used": len(self.numbers["used_numbers"]),
            "invalid": len(self.numbers["invalid_numbers"]),
            "files": len(self.numbers["files"]),
            "total_added": self.numbers["total_added"],
            "total_used": self.numbers["total_used"]
        }
    
    # ========== إدارة التمويل ==========
    
    def create_financing(self, user_id: int, channel_link: str, members_count: int, cost: int) -> str:
        """إنشاء عملية تمويل جديدة"""
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
            "created_at": datetime.now().isoformat(),
            "last_update": datetime.now().isoformat(),
            "used_numbers": []
        }
        
        user = self.get_user(int(user_id))
        user["financing_count"] += 1
        
        self.stats["total_financing"] += 1
        self.stats["total_spent"] += cost
        
        return finance_id
    
    def update_financing(self, finance_id: str, **kwargs) -> Optional[Dict]:
        """تحديث عملية تمويل"""
        if finance_id in self.financing:
            self.financing[finance_id].update(kwargs)
            self.financing[finance_id]["last_update"] = datetime.now().isoformat()
            return self.financing[finance_id]
        return None
    
    def add_financing_member(self, finance_id: str, number: str) -> Dict:
        """إضافة عضو في عملية تمويل"""
        finance = self.financing.get(finance_id)
        if not finance:
            return {"success": False, "error": "عملية تمويل غير موجودة"}
        
        if finance["added_members"] >= finance["total_members"]:
            return {"success": False, "error": "اكتمل العدد المطلوب"}
        
        finance["added_members"] += 1
        finance["used_numbers"].append({
            "number": number,
            "added_at": datetime.now().isoformat()
        })
        
        if finance["added_members"] >= finance["total_members"]:
            finance["status"] = "completed"
        
        return {
            "success": True,
            "finance": finance,
            "completed": finance["status"] == "completed",
            "progress": f"{finance['added_members']}/{finance['total_members']}"
        }
    
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
        return str(user_id) in self.banned
    
    def ban_user(self, user_id: int, reason: str = "") -> bool:
        """حظر مستخدم"""
        user_id = str(user_id)
        if int(user_id) in ADMIN_IDS:
            return False
        
        if user_id not in self.banned:
            self.banned.append({
                "user_id": user_id,
                "reason": reason,
                "banned_at": datetime.now().isoformat()
            })
            if user_id in self.users:
                self.users[user_id]["is_banned"] = True
            return True
        return False
    
    def unban_user(self, user_id: int) -> bool:
        """رفع الحظر عن مستخدم"""
        user_id = str(user_id)
        for i, banned in enumerate(self.banned):
            if banned["user_id"] == user_id:
                self.banned.pop(i)
                if user_id in self.users:
                    self.users[user_id]["is_banned"] = False
                return True
        return False
    
    # ========== إدارة القنوات الإجبارية ==========
    
    def add_mandatory_channel(self, name: str, link: str, chat_id: str) -> Dict:
        """إضافة قناة إجبارية"""
        channel = {
            "name": name,
            "link": link,
            "chat_id": chat_id,
            "added_at": datetime.now().isoformat(),
            "is_active": True
        }
        self.mandatory.append(channel)
        return channel
    
    def remove_mandatory_channel(self, chat_id: str) -> bool:
        """حذف قناة إجبارية"""
        for i, channel in enumerate(self.mandatory):
            if str(channel["chat_id"]) == str(chat_id):
                self.mandatory.pop(i)
                return True
        return False
    
    async def check_mandatory_subscription(self, user_id: int, bot) -> Tuple[bool, List[Dict]]:
        """التحقق من اشتراك المستخدم في القنوات الإجبارية"""
        if not self.mandatory:
            return True, []
        
        not_joined = []
        for channel in self.mandatory:
            if not channel.get("is_active", True):
                continue
            
            try:
                chat_id = channel["chat_id"]
                if str(chat_id).lstrip('-').isdigit():
                    chat_id = int(chat_id)
                
                member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
                    not_joined.append(channel)
            except:
                not_joined.append(channel)
        
        return len(not_joined) == 0, not_joined
    
    # ========== الإحصائيات ==========
    
    def get_bot_stats(self) -> Dict:
        """إحصائيات البوت الكاملة"""
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        
        active_today = 0
        for user_data in self.users.values():
            last_active = user_data.get("last_active", "")
            if last_active and last_active.startswith(today):
                active_today += 1
        
        total_points = sum(u.get("points", 0) for u in self.users.values())
        
        financing_today = 0
        for finance in self.financing.values():
            created = finance.get("created_at", "")
            if created.startswith(today):
                financing_today += 1
        
        numbers_stats = self.get_numbers_stats()
        
        return {
            "total_users": len(self.users),
            "active_today": active_today,
            "total_points": total_points,
            "total_financing": len(self.financing),
            "financing_today": financing_today,
            "completed_financing": sum(1 for f in self.financing.values() if f["status"] == "completed"),
            "pending_financing": sum(1 for f in self.financing.values() if f["status"] == "pending"),
            "total_spent": self.stats["total_spent"],
            "total_referrals": self.stats["total_referrals"],
            "banned_count": len(self.banned),
            "numbers": numbers_stats,
            "mandatory_channels": len(self.mandatory),
            "version": self.settings["version"]
        }

# إنشاء كائن قاعدة البيانات
db = Database()

# ==================== أدوات مساعدة ====================

class Helpers:
    """فئة الأدوات المساعدة"""
    
    @staticmethod
    def format_number(num: int) -> str:
        """تنسيق الأرقام"""
        if num >= 1_000_000:
            return f"{num/1_000_000:.1f}M"
        if num >= 1_000:
            return f"{num/1_000:.1f}K"
        return str(num)
    
    @staticmethod
    def escape_markdown(text: str) -> str:
        """تجنب أحرف Markdown"""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    @staticmethod
    def is_valid_link(link: str) -> bool:
        """التحقق من صحة الرابط"""
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
    async def safe_edit_message(query, text: str, reply_markup=None, parse_mode=None):
        """تعديل الرسالة بأمان"""
        try:
            await query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            return True
        except BadRequest as e:
            if "Message is not modified" in str(e):
                # تجاهل هذا الخطأ
                return False
            logger.warning(f"خطأ في تعديل الرسالة: {e}")
            return False
        except Exception as e:
            logger.warning(f"خطأ في تعديل الرسالة: {e}")
            return False
    
    @staticmethod
    async def safe_send_message(bot, chat_id: int, text: str, **kwargs) -> bool:
        """إرسال رسالة بأمان"""
        try:
            await bot.send_message(chat_id=chat_id, text=text, **kwargs)
            return True
        except Exception as e:
            logger.warning(f"فشل ارسال رسالة للمستخدم {chat_id}: {e}")
            return False

helpers = Helpers()

# ==================== لوحات المفاتيح ====================

class Keyboards:
    """فئة لوحات المفاتيح"""
    
    @staticmethod
    def main_menu(user_id: int) -> InlineKeyboardMarkup:
        """لوحة المفاتيح الرئيسية للمستخدم"""
        user = db.get_user(user_id)
        
        # بناء القائمة الرئيسية
        keyboard = [
            [
                InlineKeyboardButton("💰 تجميع النقاط", callback_data="collect_points"),
                InlineKeyboardButton("🚀 تمويل مشتركين", callback_data="finance_members")
            ],
            [
                InlineKeyboardButton("📊 تمويلاتي", callback_data="my_financing"),
                InlineKeyboardButton("📈 احصائياتي", callback_data="my_stats")
            ],
            [
                InlineKeyboardButton("🎁 المكافأة اليومية", callback_data="daily_bonus"),
                InlineKeyboardButton("👥 دعوة صديق", callback_data="invite_friend")
            ],
            [
                InlineKeyboardButton("🆘 الدعم الفني", url=f"https://t.me/{db.settings['support_username']}"),
                InlineKeyboardButton("📢 قناة البوت", url=db.settings["channel_link"])
            ],
            [InlineKeyboardButton("🔄 تحديث", callback_data="refresh")]
        ]
        
        # إضافة زر لوحة التحكم للمديرين
        if user_id in ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("⚙️ لوحة التحكم", callback_data="admin_panel")])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def admin_panel() -> InlineKeyboardMarkup:
        """لوحة تحكم المدير"""
        keyboard = [
            [InlineKeyboardButton("📊 احصائيات البوت", callback_data="admin_stats")],
            [
                InlineKeyboardButton("💰 شحن رصيد", callback_data="admin_add_points"),
                InlineKeyboardButton("💸 خصم رصيد", callback_data="admin_deduct_points")
            ],
            [
                InlineKeyboardButton("📁 اضافة ملف ارقام", callback_data="admin_add_numbers"),
                InlineKeyboardButton("📞 احصائيات الارقام", callback_data="admin_numbers_stats")
            ],
            [
                InlineKeyboardButton("👤 تغيير حساب الدعم", callback_data="admin_add_support"),
                InlineKeyboardButton("🔗 تغيير رابط القناة", callback_data="admin_add_channel")
            ],
            [
                InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban"),
                InlineKeyboardButton("✅ رفع حظر", callback_data="admin_unban")
            ],
            [
                InlineKeyboardButton("🎁 تغيير مكافأة الدعوة", callback_data="admin_change_reward"),
                InlineKeyboardButton("💵 تغيير سعر العضو", callback_data="admin_change_price")
            ],
            [
                InlineKeyboardButton("📢 اضافة قناة اجبارية", callback_data="admin_add_mandatory"),
                InlineKeyboardButton("📋 عرض القنوات الاجبارية", callback_data="admin_view_mandatory")
            ],
            [
                InlineKeyboardButton("✏️ تغيير رسالة الترحيب", callback_data="admin_change_welcome"),
                InlineKeyboardButton("📨 رسالة جماعية", callback_data="admin_broadcast")
            ],
            [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="back_to_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def back_button(callback_data: str = "back_to_main") -> InlineKeyboardMarkup:
        """زر رجوع"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data=callback_data)]
        ])
    
    @staticmethod
    def cancel_button() -> InlineKeyboardMarkup:
        """زر إلغاء"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
        ])

# ==================== معالج الاشتراك الإجباري ====================

class MandatoryCheck:
    """التحقق من الاشتراك الإجباري"""
    
    @staticmethod
    async def check_and_handle(user_id: int, context: ContextTypes.DEFAULT_TYPE, 
                              update: Update = None, query=None) -> bool:
        """التحقق ومعالجة الاشتراك الإجباري"""
        
        if user_id in ADMIN_IDS:
            return True
        
        is_subscribed, not_joined = await db.check_mandatory_subscription(user_id, context.bot)
        
        if not is_subscribed:
            text = "⚠️ **عذراً، يجب الاشتراك في القنوات التالية اولاً**\n\n"
            
            for channel in not_joined:
                text += f"📢 {channel['name']}\n"
                text += f"🔗 [اضغط للاشتراك]({channel['link']})\n\n"
            
            text += "✅ بعد الاشتراك اضغط على زر التحقق"
            
            keyboard = []
            for channel in not_joined:
                keyboard.append([InlineKeyboardButton(
                    text=f"📢 {channel['name']}",
                    url=channel["link"]
                )])
            
            keyboard.append([InlineKeyboardButton(
                text="✅ تحقق من الاشتراك",
                callback_data="check_subscription"
            )])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if query:
                await query.edit_message_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            elif update:
                await update.message.reply_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            
            return False
        
        return True

# ==================== معالج البداية ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج أمر البدء"""
    user = update.effective_user
    user_id = user.id
    
    logger.info(f"👤 مستخدم جديد: {user_id} - {user.first_name}")
    
    # التحقق من الحظر
    if db.is_banned(user_id):
        await update.message.reply_text(
            "⛔️ **عذراً، أنت محظور من استخدام البوت**",
            parse_mode=ParseMode.MARKDOWN
        )
        return States.MAIN_MENU.value
    
    # معالجة رمز الدعوة
    args = context.args
    if args and len(args) > 0:
        referral_code = args[0]
        
        for uid, u_data in db.users.items():
            if u_data.get("referral_code") == referral_code and str(uid) != str(user_id):
                referrer_id = int(uid)
                
                if db.process_referral(referrer_id, user_id):
                    await helpers.safe_send_message(
                        context.bot,
                        referrer_id,
                        f"🎉 **مبروك!**\n"
                        f"قام {user.first_name} بالانضمام عبر رابط دعوتك\n"
                        f"💰 تم اضافة {db.settings['invite_reward']} نقطة الى رصيدك",
                        parse_mode=ParseMode.MARKDOWN
                    )
                break
    
    # تحديث معلومات المستخدم
    user_data = db.get_user(user_id)
    db.update_user_info(
        user_id,
        username=user.username,
        first_name=user.first_name
    )
    
    await db.save_all()
    
    # التحقق من الاشتراك الإجباري
    if not await MandatoryCheck.check_and_handle(user_id, context, update=update):
        return States.MAIN_MENU.value
    
    # رسالة الترحيب
    welcome_text = (
        f"{db.settings['welcome_message']}\n\n"
        f"👤 **مرحباً {helpers.escape_markdown(user.first_name)}**\n"
        f"🆔 **ايديك:** `{user_id}`\n"
        f"⭐️ **نقاطك:** {user_data['points']}\n"
        f"👥 **عدد من دعوتهم:** {user_data['referrals']}"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=Keyboards.main_menu(user_id),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return States.MAIN_MENU.value

# ==================== معالج التحقق من الاشتراك ====================

async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج التحقق من الاشتراك"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    is_subscribed, not_joined = await db.check_mandatory_subscription(user_id, context.bot)
    
    if is_subscribed:
        user_data = db.get_user(user_id)
        welcome_text = (
            f"{db.settings['welcome_message']}\n\n"
            f"👤 **مرحباً {helpers.escape_markdown(query.from_user.first_name)}**\n"
            f"🆔 **ايديك:** `{user_id}`\n"
            f"⭐️ **نقاطك:** {user_data['points']}\n"
            f"👥 **عدد من دعوتهم:** {user_data['referrals']}"
        )
        
        await query.edit_message_text(
            welcome_text,
            reply_markup=Keyboards.main_menu(user_id),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        text = "❌ **لم تشترك في جميع القنوات بعد**\n\n"
        for channel in not_joined:
            text += f"📢 {channel['name']}\n"
            text += f"🔗 [اضغط للاشتراك]({channel['link']})\n\n"
        text += "✅ بعد الاشتراك اضغط على زر التحقق مرة اخرى"
        
        keyboard = []
        for channel in not_joined:
            keyboard.append([InlineKeyboardButton(
                text=f"📢 {channel['name']}",
                url=channel["link"]
            )])
        keyboard.append([InlineKeyboardButton(
            text="✅ تحقق من الاشتراك",
            callback_data="check_subscription"
        )])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    return States.MAIN_MENU.value

# ==================== معالج أزرار المستخدم ====================

async def user_buttons_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج أزرار المستخدم"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    logger.info(f"زر مستخدم: {data} من {user_id}")
    
    # التحقق من الحظر
    if db.is_banned(user_id) and data != "check_subscription":
        await query.edit_message_text("⛔️ أنت محظور من استخدام البوت")
        return States.MAIN_MENU.value
    
    # التحقق من الاشتراك الإجباري
    if user_id not in ADMIN_IDS and data not in ["check_subscription", "back_to_main"]:
        if not await MandatoryCheck.check_and_handle(user_id, context, query=query):
            return States.MAIN_MENU.value
    
    # ========== تجميع النقاط ==========
    if data == "collect_points":
        user_data = db.get_user(user_id)
        bot_info = await context.bot.get_me()
        referral_link = db.get_referral_link(user_id, bot_info.username)
        
        # الحصول على أفضل الداعين
        top_referrers = db.get_top_referrers(3)
        
        text = (
            "💰 **تجميع النقاط**\n\n"
            "📌 شارك الرابط التالي مع اصدقائك\n"
            "عند دخول كل صديق عبر رابطك ستحصل على نقاط\n\n"
            f"🏆 **رصيدك الحالي:** {user_data['points']} نقطة\n"
            f"👥 **عدد الدعوات الناجحة:** {user_data['referrals']}\n"
            f"🎁 **مكافأة كل دعوة:** {db.settings['invite_reward']} نقطة\n\n"
            f"🔗 **رابط الدعوة الخاص بك:**\n"
            f"`{referral_link}`\n\n"
        )
        
        # إضافة أفضل الداعين
        if top_referrers:
            text += "🏅 **أفضل الداعين:**\n"
            for i, ref in enumerate(top_referrers, 1):
                user_info = db.users.get(ref["user_id"], {})
                name = user_info.get("first_name", "مستخدم")[:20]
                text += f"{i}. {name} - `{ref['user_id']}` - {ref['count']} دعوة\n"
        
        share_keyboard = [
            [
                InlineKeyboardButton("📱 مشاركة", switch_inline_query=f"انضم الي في بوت التمويل 🚀\n{referral_link}"),
                InlineKeyboardButton("📋 نسخ الرابط", callback_data="copy_link")
            ],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
        ]
        
        await helpers.safe_edit_message(
            query,
            text,
            reply_markup=InlineKeyboardMarkup(share_keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== نسخ الرابط ==========
    elif data == "copy_link":
        bot_info = await context.bot.get_me()
        user_data = db.get_user(user_id)
        referral_link = db.get_referral_link(user_id, bot_info.username)
        
        await query.answer(f"✅ تم نسخ الرابط: {referral_link}", show_alert=True)
    
    # ========== تمويل مشتركين ==========
    elif data == "finance_members":
        user_data = db.get_user(user_id)
        member_price = db.settings["member_price"]
        min_finance = db.settings["min_financing"]
        max_finance = db.settings["max_financing"]
        
        text = (
            "🚀 **تمويل مشتركين**\n\n"
            f"⭐️ **رصيدك الحالي:** {user_data['points']} نقطة\n"
            f"💵 **سعر العضو الواحد:** {member_price} نقطة\n"
            f"📊 **الحد الأدنى:** {min_finance} عضو\n"
            f"📊 **الحد الأقصى:** {max_finance} عضو\n\n"
            f"📞 **الارقام المتاحة:** {len(db.numbers['numbers'])}\n\n"
            "📝 **ارسل الآن عدد الاعضاء الذي تريد تمويلهم**\n"
            "مثال: `100`\n\n"
            "⚠️ **ملاحظة مهمة:** يجب ان يكون البوت ادمن في قناتك"
        )
        
        await helpers.safe_edit_message(
            query,
            text,
            reply_markup=Keyboards.cancel_button(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data["state"] = States.WAITING_FOR_MEMBERS_COUNT.value
        return States.WAITING_FOR_MEMBERS_COUNT.value
    
    # ========== تمويلاتي ==========
    elif data == "my_financing":
        finances = db.get_user_financing(user_id)
        
        if not finances:
            text = "📊 **لا يوجد لديك تمويلات حالية**\n\nاستخدم زر تمويل مشتركين للبدء"
        else:
            text = "📊 **تمويلاتك**\n\n"
            for finance in finances[-5:]:
                status_emoji = {
                    "pending": "⏳",
                    "processing": "🔄",
                    "completed": "✅",
                    "failed": "❌"
                }.get(finance["status"], "⏳")
                
                text += f"{status_emoji} **{finance['id'][:8]}...**\n"
                text += f"   👥 التقدم: {finance['added_members']}/{finance['total_members']}\n"
                text += f"   💰 التكلفة: {finance['cost']} نقطة\n"
                text += f"   📅 التاريخ: {finance['created_at'][:10]}\n\n"
        
        await helpers.safe_edit_message(
            query,
            text,
            reply_markup=Keyboards.back_button(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== احصائياتي ==========
    elif data == "my_stats":
        user_data = db.get_user(user_id)
        
        completed = sum(1 for f in db.financing.values() 
                       if f["user_id"] == str(user_id) and f["status"] == "completed")
        success_rate = (completed / user_data['financing_count'] * 100) if user_data['financing_count'] > 0 else 0
        
        text = (
            "📈 **احصائياتك الشخصية**\n\n"
            f"🆔 **الايدي:** `{user_id}`\n"
            f"👤 **الاسم:** {query.from_user.first_name}\n"
            f"⭐️ **رصيد النقاط:** {user_data['points']}\n"
            f"👥 **عدد الدعوات:** {user_data['referrals']}\n"
            f"🚀 **عدد عمليات التمويل:** {user_data['financing_count']}\n"
            f"💸 **اجمالي المنفق:** {user_data['total_spent']} نقطة\n"
            f"💰 **اجمالي المكتسب:** {user_data['total_earned']} نقطة\n"
            f"📊 **نسبة النجاح:** {success_rate:.1f}%\n"
            f"📅 **تاريخ الانضمام:** {user_data['joined_date'][:10]}"
        )
        
        await helpers.safe_edit_message(
            query,
            text,
            reply_markup=Keyboards.back_button(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== المكافأة اليومية ==========
    elif data == "daily_bonus":
        user_data = db.get_user(user_id)
        now = datetime.now()
        last_daily = user_data.get("last_daily")
        
        if last_daily:
            last = datetime.fromisoformat(last_daily)
            if (now - last) < timedelta(hours=24):
                remaining = timedelta(hours=24) - (now - last)
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60
                
                await query.answer(
                    f"⏳ يمكنك الحصول على المكافأة بعد {hours} ساعة و {minutes} دقيقة",
                    show_alert=True
                )
                return States.MAIN_MENU.value
        
        bonus = db.settings["daily_bonus"]
        db.add_points(user_id, bonus)
        db.update_user_info(user_id, last_daily=now.isoformat())
        await db.save_all()
        
        await query.answer(f"✅ تم اضافة {bonus} نقطة كمكافأة يومية", show_alert=True)
        
        # تحديث العرض
        user_data = db.get_user(user_id)
        welcome_text = (
            f"{db.settings['welcome_message']}\n\n"
            f"👤 **مرحباً {query.from_user.first_name}**\n"
            f"🆔 **ايديك:** `{user_id}`\n"
            f"⭐️ **نقاطك:** {user_data['points']}\n"
            f"👥 **عدد من دعوتهم:** {user_data['referrals']}"
        )
        
        await helpers.safe_edit_message(
            query,
            welcome_text,
            reply_markup=Keyboards.main_menu(user_id),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== دعوة صديق ==========
    elif data == "invite_friend":
        bot_info = await context.bot.get_me()
        user_data = db.get_user(user_id)
        referral_link = db.get_referral_link(user_id, bot_info.username)
        
        # الحصول على أفضل الداعين
        top_referrers = db.get_top_referrers(3)
        
        text = (
            "👥 **دعوة صديق**\n\n"
            "🎁 شارك الرابط التالي مع اصدقائك\n"
            "ستحصل على مكافأة عند كل صديق ينضم\n\n"
            f"💰 **المكافأة:** {db.settings['invite_reward']} نقطة لكل صديق\n"
            f"👥 **عدد دعواتك:** {user_data['referrals']}\n"
            f"🔗 **رابط الدعوة:**\n`{referral_link}`\n\n"
        )
        
        # إضافة أفضل الداعين
        if top_referrers:
            text += "🏅 **أفضل الداعين:**\n"
            for i, ref in enumerate(top_referrers, 1):
                user_info = db.users.get(ref["user_id"], {})
                name = user_info.get("first_name", "مستخدم")[:20]
                text += f"{i}. `{ref['user_id']}` - {ref['count']} دعوة\n"
        
        share_keyboard = [
            [InlineKeyboardButton("📱 مشاركة", switch_inline_query=f"انضم الي في بوت التمويل 🚀\n{referral_link}")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
        ]
        
        await helpers.safe_edit_message(
            query,
            text,
            reply_markup=InlineKeyboardMarkup(share_keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== تحديث ==========
    elif data == "refresh":
        user_data = db.get_user(user_id)
        text = (
            f"{db.settings['welcome_message']}\n\n"
            f"👤 **مرحباً {query.from_user.first_name}**\n"
            f"🆔 **ايديك:** `{user_id}`\n"
            f"⭐️ **نقاطك:** {user_data['points']}\n"
            f"👥 **عدد من دعوتهم:** {user_data['referrals']}"
        )
        
        await helpers.safe_edit_message(
            query,
            text,
            reply_markup=Keyboards.main_menu(user_id),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== رجوع للقائمة الرئيسية ==========
    elif data == "back_to_main":
        user_data = db.get_user(user_id)
        text = (
            f"{db.settings['welcome_message']}\n\n"
            f"👤 **مرحباً {query.from_user.first_name}**\n"
            f"🆔 **ايديك:** `{user_id}`\n"
            f"⭐️ **نقاطك:** {user_data['points']}\n"
            f"👥 **عدد من دعوتهم:** {user_data['referrals']}"
        )
        
        await helpers.safe_edit_message(
            query,
            text,
            reply_markup=Keyboards.main_menu(user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data.clear()
    
    # ========== لوحة تحكم المدير ==========
    elif data == "admin_panel" and user_id in ADMIN_IDS:
        await helpers.safe_edit_message(
            query,
            "⚙️ **لوحة تحكم المدير**\nاختر العملية التي تريد تنفيذها",
            reply_markup=Keyboards.admin_panel(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== إلغاء ==========
    elif data == "cancel":
        user_data = db.get_user(user_id)
        text = (
            f"{db.settings['welcome_message']}\n\n"
            f"👤 **مرحباً {query.from_user.first_name}**\n"
            f"🆔 **ايديك:** `{user_id}`\n"
            f"⭐️ **نقاطك:** {user_data['points']}\n"
            f"👥 **عدد من دعوتهم:** {user_data['referrals']}"
        )
        
        await helpers.safe_edit_message(
            query,
            text,
            reply_markup=Keyboards.main_menu(user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data.clear()
    
    await db.save_all()
    return States.MAIN_MENU.value

# ==================== معالج عدد الاعضاء ====================

async def handle_members_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج استلام عدد الاعضاء"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if text.lower() in ["الغاء", "cancel"]:
        await update.message.reply_text(
            "✅ تم الغاء العملية",
            reply_markup=Keyboards.main_menu(user_id)
        )
        context.user_data.clear()
        return States.MAIN_MENU.value
    
    try:
        count = int(text)
        min_count = db.settings["min_financing"]
        max_count = db.settings["max_financing"]
        
        if count < min_count:
            await update.message.reply_text(f"❌ الحد الأدنى هو {min_count} عضو")
            return States.WAITING_FOR_MEMBERS_COUNT.value
        
        if count > max_count:
            await update.message.reply_text(f"❌ الحد الأقصى هو {max_count} عضو")
            return States.WAITING_FOR_MEMBERS_COUNT.value
        
        # التحقق من وجود ارقام كافية
        if len(db.numbers["numbers"]) < count:
            await update.message.reply_text(
                f"❌ لا يوجد ارقام كافية\nالمتوفر: {len(db.numbers['numbers'])} رقم فقط"
            )
            context.user_data.clear()
            return States.MAIN_MENU.value
        
        user_data = db.get_user(user_id)
        member_price = db.settings["member_price"]
        total_cost = count * member_price
        
        if user_data["points"] < total_cost:
            await update.message.reply_text(
                f"❌ **رصيدك غير كافي**\n\n"
                f"💰 المطلوب: {total_cost} نقطة\n"
                f"⭐️ رصيدك: {user_data['points']} نقطة",
                parse_mode=ParseMode.MARKDOWN
            )
            context.user_data.clear()
            return States.MAIN_MENU.value
        
        context.user_data["finance"] = {
            "count": count,
            "cost": total_cost
        }
        
        await update.message.reply_text(
            f"✅ **تم حساب التكلفة**\n\n"
            f"👥 العدد: {count}\n"
            f"💰 التكلفة: {total_cost} نقطة\n"
            f"⭐️ الرصيد المتبقي: {user_data['points'] - total_cost} نقطة\n\n"
            f"📤 **ارسل رابط قناتك الآن**\n"
            f"مثال: `https://t.me/your_channel`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=Keyboards.cancel_button()
        )
        
        return States.WAITING_FOR_CHANNEL_LINK.value
        
    except ValueError:
        await update.message.reply_text("❌ الرجاء ادخال رقم صحيح")
        return States.WAITING_FOR_MEMBERS_COUNT.value

# ==================== معالج رابط القناة ====================

async def handle_channel_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج استلام رابط القناة"""
    user_id = update.effective_user.id
    link = update.message.text.strip()
    
    if link.lower() in ["الغاء", "cancel"]:
        await update.message.reply_text(
            "✅ تم الغاء العملية",
            reply_markup=Keyboards.main_menu(user_id)
        )
        context.user_data.clear()
        return States.MAIN_MENU.value
    
    if not helpers.is_valid_link(link):
        await update.message.reply_text(
            "❌ رابط غير صالح\n"
            "ارسل رابط مثل: https://t.me/your_channel"
        )
        return States.WAITING_FOR_CHANNEL_LINK.value
    
    if link.startswith('@'):
        clean_link = link
    elif 't.me/' not in link:
        clean_link = f"https://t.me/{link}"
    else:
        clean_link = link
    
    finance_data = context.user_data.get("finance")
    if not finance_data:
        await update.message.reply_text("❌ حدث خطأ، الرجاء المحاولة مرة اخرى")
        return States.MAIN_MENU.value
    
    # خصم النقاط
    if not db.deduct_points(user_id, finance_data["cost"]):
        await update.message.reply_text("❌ فشل خصم النقاط")
        return States.MAIN_MENU.value
    
    # إنشاء عملية تمويل
    finance_id = db.create_financing(
        user_id,
        clean_link,
        finance_data["count"],
        finance_data["cost"]
    )
    
    await db.save_all()
    
    await update.message.reply_text(
        f"✅ **تم بدء التمويل بنجاح**\n\n"
        f"🆔 المعرف: `{finance_id}`\n"
        f"👥 العدد: {finance_data['count']}\n"
        f"💰 التكلفة: {finance_data['cost']} نقطة\n\n"
        f"⏳ جاري التمويل...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # بدء التمويل في الخلفية
    asyncio.create_task(process_financing(update.get_bot(), finance_id))
    
    # العودة للقائمة الرئيسية
    user_data = db.get_user(user_id)
    welcome_text = (
        f"{db.settings['welcome_message']}\n\n"
        f"👤 **مرحباً {update.effective_user.first_name}**\n"
        f"🆔 **ايديك:** `{user_id}`\n"
        f"⭐️ **نقاطك:** {user_data['points']}\n"
        f"👥 **عدد من دعوتهم:** {user_data['referrals']}"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=Keyboards.main_menu(user_id),
        parse_mode=ParseMode.MARKDOWN
    )
    
    context.user_data.clear()
    return States.MAIN_MENU.value

# ==================== معالج التمويل في الخلفية ====================

async def process_financing(bot, finance_id: str):
    """معالجة التمويل في الخلفية"""
    await asyncio.sleep(2)
    
    finance = db.financing.get(finance_id)
    if not finance:
        return
    
    logger.info(f"🚀 بدء تمويل: {finance_id}")
    
    db.update_financing(finance_id, status="processing")
    await db.save_all()
    
    user_id = int(finance["user_id"])
    remaining = finance["total_members"] - finance["added_members"]
    
    for i in range(remaining):
        current = db.financing.get(finance_id)
        if not current or current["status"] != "processing":
            break
        
        numbers = db.get_available_numbers(1)
        if not numbers:
            await helpers.safe_send_message(
                bot,
                user_id,
                "⚠️ نفذت الارقام المتاحة، سيتم اكمال التمويل لاحقاً"
            )
            break
        
        number = numbers[0]
        
        # محاكاة اضافة العضو
        await asyncio.sleep(random.uniform(1, 2))
        
        result = db.add_financing_member(finance_id, number)
        
        if result["success"] and (i + 1) % 5 == 0:
            await helpers.safe_send_message(
                bot,
                user_id,
                f"✅ تم اضافة {i+1} عضو\nالتقدم: {result['progress']}"
            )
        
        await db.save_all()
        
        if result["completed"]:
            await helpers.safe_send_message(
                bot,
                user_id,
                f"✅ **اكتمل التمويل بنجاح**\n\n"
                f"👥 اجمالي الاعضاء: {finance['total_members']}",
                parse_mode=ParseMode.MARKDOWN
            )
            break
    
    logger.info(f"🏁 انتهاء تمويل: {finance_id}")

# ==================== معالج أزرار المدير ====================

async def admin_buttons_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج أزرار المدير"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("⛔️ هذه الخاصية للمدراء فقط")
        return States.MAIN_MENU.value
    
    data = query.data
    logger.info(f"🔧 زر مدير: {data} من {user_id}")
    
    # ========== احصائيات البوت ==========
    if data == "admin_stats":
        stats = db.get_bot_stats()
        
        text = (
            "📊 **احصائيات البوت**\n\n"
            f"👥 **المستخدمين:**\n"
            f"   • اجمالي: {stats['total_users']}\n"
            f"   • نشط اليوم: {stats['active_today']}\n"
            f"   • محظورين: {stats['banned_count']}\n\n"
            f"💰 **النقاط:**\n"
            f"   • اجمالي النقاط: {stats['total_points']}\n"
            f"   • اجمالي المنفق: {stats['total_spent']}\n\n"
            f"🚀 **التمويل:**\n"
            f"   • اجمالي: {stats['total_financing']}\n"
            f"   • اليوم: {stats['financing_today']}\n"
            f"   • قيد التنفيذ: {stats['pending_financing']}\n"
            f"   • مكتمل: {stats['completed_financing']}\n\n"
            f"📞 **الارقام:**\n"
            f"   • متاح: {stats['numbers']['available']}\n"
            f"   • مستخدم: {stats['numbers']['used']}\n"
            f"   • ملفات: {stats['numbers']['files']}\n\n"
            f"📢 **قنوات اجبارية:** {stats['mandatory_channels']}\n"
            f"👥 **دعوات:** {stats['total_referrals']}"
        )
        
        await helpers.safe_edit_message(
            query,
            text,
            reply_markup=Keyboards.admin_panel(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== اضافة ملف ارقام ==========
    elif data == "admin_add_numbers":
        await helpers.safe_edit_message(
            query,
            "📁 **اضافة ملف ارقام**\n\n"
            "📤 ارسل ملف txt يحتوي على ارقام تليجرام\n"
            "كل رقم في سطر منفصل\n"
            "الارقام يجب ان تبدأ بـ 00963 او +963\n\n"
            "✅ مثال:\n"
            "00963123456789\n"
            "+963987654321",
            reply_markup=Keyboards.cancel_button(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data["admin_action"] = "add_numbers"
        return States.ADMIN_ADD_NUMBERS.value
    
    # ========== احصائيات الارقام ==========
    elif data == "admin_numbers_stats":
        stats = db.get_numbers_stats()
        
        text = (
            "📞 **احصائيات الارقام**\n\n"
            f"✅ **متاح للاستخدام:** {stats['available']}\n"
            f"📌 **مستخدم:** {stats['used']}\n"
            f"❌ **غير صالح:** {stats['invalid']}\n"
            f"📁 **عدد الملفات:** {stats['files']}\n"
            f"📊 **اجمالي المضاف:** {stats['total_added']}\n"
            f"📊 **اجمالي المستخدم:** {stats['total_used']}"
        )
        
        await helpers.safe_edit_message(
            query,
            text,
            reply_markup=Keyboards.back_button("back_to_admin"),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== شحن رصيد ==========
    elif data == "admin_add_points":
        await helpers.safe_edit_message(
            query,
            "💰 **شحن رصيد مستخدم**\n\n"
            "ارسل: `ايدي المستخدم المبلغ`\n"
            "مثال: `123456789 100`",
            reply_markup=Keyboards.cancel_button(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data["admin_action"] = "add_points"
        return States.ADMIN_ADD_POINTS.value
    
    # ========== خصم رصيد ==========
    elif data == "admin_deduct_points":
        await helpers.safe_edit_message(
            query,
            "💸 **خصم رصيد مستخدم**\n\n"
            "ارسل: `ايدي المستخدم المبلغ`\n"
            "مثال: `123456789 50`",
            reply_markup=Keyboards.cancel_button(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data["admin_action"] = "deduct_points"
        return States.ADMIN_DEDUCT_POINTS.value
    
    # ========== تغيير حساب الدعم ==========
    elif data == "admin_add_support":
        current = db.settings['support_username']
        await helpers.safe_edit_message(
            query,
            f"👤 **تغيير حساب الدعم**\n\n"
            f"الحالي: @{current}\n\n"
            "ارسل اليوزر الجديد:\n"
            "مثال: `support_new`",
            reply_markup=Keyboards.cancel_button(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data["admin_action"] = "add_support"
        return States.ADMIN_ADD_SUPPORT.value
    
    # ========== تغيير رابط القناة ==========
    elif data == "admin_add_channel":
        current = db.settings['channel_link']
        await helpers.safe_edit_message(
            query,
            f"🔗 **تغيير رابط القناة**\n\n"
            f"الحالي: {current}\n\n"
            "ارسل الرابط الجديد:\n"
            "مثال: `https://t.me/new_channel`",
            reply_markup=Keyboards.cancel_button(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data["admin_action"] = "add_channel"
        return States.ADMIN_ADD_CHANNEL.value
    
    # ========== حظر مستخدم ==========
    elif data == "admin_ban":
        await helpers.safe_edit_message(
            query,
            "🚫 **حظر مستخدم**\n\n"
            "ارسل ايدي المستخدم المراد حظره\n"
            "مثال: `123456789`\n"
            "او: `123456789 سبب الحظر`",
            reply_markup=Keyboards.cancel_button(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data["admin_action"] = "ban"
        return States.ADMIN_BAN_USER.value
    
    # ========== رفع حظر ==========
    elif data == "admin_unban":
        await helpers.safe_edit_message(
            query,
            "✅ **رفع حظر عن مستخدم**\n\n"
            "ارسل ايدي المستخدم\n"
            "مثال: `123456789`",
            reply_markup=Keyboards.cancel_button(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data["admin_action"] = "unban"
        return States.ADMIN_UNBAN_USER.value
    
    # ========== تغيير مكافأة الدعوة ==========
    elif data == "admin_change_reward":
        current = db.settings['invite_reward']
        await helpers.safe_edit_message(
            query,
            f"🎁 **تغيير مكافأة الدعوة**\n\n"
            f"الحالية: {current} نقطة\n\n"
            "ارسل القيمة الجديدة:\n"
            "مثال: `15`",
            reply_markup=Keyboards.cancel_button(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data["admin_action"] = "change_reward"
        return States.ADMIN_CHANGE_REWARD.value
    
    # ========== تغيير سعر العضو ==========
    elif data == "admin_change_price":
        current = db.settings['member_price']
        await helpers.safe_edit_message(
            query,
            f"💵 **تغيير سعر العضو**\n\n"
            f"الحالي: {current} نقطة\n\n"
            "ارسل السعر الجديد:\n"
            "مثال: `10`",
            reply_markup=Keyboards.cancel_button(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data["admin_action"] = "change_price"
        return States.ADMIN_CHANGE_PRICE.value
    
    # ========== اضافة قناة اجبارية ==========
    elif data == "admin_add_mandatory":
        await helpers.safe_edit_message(
            query,
            "📢 **اضافة قناة اجبارية**\n\n"
            "ارسل: `الاسم | الرابط | ايدي القناة`\n\n"
            "مثال:\n"
            "`قناتي | https://t.me/my_channel | -100123456789`",
            reply_markup=Keyboards.cancel_button(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data["admin_action"] = "add_mandatory"
        return States.ADMIN_ADD_MANDATORY.value
    
    # ========== عرض القنوات الاجبارية ==========
    elif data == "admin_view_mandatory":
        if not db.mandatory:
            text = "📢 **لا يوجد قنوات اجبارية**"
        else:
            text = "📢 **القنوات الاجبارية**\n\n"
            for i, channel in enumerate(db.mandatory, 1):
                text += f"{i}. **{channel['name']}**\n"
                text += f"   • الرابط: {channel['link']}\n"
                text += f"   • الايدي: `{channel['chat_id']}`\n\n"
        
        await helpers.safe_edit_message(
            query,
            text,
            reply_markup=Keyboards.back_button("back_to_admin"),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== تغيير رسالة الترحيب ==========
    elif data == "admin_change_welcome":
        current = db.settings['welcome_message']
        await helpers.safe_edit_message(
            query,
            f"✏️ **تغيير رسالة الترحيب**\n\n"
            f"الحالية:\n{current}\n\n"
            "ارسل الرسالة الجديدة",
            reply_markup=Keyboards.cancel_button(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data["admin_action"] = "change_welcome"
        return States.ADMIN_CHANGE_WELCOME.value
    
    # ========== رسالة جماعية ==========
    elif data == "admin_broadcast":
        await helpers.safe_edit_message(
            query,
            "📨 **ارسال رسالة جماعية**\n\n"
            "ارسل الرسالة التي تريد ارسالها لجميع المستخدمين",
            reply_markup=Keyboards.cancel_button(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data["admin_action"] = "broadcast"
        return States.ADMIN_BROADCAST.value
    
    # ========== رجوع للوحة التحكم ==========
    elif data == "back_to_admin":
        await helpers.safe_edit_message(
            query,
            "⚙️ **لوحة تحكم المدير**",
            reply_markup=Keyboards.admin_panel(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    await db.save_all()
    return States.MAIN_MENU.value

# ==================== معالج نصوص المدير ====================

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج النصوص للمديرين"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if text.lower() in ["الغاء", "cancel"]:
        await update.message.reply_text(
            "✅ تم الغاء العملية",
            reply_markup=Keyboards.admin_panel()
        )
        context.user_data.clear()
        return States.MAIN_MENU.value
    
    admin_action = context.user_data.get("admin_action")
    
    # ========== شحن رصيد ==========
    if admin_action == "add_points":
        try:
            parts = text.split()
            if len(parts) != 2:
                await update.message.reply_text("❌ استخدم: ايدي المستخدم المبلغ")
                return States.ADMIN_ADD_POINTS.value
            
            target_id = int(parts[0])
            points = int(parts[1])
            
            if points <= 0:
                await update.message.reply_text("❌ المبلغ يجب ان يكون اكبر من 0")
                return States.ADMIN_ADD_POINTS.value
            
            db.add_points(target_id, points)
            await db.save_all()
            
            await update.message.reply_text(f"✅ تم اضافة {points} نقطة للمستخدم {target_id}")
            
            await helpers.safe_send_message(
                context.bot,
                target_id,
                f"💰 تم شحن رصيدك ب {points} نقطة"
            )
            
        except ValueError:
            await update.message.reply_text("❌ ارقام غير صحيحة")
            return States.ADMIN_ADD_POINTS.value
    
    # ========== خصم رصيد ==========
    elif admin_action == "deduct_points":
        try:
            parts = text.split()
            if len(parts) != 2:
                await update.message.reply_text("❌ استخدم: ايدي المستخدم المبلغ")
                return States.ADMIN_DEDUCT_POINTS.value
            
            target_id = int(parts[0])
            points = int(parts[1])
            
            if points <= 0:
                await update.message.reply_text("❌ المبلغ يجب ان يكون اكبر من 0")
                return States.ADMIN_DEDUCT_POINTS.value
            
            if db.deduct_points(target_id, points):
                await db.save_all()
                await update.message.reply_text(f"✅ تم خصم {points} نقطة من المستخدم {target_id}")
                
                await helpers.safe_send_message(
                    context.bot,
                    target_id,
                    f"💸 تم خصم {points} نقطة من رصيدك"
                )
            else:
                await update.message.reply_text("❌ رصيد المستخدم غير كافي")
            
        except ValueError:
            await update.message.reply_text("❌ ارقام غير صحيحة")
            return States.ADMIN_DEDUCT_POINTS.value
    
    # ========== اضافة حساب دعم ==========
    elif admin_action == "add_support":
        username = text.replace('@', '').strip()
        db.settings["support_username"] = username
        await db.save_all()
        await update.message.reply_text(f"✅ تم تعيين حساب الدعم: @{username}")
    
    # ========== اضافة رابط قناة ==========
    elif admin_action == "add_channel":
        if helpers.is_valid_link(text):
            db.settings["channel_link"] = text
            await db.save_all()
            await update.message.reply_text(f"✅ تم تعيين رابط القناة: {text}")
        else:
            await update.message.reply_text("❌ رابط غير صالح")
            return States.ADMIN_ADD_CHANNEL.value
    
    # ========== حظر مستخدم ==========
    elif admin_action == "ban":
        try:
            parts = text.split(maxsplit=1)
            target_id = int(parts[0])
            reason = parts[1] if len(parts) > 1 else "بدون سبب"
            
            if target_id in ADMIN_IDS:
                await update.message.reply_text("❌ لا يمكن حظر مدير")
                return States.ADMIN_BAN_USER.value
            
            if db.ban_user(target_id, reason):
                await db.save_all()
                await update.message.reply_text(f"✅ تم حظر المستخدم {target_id}")
                
                await helpers.safe_send_message(
                    context.bot,
                    target_id,
                    f"⛔️ تم حظرك من البوت\nالسبب: {reason}"
                )
            else:
                await update.message.reply_text("❌ المستخدم محظور بالفعل")
            
        except ValueError:
            await update.message.reply_text("❌ ايدي غير صحيح")
            return States.ADMIN_BAN_USER.value
    
    # ========== رفع حظر ==========
    elif admin_action == "unban":
        try:
            target_id = int(text)
            
            if db.unban_user(target_id):
                await db.save_all()
                await update.message.reply_text(f"✅ تم رفع الحظر عن المستخدم {target_id}")
                
                await helpers.safe_send_message(
                    context.bot,
                    target_id,
                    "✅ تم رفع الحظر عنك، يمكنك استخدام البوت مرة اخرى"
                )
            else:
                await update.message.reply_text("❌ المستخدم غير موجود في قائمة المحظورين")
            
        except ValueError:
            await update.message.reply_text("❌ ايدي غير صحيح")
            return States.ADMIN_UNBAN_USER.value
    
    # ========== تغيير مكافأة الدعوة ==========
    elif admin_action == "change_reward":
        try:
            reward = int(text)
            if reward <= 0:
                await update.message.reply_text("❌ المكافأة يجب ان تكون اكبر من 0")
                return States.ADMIN_CHANGE_REWARD.value
            
            db.settings["invite_reward"] = reward
            await db.save_all()
            await update.message.reply_text(f"✅ تم تغيير مكافأة الدعوة الى {reward} نقطة")
            
        except ValueError:
            await update.message.reply_text("❌ رقم غير صحيح")
            return States.ADMIN_CHANGE_REWARD.value
    
    # ========== تغيير سعر العضو ==========
    elif admin_action == "change_price":
        try:
            price = int(text)
            if price <= 0:
                await update.message.reply_text("❌ السعر يجب ان يكون اكبر من 0")
                return States.ADMIN_CHANGE_PRICE.value
            
            db.settings["member_price"] = price
            await db.save_all()
            await update.message.reply_text(f"✅ تم تغيير سعر العضو الى {price} نقطة")
            
        except ValueError:
            await update.message.reply_text("❌ رقم غير صحيح")
            return States.ADMIN_CHANGE_PRICE.value
    
    # ========== اضافة قناة اجبارية ==========
    elif admin_action == "add_mandatory":
        try:
            parts = [p.strip() for p in text.split('|')]
            if len(parts) != 3:
                await update.message.reply_text("❌ استخدم: الاسم | الرابط | الايدي")
                return States.ADMIN_ADD_MANDATORY.value
            
            name, link, chat_id = parts
            
            if not helpers.is_valid_link(link):
                await update.message.reply_text("❌ رابط غير صالح")
                return States.ADMIN_ADD_MANDATORY.value
            
            db.add_mandatory_channel(name, link, chat_id)
            await db.save_all()
            
            await update.message.reply_text(f"✅ تم اضافة القناة: {name}")
            
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {str(e)}")
            return States.ADMIN_ADD_MANDATORY.value
    
    # ========== تغيير رسالة الترحيب ==========
    elif admin_action == "change_welcome":
        db.settings["welcome_message"] = text
        await db.save_all()
        await update.message.reply_text("✅ تم تغيير رسالة الترحيب")
    
    # ========== رسالة جماعية ==========
    elif admin_action == "broadcast":
        await update.message.reply_text("🔄 جاري ارسال الرسالة...")
        
        success = 0
        failed = 0
        
        for uid in db.users.keys():
            try:
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=text,
                    parse_mode=ParseMode.MARKDOWN
                )
                success += 1
                await asyncio.sleep(0.05)
            except:
                failed += 1
        
        await update.message.reply_text(
            f"📨 **نتيجة الارسال**\n\n"
            f"✅ نجح: {success}\n"
            f"❌ فشل: {failed}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    await update.message.reply_text(
        "⚙️ لوحة تحكم المدير",
        reply_markup=Keyboards.admin_panel()
    )
    
    context.user_data.clear()
    return States.MAIN_MENU.value

# ==================== معالج الملفات ====================

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج استلام الملفات"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ هذه الخاصية للمدراء فقط")
        return States.MAIN_MENU.value
    
    admin_action = context.user_data.get("admin_action")
    
    if admin_action != "add_numbers":
        await update.message.reply_text("❌ انت غير في وضع اضافة ملفات")
        return States.MAIN_MENU.value
    
    document = update.message.document
    
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ فقط ملفات txt مسموحة")
        return States.ADMIN_ADD_NUMBERS.value
    
    wait_msg = await update.message.reply_text("🔄 جاري معالجة الملف...")
    
    try:
        file = await context.bot.get_file(document.file_id)
        file_content = await file.download_as_bytearray()
        
        content = file_content.decode('utf-8')
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        if not lines:
            await wait_msg.edit_text("❌ الملف فارغ")
            return States.ADMIN_ADD_NUMBERS.value
        
        file_info = db.add_numbers_file(document.file_name, lines)
        await db.save_all()
        
        text = (
            f"✅ **تم رفع الملف بنجاح**\n\n"
            f"📁 الملف: {document.file_name}\n"
            f"✅ الصالح: {file_info['valid']}\n"
            f"❌ غير الصالح: {file_info['invalid']}\n"
            f"📞 المتاح الآن: {len(db.numbers['numbers'])}"
        )
        
        await wait_msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        await wait_msg.edit_text(f"❌ خطأ: {str(e)}")
    
    await update.message.reply_text(
        "⚙️ لوحة تحكم المدير",
        reply_markup=Keyboards.admin_panel()
    )
    
    context.user_data.clear()
    return States.MAIN_MENU.value

# ==================== معالج النصوص العام ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج النصوص العام"""
    user_id = update.effective_user.id
    
    if db.is_banned(user_id):
        await update.message.reply_text("⛔️ أنت محظور من استخدام البوت")
        return States.MAIN_MENU.value
    
    current_state = context.user_data.get("state", States.MAIN_MENU.value)
    
    if current_state == States.WAITING_FOR_MEMBERS_COUNT.value:
        return await handle_members_count(update, context)
    
    elif current_state == States.WAITING_FOR_CHANNEL_LINK.value:
        return await handle_channel_link(update, context)
    
    if user_id in ADMIN_IDS and current_state in [
        States.ADMIN_ADD_POINTS.value,
        States.ADMIN_DEDUCT_POINTS.value,
        States.ADMIN_ADD_SUPPORT.value,
        States.ADMIN_ADD_CHANNEL.value,
        States.ADMIN_BAN_USER.value,
        States.ADMIN_UNBAN_USER.value,
        States.ADMIN_CHANGE_REWARD.value,
        States.ADMIN_CHANGE_PRICE.value,
        States.ADMIN_ADD_MANDATORY.value,
        States.ADMIN_CHANGE_WELCOME.value,
        States.ADMIN_BROADCAST.value
    ]:
        return await handle_admin_text(update, context)
    
    await update.message.reply_text(
        "❌ امر غير معروف\n"
        "استخدم /start للعودة للقائمة الرئيسية"
    )
    
    return States.MAIN_MENU.value

# ==================== معالج الاخطاء ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج الاخطاء"""
    try:
        error = context.error
        tb = traceback.format_exc()
        
        logger.error(f"❌ خطأ: {error}\n{tb}")
        
        error_log = LOGS_DIR / f"error_{datetime.now().strftime('%Y%m%d')}.log"
        async with aiofiles.open(error_log, 'a', encoding='utf-8') as f:
            await f.write(f"{datetime.now().isoformat()}\n")
            await f.write(f"Error: {error}\n")
            await f.write(f"Traceback: {tb}\n")
            await f.write("-" * 50 + "\n")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ حدث خطأ غير متوقع، تم ابلاغ المطورين"
            )
            
    except Exception as e:
        logger.critical(f"خطأ في معالج الاخطاء: {e}")

# ==================== اعداد اوامر البوت ====================

async def post_init(application: Application) -> None:
    """بعد تهيئة البوت"""
    commands = [
        BotCommand("start", "بدء استخدام البوت"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("✅ تم اعداد اوامر البوت")

# ==================== الدالة الرئيسية ====================

def main() -> None:
    """الدالة الرئيسية"""
    
    print(f"{Fore.CYAN}{'='*60}{Fore.RESET}")
    print(f"{Fore.GREEN}🤖 بوت التمويل المتكامل v3.0{Fore.RESET}")
    print(f"{Fore.YELLOW}👤 المطور: System{Fore.RESET}")
    print(f"{Fore.CYAN}{'='*60}{Fore.RESET}")
    
    application = Application.builder()\
        .token(BOT_TOKEN)\
        .concurrent_updates(True)\
        .post_init(post_init)\
        .build()
    
    # معالج المحادثة
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            States.MAIN_MENU.value: [
                CallbackQueryHandler(check_subscription_callback, pattern="^check_subscription$"),
                CallbackQueryHandler(user_buttons_callback),
                CallbackQueryHandler(admin_buttons_callback, pattern="^admin_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                MessageHandler(filters.Document.ALL, handle_document),
            ],
            States.WAITING_FOR_MEMBERS_COUNT.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(user_buttons_callback),
            ],
            States.WAITING_FOR_CHANNEL_LINK.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(user_buttons_callback),
            ],
            States.ADMIN_ADD_POINTS.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(admin_buttons_callback),
            ],
            States.ADMIN_DEDUCT_POINTS.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(admin_buttons_callback),
            ],
            States.ADMIN_ADD_NUMBERS.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                MessageHandler(filters.Document.ALL, handle_document),
                CallbackQueryHandler(admin_buttons_callback),
            ],
            States.ADMIN_ADD_SUPPORT.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(admin_buttons_callback),
            ],
            States.ADMIN_ADD_CHANNEL.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(admin_buttons_callback),
            ],
            States.ADMIN_BAN_USER.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(admin_buttons_callback),
            ],
            States.ADMIN_UNBAN_USER.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(admin_buttons_callback),
            ],
            States.ADMIN_CHANGE_REWARD.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(admin_buttons_callback),
            ],
            States.ADMIN_CHANGE_PRICE.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(admin_buttons_callback),
            ],
            States.ADMIN_ADD_MANDATORY.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(admin_buttons_callback),
            ],
            States.ADMIN_CHANGE_WELCOME.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(admin_buttons_callback),
            ],
            States.ADMIN_BROADCAST.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(admin_buttons_callback),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
        per_message=False,
    )
    
    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)
    
    print(f"{Fore.GREEN}✅ البوت يعمل بنجاح...{Fore.RESET}")
    print(f"{Fore.YELLOW}📝 سجل الأحداث في bot.log{Fore.RESET}")
    print(f"{Fore.CYAN}{'='*60}{Fore.RESET}")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}👋 تم ايقاف البوت{Fore.RESET}")
    except Exception as e:
        print(f"{Fore.RED}❌ خطأ فادح: {e}{Fore.RESET}")
        traceback.print_exc()

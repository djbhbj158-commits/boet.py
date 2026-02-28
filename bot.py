#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
بوت تمويل متكامل لتليجرام - النسخة الكاملة
الإصدار: 2.0
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

import aiofiles
from colorama import init, Fore, Style
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
    PicklePersistence
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
    ADMIN_DELETE_NUMBERS = 103
    ADMIN_ADD_SUPPORT = 104
    ADMIN_ADD_CHANNEL = 105
    ADMIN_BAN_USER = 106
    ADMIN_UNBAN_USER = 107
    ADMIN_CHANGE_REWARD = 108
    ADMIN_CHANGE_PRICE = 109
    ADMIN_ADD_MANDATORY = 110
    ADMIN_DELETE_MANDATORY = 111
    ADMIN_CHANGE_WELCOME = 112
    ADMIN_BROADCAST = 113
    ADMIN_BACKUP = 114
    ADMIN_RESTORE = 115
    ADMIN_VIEW_FILES = 116
    ADMIN_FINANCING_CONTROL = 117

# ==================== قاعدة البيانات ====================

class Database:
    """قاعدة بيانات البوت - متطورة مع دعم كامل"""
    
    def __init__(self):
        self.data_dir = DATA_DIR
        
        # ملفات البيانات
        self.users_file = self.data_dir / "users.json"
        self.channels_file = self.data_dir / "channels.json"
        self.numbers_file = self.data_dir / "numbers.json"
        self.settings_file = self.data_dir / "settings.json"
        self.financing_file = self.data_dir / "financing.json"
        self.banned_file = self.data_dir / "banned.json"
        self.mandatory_file = self.data_dir / "mandatory.json"
        self.referrals_file = self.data_dir / "referrals.json"
        self.stats_file = self.data_dir / "stats.json"
        self.logs_file = self.data_dir / "logs.json"
        self.backup_file = self.data_dir / "backup.json"
        
        # تحميل البيانات
        self.users = self._load_json(self.users_file, {})
        self.channels = self._load_json(self.channels_file, {})
        self.numbers = self._load_json(self.numbers_file, self._default_numbers())
        self.settings = self._load_json(self.settings_file, self._default_settings())
        self.financing = self._load_json(self.financing_file, {})
        self.banned = self._load_json(self.banned_file, {})
        self.mandatory = self._load_json(self.mandatory_file, [])
        self.referrals = self._load_json(self.referrals_file, {})
        self.stats = self._load_json(self.stats_file, self._default_stats())
        self.logs = self._load_json(self.logs_file, [])
        
        # قفل للكتابة المتزامنة
        self._lock = asyncio.Lock()
        
        logger.info(f"{Fore.GREEN}✅ تم تحميل قاعدة البيانات بنجاح{Fore.RESET}")
    
    def _default_settings(self):
        """الإعدادات الافتراضية"""
        return {
            "invite_reward": 10,
            "member_price": 8,
            "welcome_message": "👋 مرحباً بك في بوت التمويل المتكامل\n\n📍 يمكنك تجميع النقاط وتمويل قنواتك بكل سهولة",
            "support_username": "support",
            "channel_link": "https://t.me/your_channel",
            "min_financing": 10,
            "max_financing": 1000,
            "daily_bonus": 5,
            "referral_bonus": 5,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "bot_status": "active",
            "maintenance_mode": False,
            "version": "2.0"
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
            "daily_users": [],
            "daily_financing": [],
            "commands_count": {},
            "bot_start_time": datetime.now().isoformat(),
            "last_backup": None
        }
    
    def _load_json(self, file_path: Path, default: Any) -> Any:
        """تحميل ملف JSON"""
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"📂 تم تحميل {file_path.name}")
                    return data
        except Exception as e:
            logger.error(f"❌ خطأ في تحميل {file_path.name}: {e}")
        return default
    
    async def _save_json(self, file_path: Path, data: Any) -> bool:
        """حفظ ملف JSON مع قفل"""
        async with self._lock:
            try:
                # إنشاء نسخة احتياطية قبل الحفظ
                if file_path.exists():
                    backup_path = file_path.with_suffix('.bak')
                    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                        content = await f.read()
                    async with aiofiles.open(backup_path, 'w', encoding='utf-8') as f:
                        await f.write(content)
                
                # حفظ البيانات الجديدة
                async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(data, ensure_ascii=False, indent=2))
                
                logger.info(f"💾 تم حفظ {file_path.name}")
                return True
            except Exception as e:
                logger.error(f"❌ خطأ في حفظ {file_path.name}: {e}")
                return False
    
    async def save_all(self) -> bool:
        """حفظ جميع البيانات"""
        tasks = [
            self._save_json(self.users_file, self.users),
            self._save_json(self.channels_file, self.channels),
            self._save_json(self.numbers_file, self.numbers),
            self._save_json(self.settings_file, self.settings),
            self._save_json(self.financing_file, self.financing),
            self._save_json(self.banned_file, self.banned),
            self._save_json(self.mandatory_file, self.mandatory),
            self._save_json(self.referrals_file, self.referrals),
            self._save_json(self.stats_file, self.stats),
            self._save_json(self.logs_file, self.logs)
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
                "referrals_list": [],
                "financing_count": 0,
                "total_spent": 0,
                "total_earned": 0,
                "joined_date": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "last_daily": None,
                "warn_count": 0,
                "is_banned": False,
                "ban_reason": None,
                "notes": "",
                "language": "ar",
                "username": None,
                "first_name": None,
                "last_name": None
            }
            
            # تحديث الإحصائيات
            self.stats["total_users"] = len(self.users)
        
        # تحديث آخر نشاط
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
    
    def add_points(self, user_id: int, points: int, reason: str = "") -> bool:
        """إضافة نقاط لمستخدم"""
        user_id = str(user_id)
        user = self.get_user(user_id)
        user["points"] += points
        user["total_earned"] += points
        
        # تسجيل العملية
        self._add_log({
            "type": "add_points",
            "user_id": user_id,
            "points": points,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        
        return True
    
    def deduct_points(self, user_id: int, points: int, reason: str = "") -> bool:
        """خصم نقاط من مستخدم"""
        user_id = str(user_id)
        user = self.get_user(user_id)
        if user["points"] >= points:
            user["points"] -= points
            
            # تسجيل العملية
            self._add_log({
                "type": "deduct_points",
                "user_id": user_id,
                "points": points,
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            })
            
            return True
        return False
    
    def _add_log(self, log_entry: Dict):
        """إضافة سجل جديد"""
        self.logs.append(log_entry)
        # الاحتفاظ بآخر 1000 سجل فقط
        if len(self.logs) > 1000:
            self.logs = self.logs[-1000:]
    
    # ========== إدارة الدعوات ==========
    
    def process_referral(self, referrer_id: int, new_user_id: int) -> bool:
        """معالجة دعوة جديدة"""
        referrer_id = str(referrer_id)
        new_user_id = str(new_user_id)
        
        # منع الدعوة الذاتية
        if referrer_id == new_user_id:
            return False
        
        # التحقق من عدم تكرار الدعوة
        if referrer_id not in self.referrals:
            self.referrals[referrer_id] = []
        
        if new_user_id in self.referrals[referrer_id]:
            return False
        
        # إضافة الدعوة
        self.referrals[referrer_id].append(new_user_id)
        
        # إضافة نقاط للداعي
        reward = self.settings["invite_reward"]
        self.add_points(int(referrer_id), reward, "مكافأة دعوة")
        
        # تحديث إحصائيات الداعي
        referrer = self.get_user(int(referrer_id))
        referrer["referrals"] += 1
        if "referrals_list" not in referrer:
            referrer["referrals_list"] = []
        referrer["referrals_list"].append({
            "user_id": new_user_id,
            "date": datetime.now().isoformat(),
            "reward": reward
        })
        
        # تحديث الإحصائيات العامة
        self.stats["total_referrals"] += 1
        
        return True
    
    def get_referral_link(self, user_id: int, bot_username: str) -> str:
        """الحصول على رابط الدعوة"""
        user = self.get_user(user_id)
        return f"https://t.me/{bot_username}?start={user['referral_code']}"
    
    # ========== إدارة الأرقام ==========
    
    def add_numbers_file(self, filename: str, numbers: List[str]) -> Dict:
        """إضافة ملف أرقام جديد"""
        # تنظيف الأرقام والتحقق منها
        valid_numbers = []
        invalid_numbers = []
        
        for num in numbers:
            num = num.strip()
            if not num:
                continue
            
            # تنظيف الرقم
            cleaned = re.sub(r'[^0-9+]', '', num)
            
            # التحقق من صحة الرقم (يبدأ بـ 00963 أو +963 أو 963)
            if re.match(r'^(00963|\+963|963)\d{8,9}$', cleaned):
                # توحيد التنسيق
                if cleaned.startswith('00963'):
                    cleaned = '+' + cleaned[1:]
                elif cleaned.startswith('963') and not cleaned.startswith('+'):
                    cleaned = '+' + cleaned
                valid_numbers.append(cleaned)
            else:
                invalid_numbers.append(num)
        
        # إضافة الأرقام الصالحة
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
        numbers_copy = self.numbers["numbers"].copy()
        
        for i in range(min(count, len(numbers_copy))):
            num = numbers_copy.pop(0)
            available.append(num)
            self.numbers["used_numbers"].append({
                "number": num,
                "used_at": datetime.now().isoformat()
            })
        
        self.numbers["numbers"] = numbers_copy
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
    
    def delete_file(self, filename: str) -> bool:
        """حذف ملف أرقام"""
        for i, file_info in enumerate(self.numbers["files"]):
            if file_info["name"] == filename:
                self.numbers["files"].pop(i)
                return True
        return False
    
    # ========== إدارة التمويل ==========
    
    def create_financing(self, user_id: int, channel_link: str, 
                        members_count: int, cost: int) -> str:
        """إنشاء عملية تمويل جديدة"""
        finance_id = self._generate_code(12)
        user_id = str(user_id)
        
        self.financing[finance_id] = {
            "id": finance_id,
            "user_id": user_id,
            "channel_link": channel_link,
            "channel_id": self._extract_channel_id(channel_link),
            "total_members": members_count,
            "added_members": 0,
            "status": "pending",  # pending, processing, completed, failed
            "cost": cost,
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "last_update": datetime.now().isoformat(),
            "used_numbers": [],
            "failed_numbers": [],
            "notes": ""
        }
        
        # تحديث إحصائيات المستخدم
        user = self.get_user(int(user_id))
        user["financing_count"] += 1
        user["total_spent"] += cost
        
        # تحديث الإحصائيات العامة
        self.stats["total_financing"] += 1
        self.stats["total_spent"] += cost
        
        return finance_id
    
    def _extract_channel_id(self, link: str) -> str:
        """استخراج معرف القناة من الرابط"""
        # محاولة استخراج المعرف من الرابط
        match = re.search(r'(?:t\.me/|telegram\.me/)([a-zA-Z0-9_]+)', link)
        if match:
            return match.group(1)
        return link
    
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
        
        # إضافة العضو
        finance["added_members"] += 1
        if "used_numbers" not in finance:
            finance["used_numbers"] = []
        
        finance["used_numbers"].append({
            "number": number,
            "added_at": datetime.now().isoformat()
        })
        
        # التحقق من اكتمال التمويل
        if finance["added_members"] >= finance["total_members"]:
            finance["status"] = "completed"
            finance["completed_at"] = datetime.now().isoformat()
        
        return {
            "success": True,
            "finance": finance,
            "completed": finance["added_members"] >= finance["total_members"],
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
    
    def get_active_financing(self) -> List[Dict]:
        """الحصول على التمويلات النشطة"""
        return [
            {**finance, "id": fid}
            for fid, finance in self.financing.items()
            if finance["status"] in ["pending", "processing"]
        ]
    
    # ========== إدارة الحظر ==========
    
    def ban_user(self, user_id: int, reason: str = "", admin_id: int = None) -> bool:
        """حظر مستخدم"""
        user_id = str(user_id)
        
        # منع حظر المديرين
        if int(user_id) in ADMIN_IDS:
            return False
        
        self.banned[user_id] = {
            "user_id": user_id,
            "reason": reason,
            "banned_by": str(admin_id) if admin_id else "system",
            "banned_at": datetime.now().isoformat(),
            "expires": None  # يمكن تحديد تاريخ انتهاء
        }
        
        # تحديث حالة المستخدم
        if user_id in self.users:
            self.users[user_id]["is_banned"] = True
            self.users[user_id]["ban_reason"] = reason
        
        return True
    
    def unban_user(self, user_id: int) -> bool:
        """رفع الحظر عن مستخدم"""
        user_id = str(user_id)
        if user_id in self.banned:
            del self.banned[user_id]
            
            if user_id in self.users:
                self.users[user_id]["is_banned"] = False
                self.users[user_id]["ban_reason"] = None
            
            return True
        return False
    
    def is_banned(self, user_id: int) -> bool:
        """التحقق من حظر المستخدم"""
        user_id = str(user_id)
        return user_id in self.banned
    
    # ========== إدارة القنوات الإجبارية ==========
    
    def add_mandatory_channel(self, name: str, link: str, chat_id: str) -> Dict:
        """إضافة قناة إجبارية"""
        channel = {
            "name": name,
            "link": link,
            "chat_id": chat_id,
            "added_at": datetime.now().isoformat(),
            "is_active": True,
            "check_count": 0,
            "joined_count": 0
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
                # محاولة تحويل إلى رقم إذا كان معرف رقمي
                if str(chat_id).lstrip('-').isdigit():
                    chat_id = int(chat_id)
                
                member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                
                # تحديث إحصائيات القناة
                channel["check_count"] = channel.get("check_count", 0) + 1
                
                if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
                    not_joined.append(channel)
                else:
                    channel["joined_count"] = channel.get("joined_count", 0) + 1
                    
            except Exception as e:
                logger.warning(f"خطأ في التحقق من القناة {channel['name']}: {e}")
                not_joined.append(channel)
        
        return len(not_joined) == 0, not_joined
    
    # ========== الإحصائيات ==========
    
    def get_bot_stats(self) -> Dict:
        """إحصائيات البوت الكاملة"""
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        
        # تحديث الإحصائيات اليومية
        self.stats["daily_users"] = self.stats.get("daily_users", [])
        self.stats["daily_financing"] = self.stats.get("daily_financing", [])
        
        # حساب المستخدمين النشطين اليوم
        active_today = 0
        for user_data in self.users.values():
            last_active = user_data.get("last_active", "")
            if last_active and last_active.startswith(today):
                active_today += 1
        
        # حساب إجمالي النقاط
        total_points = sum(u.get("points", 0) for u in self.users.values())
        
        # حساب التمويلات اليوم
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
            "pending_financing": sum(1 for f in self.financing.values() if f["status"] in ["pending", "processing"]),
            "total_spent": self.stats["total_spent"],
            "total_referrals": self.stats["total_referrals"],
            "banned_count": len(self.banned),
            "numbers": numbers_stats,
            "mandatory_channels": len(self.mandatory),
            "bot_uptime": self._get_uptime(),
            "last_backup": self.stats.get("last_backup"),
            "version": self.settings["version"]
        }
    
    def _get_uptime(self) -> str:
        """مدة تشغيل البوت"""
        start_time = datetime.fromisoformat(self.stats["bot_start_time"])
        uptime = datetime.now() - start_time
        
        days = uptime.days
        hours = uptime.seconds // 3600
        minutes = (uptime.seconds % 3600) // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days} يوم")
        if hours > 0:
            parts.append(f"{hours} ساعة")
        if minutes > 0:
            parts.append(f"{minutes} دقيقة")
        
        return " ".join(parts) if parts else "أقل من دقيقة"
    
    def update_stats(self, command: str = None):
        """تحديث الإحصائيات"""
        if command:
            if "commands_count" not in self.stats:
                self.stats["commands_count"] = {}
            self.stats["commands_count"][command] = self.stats["commands_count"].get(command, 0) + 1
    
    # ========== النسخ الاحتياطي ==========
    
    async def create_backup(self) -> Optional[Path]:
        """إنشاء نسخة احتياطية"""
        try:
            backup_data = {
                "users": self.users,
                "channels": self.channels,
                "numbers": self.numbers,
                "settings": self.settings,
                "financing": self.financing,
                "banned": self.banned,
                "mandatory": self.mandatory,
                "referrals": self.referrals,
                "stats": self.stats,
                "backup_date": datetime.now().isoformat(),
                "version": self.settings["version"]
            }
            
            backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            backup_path = DATA_DIR / backup_filename
            
            await self._save_json(backup_path, backup_data)
            
            self.stats["last_backup"] = datetime.now().isoformat()
            
            return backup_path
            
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء النسخة الاحتياطية: {e}")
            return None
    
    async def restore_backup(self, backup_path: Path) -> bool:
        """استعادة نسخة احتياطية"""
        try:
            async with aiofiles.open(backup_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                backup_data = json.loads(content)
            
            self.users = backup_data.get("users", {})
            self.channels = backup_data.get("channels", {})
            self.numbers = backup_data.get("numbers", self._default_numbers())
            self.settings = backup_data.get("settings", self._default_settings())
            self.financing = backup_data.get("financing", {})
            self.banned = backup_data.get("banned", {})
            self.mandatory = backup_data.get("mandatory", [])
            self.referrals = backup_data.get("referrals", {})
            self.stats = backup_data.get("stats", self._default_stats())
            
            await self.save_all()
            return True
            
        except Exception as e:
            logger.error(f"❌ خطأ في استعادة النسخة الاحتياطية: {e}")
            return False

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
    def format_time(seconds: int) -> str:
        """تنسيق الوقت"""
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        
        parts = []
        if days > 0:
            parts.append(f"{days} يوم")
        if hours > 0:
            parts.append(f"{hours} ساعة")
        if minutes > 0:
            parts.append(f"{minutes} دقيقة")
        if seconds > 0 and not parts:
            parts.append(f"{seconds} ثانية")
        
        return " و ".join(parts) if parts else "0 ثانية"
    
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
    def clean_phone_number(number: str) -> str:
        """تنظيف رقم الهاتف"""
        # إزالة المسافات والرموز غير المرقمة
        cleaned = re.sub(r'[^\d+]', '', number)
        
        # توحيد التنسيق
        if cleaned.startswith('00963'):
            cleaned = '+' + cleaned[2:]
        elif cleaned.startswith('963') and not cleaned.startswith('+'):
            cleaned = '+' + cleaned
        
        return cleaned
    
    @staticmethod
    async def safe_send_message(bot, chat_id: int, text: str, **kwargs) -> bool:
        """إرسال رسالة بأمان مع معالجة الأخطاء"""
        try:
            await bot.send_message(chat_id=chat_id, text=text, **kwargs)
            return True
        except Forbidden:
            logger.warning(f"المستخدم {chat_id} حظر البوت")
        except BadRequest as e:
            logger.warning(f"خطأ في إرسال الرسالة للمستخدم {chat_id}: {e}")
        except RetryAfter as e:
            logger.warning(f"تم تجاوز الحد المسموح، الانتظار {e.retry_after} ثانية")
            await asyncio.sleep(e.retry_after)
            return await Helpers.safe_send_message(bot, chat_id, text, **kwargs)
        except Exception as e:
            logger.error(f"خطأ غير متوقع في إرسال الرسالة: {e}")
        return False

helpers = Helpers()

# ==================== لوحات المفاتيح ====================

class Keyboards:
    """فئة لوحات المفاتيح"""
    
    @staticmethod
    def main_menu(user_id: int) -> InlineKeyboardMarkup:
        """لوحة المفاتيح الرئيسية للمستخدم"""
        user = db.get_user(user_id)
        
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
            [
                InlineKeyboardButton("🔄 تحديث", callback_data="refresh"),
                InlineKeyboardButton("ℹ️ معلومات", callback_data="info")
            ]
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
                InlineKeyboardButton("🗑 حذف ملف ارقام", callback_data="admin_delete_numbers")
            ],
            [
                InlineKeyboardButton("📋 عرض ملفات الارقام", callback_data="admin_view_files"),
                InlineKeyboardButton("📞 احصائيات الارقام", callback_data="admin_numbers_stats")
            ],
            [
                InlineKeyboardButton("👤 اضافة حساب دعم", callback_data="admin_add_support"),
                InlineKeyboardButton("🔗 اضافة رابط قناة", callback_data="admin_add_channel")
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
                InlineKeyboardButton("🗑 حذف قناة اجبارية", callback_data="admin_delete_mandatory")
            ],
            [
                InlineKeyboardButton("📋 عرض القنوات الاجبارية", callback_data="admin_view_mandatory"),
                InlineKeyboardButton("✏️ تغيير رسالة الترحيب", callback_data="admin_change_welcome")
            ],
            [
                InlineKeyboardButton("📨 رسالة جماعية", callback_data="admin_broadcast"),
                InlineKeyboardButton("🔄 التحكم بالتمويل", callback_data="admin_financing_control")
            ],
            [
                InlineKeyboardButton("💾 نسخة احتياطية", callback_data="admin_backup"),
                InlineKeyboardButton("🔄 استعادة نسخة", callback_data="admin_restore")
            ],
            [
                InlineKeyboardButton("📋 سجلات البوت", callback_data="admin_logs"),
                InlineKeyboardButton("⚙️ اعدادات متقدمة", callback_data="admin_settings")
            ],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
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
    
    @staticmethod
    def confirmation_buttons(action: str, item_id: str = None) -> InlineKeyboardMarkup:
        """أزرار تأكيد"""
        callback_data = f"confirm_{action}"
        if item_id:
            callback_data += f"_{item_id}"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ نعم", callback_data=callback_data),
                InlineKeyboardButton("❌ لا", callback_data="cancel")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def financing_control(finance_id: str) -> InlineKeyboardMarkup:
        """التحكم في عملية تمويل"""
        keyboard = [
            [
                InlineKeyboardButton("⏸ ايقاف مؤقت", callback_data=f"finance_pause_{finance_id}"),
                InlineKeyboardButton("▶️ استئناف", callback_data=f"finance_resume_{finance_id}")
            ],
            [
                InlineKeyboardButton("⏹ ايقاف نهائي", callback_data=f"finance_stop_{finance_id}"),
                InlineKeyboardButton("🔄 اعادة المحاولة", callback_data=f"finance_retry_{finance_id}")
            ],
            [InlineKeyboardButton("📊 تحديث", callback_data=f"finance_refresh_{finance_id}")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_financing_control")]
        ]
        return InlineKeyboardMarkup(keyboard)

# ==================== معالج الاشتراك الإجباري ====================

class MandatoryCheck:
    """التحقق من الاشتراك الإجباري"""
    
    @staticmethod
    async def check_and_handle(user_id: int, context: ContextTypes.DEFAULT_TYPE, 
                              update: Update = None) -> bool:
        """التحقق ومعالجة الاشتراك الإجباري"""
        
        # المديرين مستثنون
        if user_id in ADMIN_IDS:
            return True
        
        is_subscribed, not_joined = await db.check_mandatory_subscription(user_id, context.bot)
        
        if not is_subscribed:
            text = "⚠️ **عذراً، يجب الاشتراك في القنوات التالية اولاً**\n\n"
            
            for channel in not_joined:
                text += f"📢 {channel['name']}\n"
                text += f"🔗 [اضغط للاشتراك]({channel['link']})\n\n"
            
            text += "✅ بعد الاشتراك اضغط على زر التحقق"
            
            # إنشاء أزرار القنوات
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
            
            if update:
                if update.callback_query:
                    await update.callback_query.edit_message_text(
                        text,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
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
            "⛔️ **عذراً، أنت محظور من استخدام البوت**\n\n"
            "للتواصل مع الدعم الفني: @support",
            parse_mode=ParseMode.MARKDOWN
        )
        return States.MAIN_MENU.value
    
    # معالجة رمز الدعوة
    args = context.args
    if args and len(args) > 0:
        referral_code = args[0]
        
        # البحث عن المستخدم الداعي
        for uid, u_data in db.users.items():
            if u_data.get("referral_code") == referral_code and str(uid) != str(user_id):
                referrer_id = int(uid)
                
                # معالجة الدعوة
                if db.process_referral(referrer_id, user_id):
                    # إشعار الداعي
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
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # التحقق من الاشتراك الإجباري
    if not await MandatoryCheck.check_and_handle(user_id, context, update):
        return States.MAIN_MENU.value
    
    # رسالة الترحيب
    welcome_text = (
        f"{db.settings['welcome_message']}\n\n"
        f"👤 **مرحباً {helpers.escape_markdown(user.first_name)}**\n"
        f"🆔 **ايديك:** `{user_id}`\n"
        f"⭐️ **نقاطك:** {user_data['points']}\n"
        f"👥 **عدد من دعوتهم:** {user_data['referrals']}\n\n"
        f"📌 استخدم الأزرار أدناه للتنقل"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=Keyboards.main_menu(user_id),
        parse_mode=ParseMode.MARKDOWN
    )
    
    # تحديث الإحصائيات
    db.update_stats("/start")
    await db.save_all()
    
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
        
        # إعادة إنشاء الأزرار
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
    if db.is_banned(user_id):
        await query.edit_message_text("⛔️ أنت محظور من استخدام البوت")
        return States.MAIN_MENU.value
    
    # التحقق من الاشتراك الإجباري (للمستخدمين العاديين)
    if user_id not in ADMIN_IDS and data not in ["check_subscription", "back_to_main"]:
        if not await MandatoryCheck.check_and_handle(user_id, context, update):
            return States.MAIN_MENU.value
    
    # ========== تجميع النقاط ==========
    if data == "collect_points":
        user_data = db.get_user(user_id)
        bot_info = await context.bot.get_me()
        referral_link = db.get_referral_link(user_id, bot_info.username)
        
        text = (
            "💰 **تجميع النقاط**\n\n"
            "📌 شارك الرابط التالي مع اصدقائك\n"
            "عند دخول كل صديق عبر رابطك ستحصل على نقاط\n\n"
            f"🏆 **رصيدك الحالي:** {user_data['points']} نقطة\n"
            f"👥 **عدد الدعوات الناجحة:** {user_data['referrals']}\n"
            f"🎁 **مكافأة كل دعوة:** {db.settings['invite_reward']} نقطة\n\n"
            f"🔗 **رابط الدعوة الخاص بك:**\n"
            f"`{referral_link}`\n\n"
            "✨ كلما زاد عدد الدعوات زاد رصيدك"
        )
        
        # أزرار المشاركة
        share_keyboard = [
            [
                InlineKeyboardButton("📱 مشاركة", switch_inline_query="اشترك في بوت التمويل 🚀"),
                InlineKeyboardButton("📋 نسخ الرابط", callback_data="copy_link")
            ],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
        ]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(share_keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        db.update_stats("collect_points")
    
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
            "📝 **ارسل الآن عدد الاعضاء الذي تريد تمويلهم**\n"
            "مثال: `100`\n\n"
            "⚠️ **ملاحظة مهمة:** يجب ان يكون البوت ادمن في قناتك"
        )
        
        await query.edit_message_text(
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
            for finance in finances[-5:]:  # آخر 5 تمويلات
                status_emoji = {
                    "pending": "⏳",
                    "processing": "🔄",
                    "completed": "✅",
                    "failed": "❌"
                }.get(finance["status"], "⏳")
                
                text += f"{status_emoji} **{finance['id'][:8]}...**\n"
                text += f"   📍 القناة: {finance['channel_link'][:30]}...\n"
                text += f"   👥 التقدم: {finance['added_members']}/{finance['total_members']}\n"
                text += f"   💰 التكلفة: {finance['cost']} نقطة\n"
                text += f"   📅 التاريخ: {finance['created_at'][:10]}\n\n"
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.back_button(),
            parse_mode=ParseMode.MARKDOWN
        )
        db.update_stats("my_financing")
    
    # ========== احصائياتي ==========
    elif data == "my_stats":
        user_data = db.get_user(user_id)
        
        # حساب نسبة النجاح
        success_rate = 0
        if user_data['financing_count'] > 0:
            completed = sum(1 for f in db.financing.values() 
                          if f["user_id"] == str(user_id) and f["status"] == "completed")
            success_rate = (completed / user_data['financing_count']) * 100
        
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
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.back_button(),
            parse_mode=ParseMode.MARKDOWN
        )
        db.update_stats("my_stats")
    
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
        
        # إضافة المكافأة
        bonus = db.settings["daily_bonus"]
        db.add_points(user_id, bonus, "مكافأة يومية")
        db.update_user_info(user_id, last_daily=now.isoformat())
        
        await query.answer(f"✅ تم اضافة {bonus} نقطة كمكافأة يومية", show_alert=True)
        
        # تحديث العرض
        user_data = db.get_user(user_id)
        await query.edit_message_text(
            f"{db.settings['welcome_message']}\n\n"
            f"👤 **مرحباً {query.from_user.first_name}**\n"
            f"🆔 **ايديك:** `{user_id}`\n"
            f"⭐️ **نقاطك:** {user_data['points']}\n"
            f"👥 **عدد من دعوتهم:** {user_data['referrals']}",
            reply_markup=Keyboards.main_menu(user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        
        db.update_stats("daily_bonus")
    
    # ========== دعوة صديق ==========
    elif data == "invite_friend":
        bot_info = await context.bot.get_me()
        user_data = db.get_user(user_id)
        referral_link = db.get_referral_link(user_id, bot_info.username)
        
        text = (
            "👥 **دعوة صديق**\n\n"
            "🎁 شارك الرابط التالي مع اصدقائك\n"
            "ستحصل على مكافأة عند كل صديق ينضم\n\n"
            f"💰 **المكافأة:** {db.settings['invite_reward']} نقطة لكل صديق\n"
            f"🔗 **رابط الدعوة:**\n`{referral_link}`\n\n"
            "📱 اضغط على الزر لمشاركة الرابط"
        )
        
        share_keyboard = [
            [InlineKeyboardButton("📱 مشاركة", switch_inline_query=f"انضم الي في بوت التمويل 🚀\n{referral_link}")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
        ]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(share_keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== معلومات ==========
    elif data == "info":
        stats = db.get_bot_stats()
        
        text = (
            "ℹ️ **معلومات البوت**\n\n"
            f"👥 **عدد المستخدمين:** {stats['total_users']}\n"
            f"⭐️ **اجمالي النقاط:** {stats['total_points']}\n"
            f"🚀 **اجمالي التمويلات:** {stats['total_financing']}\n"
            f"💸 **اجمالي المنفق:** {stats['total_spent']} نقطة\n"
            f"👥 **اجمالي الدعوات:** {stats['total_referrals']}\n"
            f"📞 **الارقام المتاحة:** {stats['numbers']['available']}\n"
            f"⏱ **مدة التشغيل:** {stats['bot_uptime']}\n"
            f"📌 **الاصدار:** {stats['version']}\n\n"
            f"🆘 **للاستفسار:** @{db.settings['support_username']}"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.back_button(),
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
        
        await query.edit_message_text(
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
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.main_menu(user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data.clear()
    
    # ========== لوحة تحكم المدير ==========
    elif data == "admin_panel" and user_id in ADMIN_IDS:
        await query.edit_message_text(
            "⚙️ **لوحة تحكم المدير**\n"
            "اختر العملية التي تريد تنفيذها",
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
        
        await query.edit_message_text(
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
            await update.message.reply_text(
                f"❌ الحد الأدنى للتمويل هو {min_count} عضو\n"
                f"الرجاء ادخال عدد اكبر"
            )
            return States.WAITING_FOR_MEMBERS_COUNT.value
        
        if count > max_count:
            await update.message.reply_text(
                f"❌ الحد الأقصى للتمويل هو {max_count} عضو\n"
                f"الرجاء ادخال عدد اقل"
            )
            return States.WAITING_FOR_MEMBERS_COUNT.value
        
        user_data = db.get_user(user_id)
        member_price = db.settings["member_price"]
        total_cost = count * member_price
        
        if user_data["points"] < total_cost:
            await update.message.reply_text(
                f"❌ **رصيدك غير كافي**\n\n"
                f"💰 المطلوب: {total_cost} نقطة\n"
                f"⭐️ رصيدك: {user_data['points']} نقطة\n"
                f"📊 العجز: {total_cost - user_data['points']} نقطة\n\n"
                "يمكنك تجميع المزيد من النقاط عبر:\n"
                "• دعوة اصدقاء\n"
                "• المكافأة اليومية",
                parse_mode=ParseMode.MARKDOWN
            )
            context.user_data.clear()
            return States.MAIN_MENU.value
        
        # حفظ البيانات مؤقتاً
        context.user_data["finance"] = {
            "count": count,
            "cost": total_cost
        }
        
        await update.message.reply_text(
            f"✅ **تم حساب التكلفة**\n\n"
            f"👥 عدد الاعضاء: {count}\n"
            f"💰 التكلفة الاجمالية: {total_cost} نقطة\n"
            f"⭐️ رصيدك المتبقي: {user_data['points'] - total_cost} نقطة\n\n"
            "📤 **الآن ارسل رابط قناتك**\n"
            "⚠️ تأكد ان البوت ادمن في القناة\n\n"
            "مثال:\n"
            "`https://t.me/your_channel`\n"
            "او `@your_channel`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=Keyboards.cancel_button()
        )
        
        return States.WAITING_FOR_CHANNEL_LINK.value
        
    except ValueError:
        await update.message.reply_text(
            "❌ الرجاء ادخال رقم صحيح\n"
            "مثال: 100"
        )
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
    
    # التحقق من صحة الرابط
    if not helpers.is_valid_link(link):
        await update.message.reply_text(
            "❌ رابط غير صالح\n"
            "الرجاء ارسال رابط صحيح مثل:\n"
            "`https://t.me/your_channel`\n"
            "او `@your_channel`",
            parse_mode=ParseMode.MARKDOWN
        )
        return States.WAITING_FOR_CHANNEL_LINK.value
    
    # تنظيف الرابط
    if link.startswith('@'):
        clean_link = link
    elif 't.me/' in link:
        clean_link = link
    else:
        clean_link = f"https://t.me/{link}"
    
    finance_data = context.user_data.get("finance")
    if not finance_data:
        await update.message.reply_text("❌ حدث خطأ، الرجاء المحاولة مرة اخرى")
        return States.MAIN_MENU.value
    
    # التحقق من وجود ارقام كافية
    numbers_available = len(db.numbers["numbers"])
    if numbers_available < finance_data["count"]:
        await update.message.reply_text(
            f"❌ **لا يوجد ارقام كافية للتمويل**\n\n"
            f"المطلوب: {finance_data['count']} رقم\n"
            f"المتوفر: {numbers_available} رقم\n\n"
            "سيتم اعلامك عند توفر ارقام جديدة",
            parse_mode=ParseMode.MARKDOWN
        )
        return States.MAIN_MENU.value
    
    # خصم النقاط
    if not db.deduct_points(user_id, finance_data["cost"], f"تمويل {finance_data['count']} عضو"):
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
    
    # رسالة تأكيد
    await update.message.reply_text(
        f"✅ **تم بدء التمويل بنجاح**\n\n"
        f"📊 **معلومات التمويل:**\n"
        f"🆔 المعرف: `{finance_id}`\n"
        f"👥 عدد الاعضاء: {finance_data['count']}\n"
        f"💰 التكلفة: {finance_data['cost']} نقطة\n"
        f"🔗 القناة: {clean_link}\n\n"
        f"⏳ جاري التمويل...\n"
        f"سيتم اعلامك عند اضافة كل عضو",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # إشعار المديرين
    for admin_id in ADMIN_IDS:
        await helpers.safe_send_message(
            context.bot,
            admin_id,
            f"🚀 **تمويل جديد**\n\n"
            f"👤 المستخدم: `{user_id}`\n"
            f"👤 الاسم: {update.effective_user.first_name}\n"
            f"🔗 القناة: {clean_link}\n"
            f"👥 العدد: {finance_data['count']}\n"
            f"💰 التكلفة: {finance_data['cost']}\n"
            f"🆔 المعرف: `{finance_id}`",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # بدء التمويل في الخلفية
    asyncio.create_task(process_financing_job(context.application, finance_id))
    
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

# ==================== مهمة التمويل في الخلفية ====================

async def process_financing_job(app: Application, finance_id: str):
    """معالجة التمويل في الخلفية"""
    await asyncio.sleep(2)  # تأخير بسيط
    
    finance = db.financing.get(finance_id)
    if not finance:
        return
    
    logger.info(f"🚀 بدء تمويل: {finance_id}")
    
    # تحديث الحالة
    db.update_financing(finance_id, status="processing", started_at=datetime.now().isoformat())
    await db.save_all()
    
    user_id = int(finance["user_id"])
    remaining = finance["total_members"] - finance["added_members"]
    
    for i in range(remaining):
        # التحقق من حالة التمويل
        current = db.financing.get(finance_id)
        if not current or current["status"] not in ["processing", "pending"]:
            logger.info(f"⏸ توقف التمويل {finance_id}")
            break
        
        # الحصول على رقم
        numbers = db.get_available_numbers(1)
        if not numbers:
            logger.warning(f"⚠️ نفذت الارقام في التمويل {finance_id}")
            await helpers.safe_send_message(
                app.bot,
                user_id,
                "⚠️ **نفذت الارقام المتاحة**\n"
                "سيتم اكمال التمويل فور توفر ارقام جديدة"
            )
            break
        
        number = numbers[0]
        
        # محاكاة اضافة العضو (هنا يتم دمج مع Telethon للاضافة الحقيقية)
        # هذا مجرد محاكاة - يجب اضافة كود Telethon هنا
        await asyncio.sleep(random.uniform(1, 3))  # محاكاة وقت الاضافة
        
        # تحديث التمويل
        result = db.add_financing_member(finance_id, number)
        
        if result["success"]:
            # إرسال اشعار للمستخدم
            if (i + 1) % 5 == 0 or result["completed"]:  # كل 5 اعضاء او عند الاكتمال
                progress = result["progress"]
                await helpers.safe_send_message(
                    app.bot,
                    user_id,
                    f"✅ **تم اضافة {i+1} اعضاء**\n"
                    f"📊 التقدم: {progress}\n"
                    f"🚀 جاري اكمال التمويل..."
                )
        
        await db.save_all()
        
        if result["completed"]:
            # إرسال اشعار الاكتمال
            await helpers.safe_send_message(
                app.bot,
                user_id,
                f"✅ **اكتمل التمويل بنجاح**\n\n"
                f"📊 **ملخص التمويل:**\n"
                f"👥 اجمالي الاعضاء: {finance['total_members']}\n"
                f"💰 التكلفة: {finance['cost']} نقطة\n"
                f"🔗 القناة: {finance['channel_link']}\n\n"
                f"شكراً لاستخدامك البوت 🌟"
            )
            
            # إشعار المديرين
            for admin_id in ADMIN_IDS:
                await helpers.safe_send_message(
                    app.bot,
                    admin_id,
                    f"✅ **اكتمال تمويل**\n\n"
                    f"🆔 المعرف: `{finance_id}`\n"
                    f"👤 المستخدم: `{user_id}`\n"
                    f"👥 العدد: {finance['total_members']}"
                )
            
            logger.info(f"✅ اكتمل التمويل: {finance_id}")
            break
    
    logger.info(f"🏁 انتهاء معالجة التمويل: {finance_id}")

# ==================== معالج أزرار المدير ====================

async def admin_buttons_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج أزرار المدير"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # التحقق من صلاحية المدير
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("⛔️ هذه الخاصية للمدراء فقط")
        return States.MAIN_MENU.value
    
    data = query.data
    logger.info(f"🔧 زر مدير: {data} من {user_id}")
    
    # ========== احصائيات البوت ==========
    if data == "admin_stats":
        stats = db.get_bot_stats()
        
        # تفاصيل إضافية
        active_financing = len(db.get_active_financing())
        
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
            f"   • غير صالح: {stats['numbers']['invalid']}\n"
            f"   • ملفات: {stats['numbers']['files']}\n\n"
            f"📢 **قنوات اجبارية:** {stats['mandatory_channels']}\n"
            f"👥 **دعوات:** {stats['total_referrals']}\n"
            f"⏱ **مدة التشغيل:** {stats['bot_uptime']}\n"
            f"📌 **الاصدار:** {stats['version']}"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.admin_panel(),
            parse_mode=ParseMode.MARKDOWN
        )
        db.update_stats("admin_stats")
    
    # ========== اضافة ملف ارقام ==========
    elif data == "admin_add_numbers":
        text = (
            "📁 **اضافة ملف ارقام**\n\n"
            "📤 **ارسل ملف txt يحتوي على ارقام تليجرام**\n\n"
            "📌 **شروط الملف:**\n"
            "• الصيغة: .txt فقط\n"
            "• كل رقم في سطر منفصل\n"
            "• الارقام يجب ان تبدأ بـ 00963 او +963\n\n"
            "✅ **مثال:**\n"
            "00963123456789\n"
            "+963987654321\n\n"
            "⚠️ **ملاحظة:** الملفات الكبيرة قد تستغرق وقتاً في المعالجة"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.cancel_button()
        )
        
        context.user_data["admin_action"] = "add_numbers"
        return States.ADMIN_ADD_NUMBERS.value
    
    # ========== حذف ملف ارقام ==========
    elif data == "admin_delete_numbers":
        files = db.numbers["files"]
        
        if not files:
            await query.edit_message_text(
                "❌ **لا يوجد ملفات ارقام**\n\n"
                "استخدم زر 'اضافة ملف ارقام' لرفع ملفات جديدة",
                reply_markup=Keyboards.admin_panel()
            )
            return States.MAIN_MENU.value
        
        keyboard = []
        for file in files[-10:]:  # آخر 10 ملفات فقط
            keyboard.append([InlineKeyboardButton(
                text=f"🗑 {file['name']} ({file['count']} رقم)",
                callback_data=f"delete_file_{file['name']}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")])
        
        await query.edit_message_text(
            "🗑 **اختر الملف المراد حذفه**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== عرض ملفات الارقام ==========
    elif data == "admin_view_files":
        files = db.numbers["files"]
        
        if not files:
            text = "📁 **لا يوجد ملفات ارقام**"
        else:
            text = "📁 **ملفات الارقام**\n\n"
            for i, file in enumerate(files[-15:], 1):  # آخر 15 ملف
                text += f"{i}. **{file['name']}**\n"
                text += f"   • عدد الارقام: {file['count']}\n"
                text += f"   • الصالح: {file.get('valid', file['count'])}\n"
                text += f"   • غير صالح: {file.get('invalid', 0)}\n"
                text += f"   • التاريخ: {file['added_date'][:10]}\n\n"
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.back_button("back_to_admin"),
            parse_mode=ParseMode.MARKDOWN
        )
    
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
            f"📊 **اجمالي المستخدم:** {stats['total_used']}\n\n"
            f"📈 **نسبة الاستخدام:** "
            f"{stats['total_used']/stats['total_added']*100 if stats['total_added'] > 0 else 0:.1f}%"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.back_button("back_to_admin"),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== شحن رصيد ==========
    elif data == "admin_add_points":
        text = (
            "💰 **شحن رصيد مستخدم**\n\n"
            "📝 **ارسل بيانات الشحن بالتنسيق التالي:**\n"
            "`ايدي المستخدم المبلغ`\n\n"
            "✅ **مثال:**\n"
            "`123456789 100`\n\n"
            "❌ يمكنك ارسال 'الغاء' للخروج"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.cancel_button()
        )
        
        context.user_data["admin_action"] = "add_points"
        return States.ADMIN_ADD_POINTS.value
    
    # ========== خصم رصيد ==========
    elif data == "admin_deduct_points":
        text = (
            "💸 **خصم رصيد مستخدم**\n\n"
            "📝 **ارسل بيانات الخصم بالتنسيق التالي:**\n"
            "`ايدي المستخدم المبلغ`\n\n"
            "✅ **مثال:**\n"
            "`123456789 50`\n\n"
            "❌ يمكنك ارسال 'الغاء' للخروج"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.cancel_button()
        )
        
        context.user_data["admin_action"] = "deduct_points"
        return States.ADMIN_DEDUCT_POINTS.value
    
    # ========== اضافة حساب دعم ==========
    elif data == "admin_add_support":
        text = (
            "👤 **تغيير حساب الدعم**\n\n"
            f"الحساب الحالي: @{db.settings['support_username']}\n\n"
            "📝 **ارسل اليوزر الجديد:**\n"
            "مثال: `support_username`\n\n"
            "❌ يمكنك ارسال 'الغاء' للخروج"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.cancel_button()
        )
        
        context.user_data["admin_action"] = "add_support"
        return States.ADMIN_ADD_SUPPORT.value
    
    # ========== اضافة رابط قناة ==========
    elif data == "admin_add_channel":
        text = (
            "🔗 **تغيير رابط قناة البوت**\n\n"
            f"الرابط الحالي: {db.settings['channel_link']}\n\n"
            "📝 **ارسل الرابط الجديد:**\n"
            "مثال: `https://t.me/your_channel`\n\n"
            "❌ يمكنك ارسال 'الغاء' للخروج"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.cancel_button()
        )
        
        context.user_data["admin_action"] = "add_channel"
        return States.ADMIN_ADD_CHANNEL.value
    
    # ========== حظر مستخدم ==========
    elif data == "admin_ban":
        text = (
            "🚫 **حظر مستخدم**\n\n"
            "📝 **ارسل ايدي المستخدم المراد حظره**\n"
            "يمكنك اضافة سبب بعد الايدي\n\n"
            "✅ **مثال:**\n"
            "`123456789`\n"
            "او `123456789  سبب الحظر`\n\n"
            "❌ يمكنك ارسال 'الغاء' للخروج"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.cancel_button()
        )
        
        context.user_data["admin_action"] = "ban"
        return States.ADMIN_BAN_USER.value
    
    # ========== رفع حظر ==========
    elif data == "admin_unban":
        text = (
            "✅ **رفع حظر عن مستخدم**\n\n"
            "📝 **ارسل ايدي المستخدم المراد رفع الحظر عنه**\n\n"
            "✅ **مثال:**\n"
            "`123456789`\n\n"
            "❌ يمكنك ارسال 'الغاء' للخروج"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.cancel_button()
        )
        
        context.user_data["admin_action"] = "unban"
        return States.ADMIN_UNBAN_USER.value
    
    # ========== تغيير مكافأة الدعوة ==========
    elif data == "admin_change_reward":
        current = db.settings["invite_reward"]
        text = (
            "🎁 **تغيير مكافأة الدعوة**\n\n"
            f"القيمة الحالية: {current} نقطة\n\n"
            "📝 **ارسل القيمة الجديدة (رقم فقط):**\n"
            "✅ مثال: `15`\n\n"
            "❌ يمكنك ارسال 'الغاء' للخروج"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.cancel_button()
        )
        
        context.user_data["admin_action"] = "change_reward"
        return States.ADMIN_CHANGE_REWARD.value
    
    # ========== تغيير سعر العضو ==========
    elif data == "admin_change_price":
        current = db.settings["member_price"]
        text = (
            "💵 **تغيير سعر العضو**\n\n"
            f"السعر الحالي: {current} نقطة للعضو\n\n"
            "📝 **ارسل السعر الجديد (رقم فقط):**\n"
            "✅ مثال: `10`\n\n"
            "❌ يمكنك ارسال 'الغاء' للخروج"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.cancel_button()
        )
        
        context.user_data["admin_action"] = "change_price"
        return States.ADMIN_CHANGE_PRICE.value
    
    # ========== اضافة قناة اجبارية ==========
    elif data == "admin_add_mandatory":
        text = (
            "📢 **اضافة قناة اجبارية**\n\n"
            "📝 **ارسل معلومات القناة بهذا التنسيق:**\n"
            "`الاسم | الرابط | ايدي القناة`\n\n"
            "✅ **مثال:**\n"
            "`قناتي | https://t.me/my_channel | -100123456789`\n\n"
            "⚠️ **ملاحظات:**\n"
            "• البوت يجب ان يكون مشرف في القناة\n"
            "• يمكن الحصول على ايدي القناة من @getidsbot\n\n"
            "❌ يمكنك ارسال 'الغاء' للخروج"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.cancel_button()
        )
        
        context.user_data["admin_action"] = "add_mandatory"
        return States.ADMIN_ADD_MANDATORY.value
    
    # ========== حذف قناة اجبارية ==========
    elif data == "admin_delete_mandatory":
        if not db.mandatory:
            await query.edit_message_text(
                "❌ لا يوجد قنوات اجبارية",
                reply_markup=Keyboards.admin_panel()
            )
            return States.MAIN_MENU.value
        
        keyboard = []
        for channel in db.mandatory:
            keyboard.append([InlineKeyboardButton(
                text=f"🗑 {channel['name']}",
                callback_data=f"delete_mandatory_{channel['chat_id']}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")])
        
        await query.edit_message_text(
            "🗑 **اختر القناة المراد حذفها**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== عرض القنوات الاجبارية ==========
    elif data == "admin_view_mandatory":
        if not db.mandatory:
            text = "📢 **لا يوجد قنوات اجبارية**"
        else:
            text = "📢 **القنوات الاجبارية**\n\n"
            for i, channel in enumerate(db.mandatory, 1):
                text += f"{i}. **{channel['name']}**\n"
                text += f"   • الرابط: {channel['link']}\n"
                text += f"   • الايدي: `{channel['chat_id']}`\n"
                text += f"   • الاضافة: {channel['added_at'][:10]}\n\n"
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.back_button("back_to_admin"),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== تغيير رسالة الترحيب ==========
    elif data == "admin_change_welcome":
        current = db.settings["welcome_message"]
        text = (
            "✏️ **تغيير رسالة الترحيب**\n\n"
            f"**الرسالة الحالية:**\n{current}\n\n"
            "📝 **ارسل الرسالة الجديدة**\n"
            "يمكنك استخدام Markdown للتنسيق\n\n"
            "❌ يمكنك ارسال 'الغاء' للخروج"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.cancel_button()
        )
        
        context.user_data["admin_action"] = "change_welcome"
        return States.ADMIN_CHANGE_WELCOME.value
    
    # ========== رسالة جماعية ==========
    elif data == "admin_broadcast":
        text = (
            "📨 **ارسال رسالة جماعية**\n\n"
            "📝 **ارسل الرسالة التي تريد ارسالها لجميع المستخدمين**\n\n"
            "⚠️ **تحذير:** هذه العملية قد تستغرق وقتاً طويلاً حسب عدد المستخدمين\n\n"
            "❌ يمكنك ارسال 'الغاء' للخروج"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.cancel_button()
        )
        
        context.user_data["admin_action"] = "broadcast"
        return States.ADMIN_BROADCAST.value
    
    # ========== التحكم بالتمويل ==========
    elif data == "admin_financing_control":
        active = db.get_active_financing()
        
        if not active:
            text = "🔄 **لا يوجد تمويلات نشطة حالياً**"
            await query.edit_message_text(
                text,
                reply_markup=Keyboards.back_button("back_to_admin")
            )
            return States.MAIN_MENU.value
        
        text = "🔄 **التمويلات النشطة**\n\n"
        keyboard = []
        
        for finance in active[:10]:  # آخر 10 تمويلات
            text += f"🆔 `{finance['id']}`\n"
            text += f"👤 المستخدم: {finance['user_id']}\n"
            text += f"👥 التقدم: {finance['added_members']}/{finance['total_members']}\n"
            text += f"📊 الحالة: {finance['status']}\n\n"
            
            keyboard.append([InlineKeyboardButton(
                text=f"🎮 تحكم: {finance['id'][:8]}...",
                callback_data=f"finance_control_{finance['id']}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== التحكم بتمويل معين ==========
    elif data.startswith("finance_control_"):
        finance_id = data.replace("finance_control_", "")
        finance = db.financing.get(finance_id)
        
        if not finance:
            await query.edit_message_text(
                "❌ عملية تمويل غير موجودة",
                reply_markup=Keyboards.back_button("admin_financing_control")
            )
            return States.MAIN_MENU.value
        
        text = (
            f"🎮 **التحكم في التمويل**\n\n"
            f"🆔 **المعرف:** `{finance_id}`\n"
            f"👤 **المستخدم:** {finance['user_id']}\n"
            f"🔗 **القناة:** {finance['channel_link'][:30]}...\n"
            f"👥 **التقدم:** {finance['added_members']}/{finance['total_members']}\n"
            f"📊 **الحالة:** {finance['status']}\n"
            f"💰 **التكلفة:** {finance['cost']}\n"
            f"📅 **البداية:** {finance['created_at'][:16]}"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.financing_control(finance_id),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== ايقاف تمويل ==========
    elif data.startswith("finance_stop_"):
        finance_id = data.replace("finance_stop_", "")
        db.update_financing(finance_id, status="failed")
        await db.save_all()
        
        await query.edit_message_text(
            f"✅ تم ايقاف التمويل {finance_id}",
            reply_markup=Keyboards.back_button("admin_financing_control")
        )
    
    # ========== نسخة احتياطية ==========
    elif data == "admin_backup":
        await query.edit_message_text(
            "🔄 جاري انشاء نسخة احتياطية...",
            reply_markup=None
        )
        
        backup_path = await db.create_backup()
        
        if backup_path:
            await query.edit_message_text(
                f"✅ **تم انشاء النسخة الاحتياطية بنجاح**\n\n"
                f"📁 اسم الملف: `{backup_path.name}`\n"
                f"📊 الحجم: {backup_path.stat().st_size / 1024:.2f} KB\n"
                f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                reply_markup=Keyboards.back_button("back_to_admin"),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.edit_message_text(
                "❌ فشل انشاء النسخة الاحتياطية",
                reply_markup=Keyboards.back_button("back_to_admin")
            )
    
    # ========== استعادة نسخة ==========
    elif data == "admin_restore":
        backups = list(DATA_DIR.glob("backup_*.json"))
        
        if not backups:
            await query.edit_message_text(
                "❌ لا يوجد نسخ احتياطية",
                reply_markup=Keyboards.back_button("back_to_admin")
            )
            return States.MAIN_MENU.value
        
        keyboard = []
        for backup in sorted(backups, reverse=True)[:10]:
            size = backup.stat().st_size / 1024
            date = backup.stem.replace("backup_", "")
            keyboard.append([InlineKeyboardButton(
                text=f"🔄 {date} ({size:.1f} KB)",
                callback_data=f"restore_{backup.name}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")])
        
        await query.edit_message_text(
            "🔄 **اختر النسخة الاحتياطية للاستعادة**\n\n⚠️ استعادة النسخة ستحل محل البيانات الحالية",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== سجلات البوت ==========
    elif data == "admin_logs":
        logs = db.logs[-20:]  # آخر 20 سجل
        
        if not logs:
            text = "📋 **لا يوجد سجلات**"
        else:
            text = "📋 **آخر السجلات**\n\n"
            for log in logs:
                text += f"• {log['type']}: {log.get('points', '')} - {log.get('reason', '')}\n"
                text += f"  🕐 {log['timestamp'][:16]}\n\n"
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.back_button("back_to_admin"),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== اعدادات متقدمة ==========
    elif data == "admin_settings":
        text = (
            "⚙️ **الاعدادات الحالية**\n\n"
            f"🎁 مكافأة الدعوة: {db.settings['invite_reward']}\n"
            f"💵 سعر العضو: {db.settings['member_price']}\n"
            f"🎁 المكافأة اليومية: {db.settings['daily_bonus']}\n"
            f"📊 الحد الادنى للتمويل: {db.settings['min_financing']}\n"
            f"📊 الحد الاقصى للتمويل: {db.settings['max_financing']}\n"
            f"👤 حساب الدعم: @{db.settings['support_username']}\n"
            f"🔗 قناة البوت: {db.settings['channel_link'][:30]}...\n"
            f"📌 حالة البوت: {db.settings['bot_status']}\n"
            f"📌 وضع الصيانة: {'🟢' if not db.settings.get('maintenance_mode') else '🔴'}\n"
            f"📌 الاصدار: {db.settings['version']}"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.back_button("back_to_admin"),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== حذف ملف محدد ==========
    elif data.startswith("delete_file_"):
        filename = data.replace("delete_file_", "")
        
        if db.delete_file(filename):
            await query.edit_message_text(
                f"✅ تم حذف الملف {filename} بنجاح",
                reply_markup=Keyboards.admin_panel()
            )
        else:
            await query.edit_message_text(
                f"❌ فشل حذف الملف {filename}",
                reply_markup=Keyboards.admin_panel()
            )
    
    # ========== حذف قناة اجبارية محددة ==========
    elif data.startswith("delete_mandatory_"):
        chat_id = data.replace("delete_mandatory_", "")
        
        if db.remove_mandatory_channel(chat_id):
            await query.edit_message_text(
                "✅ تم حذف القناة الاجبارية بنجاح",
                reply_markup=Keyboards.admin_panel()
            )
        else:
            await query.edit_message_text(
                "❌ فشل حذف القناة",
                reply_markup=Keyboards.admin_panel()
            )
    
    # ========== استعادة نسخة محددة ==========
    elif data.startswith("restore_"):
        filename = data.replace("restore_", "")
        backup_path = DATA_DIR / filename
        
        if backup_path.exists():
            await query.edit_message_text(
                "🔄 جاري استعادة النسخة الاحتياطية...",
                reply_markup=None
            )
            
            if await db.restore_backup(backup_path):
                await query.edit_message_text(
                    "✅ تم استعادة النسخة الاحتياطية بنجاح",
                    reply_markup=Keyboards.admin_panel()
                )
            else:
                await query.edit_message_text(
                    "❌ فشل استعادة النسخة الاحتياطية",
                    reply_markup=Keyboards.admin_panel()
                )
        else:
            await query.edit_message_text(
                "❌ ملف النسخة الاحتياطية غير موجود",
                reply_markup=Keyboards.admin_panel()
            )
    
    # ========== رجوع للوحة التحكم ==========
    elif data == "back_to_admin":
        await query.edit_message_text(
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
                await update.message.reply_text(
                    "❌ تنسيق خاطئ\n"
                    "استخدم: `ايدي المستخدم المبلغ`\n"
                    "مثال: `123456789 100`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return States.ADMIN_ADD_POINTS.value
            
            target_id = int(parts[0])
            points = int(parts[1])
            
            if points <= 0:
                await update.message.reply_text("❌ المبلغ يجب ان يكون اكبر من 0")
                return States.ADMIN_ADD_POINTS.value
            
            db.add_points(target_id, points, f"شحن من المدير {user_id}")
            await db.save_all()
            
            await update.message.reply_text(
                f"✅ **تم شحن الرصيد بنجاح**\n\n"
                f"👤 المستخدم: `{target_id}`\n"
                f"💰 المبلغ: {points} نقطة",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # اعلام المستهدف
            await helpers.safe_send_message(
                context.bot,
                target_id,
                f"💰 **تم شحن رصيدك**\n\n"
                f"➕ المبلغ: {points} نقطة\n"
                f"⭐️ رصيدك الجديد: {db.get_user(target_id)['points']}",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except ValueError:
            await update.message.reply_text("❌ الرجاء ادخال ارقام صحيحة")
            return States.ADMIN_ADD_POINTS.value
    
    # ========== خصم رصيد ==========
    elif admin_action == "deduct_points":
        try:
            parts = text.split()
            if len(parts) != 2:
                await update.message.reply_text(
                    "❌ تنسيق خاطئ\n"
                    "استخدم: `ايدي المستخدم المبلغ`\n"
                    "مثال: `123456789 50`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return States.ADMIN_DEDUCT_POINTS.value
            
            target_id = int(parts[0])
            points = int(parts[1])
            
            if points <= 0:
                await update.message.reply_text("❌ المبلغ يجب ان يكون اكبر من 0")
                return States.ADMIN_DEDUCT_POINTS.value
            
            if db.deduct_points(target_id, points, f"خصم من المدير {user_id}"):
                await db.save_all()
                
                await update.message.reply_text(
                    f"✅ **تم خصم الرصيد بنجاح**\n\n"
                    f"👤 المستخدم: `{target_id}`\n"
                    f"💰 المبلغ: {points} نقطة",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # اعلام المستهدف
                await helpers.safe_send_message(
                    context.bot,
                    target_id,
                    f"💸 **تم خصم من رصيدك**\n\n"
                    f"➖ المبلغ: {points} نقطة\n"
                    f"⭐️ رصيدك المتبقي: {db.get_user(target_id)['points']}",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text("❌ رصيد المستخدم غير كافي")
            
        except ValueError:
            await update.message.reply_text("❌ الرجاء ادخال ارقام صحيحة")
            return States.ADMIN_DEDUCT_POINTS.value
    
    # ========== اضافة حساب دعم ==========
    elif admin_action == "add_support":
        username = text.strip()
        if username.startswith('@'):
            username = username[1:]
        
        db.settings["support_username"] = username
        db.settings["updated_at"] = datetime.now().isoformat()
        await db.save_all()
        
        await update.message.reply_text(
            f"✅ **تم تحديث حساب الدعم**\n\n"
            f"👤 الحساب الجديد: @{username}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== اضافة رابط قناة ==========
    elif admin_action == "add_channel":
        link = text.strip()
        if not helpers.is_valid_link(link):
            await update.message.reply_text("❌ رابط غير صالح")
            return States.ADMIN_ADD_CHANNEL.value
        
        db.settings["channel_link"] = link
        db.settings["updated_at"] = datetime.now().isoformat()
        await db.save_all()
        
        await update.message.reply_text(
            f"✅ **تم تحديث رابط القناة**\n\n"
            f"🔗 الرابط الجديد: {link}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== حظر مستخدم ==========
    elif admin_action == "ban":
        try:
            parts = text.split(maxsplit=1)
            target_id = int(parts[0])
            reason = parts[1] if len(parts) > 1 else "بدون سبب"
            
            if target_id in ADMIN_IDS:
                await update.message.reply_text("❌ لا يمكن حظر مدير")
                return States.ADMIN_BAN_USER.value
            
            if db.ban_user(target_id, reason, user_id):
                await db.save_all()
                
                await update.message.reply_text(
                    f"✅ **تم حظر المستخدم**\n\n"
                    f"👤 الايدي: `{target_id}`\n"
                    f"📝 السبب: {reason}",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # اعلام المحظور
                await helpers.safe_send_message(
                    context.bot,
                    target_id,
                    f"⛔️ **تم حظرك من البوت**\n\n"
                    f"📝 السبب: {reason}\n"
                    f"🆘 للاستئناف: @{db.settings['support_username']}"
                )
            else:
                await update.message.reply_text("❌ فشل حظر المستخدم")
            
        except ValueError:
            await update.message.reply_text("❌ ايدي المستخدم غير صحيح")
            return States.ADMIN_BAN_USER.value
    
    # ========== رفع حظر ==========
    elif admin_action == "unban":
        try:
            target_id = int(text)
            
            if db.unban_user(target_id):
                await db.save_all()
                
                await update.message.reply_text(
                    f"✅ **تم رفع الحظر عن المستخدم**\n\n"
                    f"👤 الايدي: `{target_id}`",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # اعلام المستخدم
                await helpers.safe_send_message(
                    context.bot,
                    target_id,
                    "✅ **تم رفع الحظر عنك**\nيمكنك استخدام البوت مرة اخرى"
                )
            else:
                await update.message.reply_text("❌ المستخدم غير موجود في قائمة المحظورين")
            
        except ValueError:
            await update.message.reply_text("❌ ايدي المستخدم غير صحيح")
            return States.ADMIN_UNBAN_USER.value
    
    # ========== تغيير مكافأة الدعوة ==========
    elif admin_action == "change_reward":
        try:
            reward = int(text)
            if reward <= 0:
                await update.message.reply_text("❌ المكافأة يجب ان تكون اكبر من 0")
                return States.ADMIN_CHANGE_REWARD.value
            
            db.settings["invite_reward"] = reward
            db.settings["updated_at"] = datetime.now().isoformat()
            await db.save_all()
            
            await update.message.reply_text(
                f"✅ **تم تحديث مكافأة الدعوة**\n\n"
                f"🎁 القيمة الجديدة: {reward} نقطة",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except ValueError:
            await update.message.reply_text("❌ الرجاء ادخال رقم صحيح")
            return States.ADMIN_CHANGE_REWARD.value
    
    # ========== تغيير سعر العضو ==========
    elif admin_action == "change_price":
        try:
            price = int(text)
            if price <= 0:
                await update.message.reply_text("❌ السعر يجب ان يكون اكبر من 0")
                return States.ADMIN_CHANGE_PRICE.value
            
            db.settings["member_price"] = price
            db.settings["updated_at"] = datetime.now().isoformat()
            await db.save_all()
            
            await update.message.reply_text(
                f"✅ **تم تحديث سعر العضو**\n\n"
                f"💵 السعر الجديد: {price} نقطة للعضو",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except ValueError:
            await update.message.reply_text("❌ الرجاء ادخال رقم صحيح")
            return States.ADMIN_CHANGE_PRICE.value
    
    # ========== اضافة قناة اجبارية ==========
    elif admin_action == "add_mandatory":
        try:
            parts = [p.strip() for p in text.split('|')]
            if len(parts) != 3:
                await update.message.reply_text(
                    "❌ تنسيق خاطئ\n"
                    "استخدم: `الاسم | الرابط | ايدي القناة`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return States.ADMIN_ADD_MANDATORY.value
            
            name, link, chat_id = parts
            
            # التحقق من صحة الرابط
            if not helpers.is_valid_link(link):
                await update.message.reply_text("❌ رابط القناة غير صالح")
                return States.ADMIN_ADD_MANDATORY.value
            
            # محاولة التحقق من القناة
            try:
                if str(chat_id).lstrip('-').isdigit():
                    chat_id_int = int(chat_id)
                else:
                    chat_id_int = chat_id
                
                chat = await context.bot.get_chat(chat_id_int)
                await context.bot.get_chat_member(chat_id_int, context.bot.id)
                
            except Exception as e:
                await update.message.reply_text(
                    f"❌ **خطأ في التحقق من القناة**\n\n"
                    f"تأكد من:\n"
                    f"• ان البوت مشرف في القناة\n"
                    f"• صحة ايدي القناة\n\n"
                    f"الخطأ: {str(e)[:100]}"
                )
                return States.ADMIN_ADD_MANDATORY.value
            
            db.add_mandatory_channel(name, link, str(chat_id))
            await db.save_all()
            
            await update.message.reply_text(
                f"✅ **تم اضافة القناة الاجبارية**\n\n"
                f"📢 الاسم: {name}\n"
                f"🔗 الرابط: {link}\n"
                f"🆔 الايدي: `{chat_id}`",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {str(e)}")
            return States.ADMIN_ADD_MANDATORY.value
    
    # ========== تغيير رسالة الترحيب ==========
    elif admin_action == "change_welcome":
        db.settings["welcome_message"] = text
        db.settings["updated_at"] = datetime.now().isoformat()
        await db.save_all()
        
        await update.message.reply_text(
            "✅ **تم تحديث رسالة الترحيب**",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== رسالة جماعية ==========
    elif admin_action == "broadcast":
        await update.message.reply_text(
            "🔄 جاري ارسال الرسالة الى جميع المستخدمين...\n"
            "قد تستغرق هذه العملية بعض الوقت"
        )
        
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
                await asyncio.sleep(0.05)  # تجنب الـ Flood wait
            except Exception as e:
                failed += 1
                logger.warning(f"فشل ارسال رسالة للمستخدم {uid}: {e}")
        
        await update.message.reply_text(
            f"📨 **نتيجة الارسال الجماعي**\n\n"
            f"✅ نجح: {success}\n"
            f"❌ فشل: {failed}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # العودة للوحة التحكم
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
    
    # التحقق من صلاحية المدير
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ هذه الخاصية للمدراء فقط")
        return States.MAIN_MENU.value
    
    admin_action = context.user_data.get("admin_action")
    
    if admin_action != "add_numbers":
        await update.message.reply_text("❌ انت غير في وضع اضافة ملفات")
        return States.MAIN_MENU.value
    
    document = update.message.document
    
    # التحقق من صيغة الملف
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text(
            "❌ فقط ملفات txt مسموحة\n"
            "الرجاء ارسال ملف بصيغة .txt"
        )
        return States.ADMIN_ADD_NUMBERS.value
    
    # ارسال رسالة انتظار
    wait_msg = await update.message.reply_text(
        "🔄 جاري معالجة الملف...\n"
        "الرجاء الانتظار"
    )
    
    try:
        # تحميل الملف
        file = await context.bot.get_file(document.file_id)
        file_content = await file.download_as_bytearray()
        
        # قراءة المحتوى
        content = file_content.decode('utf-8')
        lines = content.split('\n')
        
        # تنظيف ومعالجة الارقام
        numbers = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):  # تجاهل التعليقات
                numbers.append(line)
        
        if not numbers:
            await wait_msg.edit_text("❌ الملف فارغ")
            return States.ADMIN_ADD_NUMBERS.value
        
        # اضافة الارقام
        file_info = db.add_numbers_file(document.file_name, numbers)
        await db.save_all()
        
        # رسالة النجاح
        text = (
            "✅ **تم رفع الملف بنجاح**\n\n"
            f"📁 **اسم الملف:** {document.file_name}\n"
            f"📊 **اجمالي الارقام:** {file_info['count']}\n"
            f"✅ **الارقام الصالحة:** {file_info['valid']}\n"
            f"❌ **الارقام غير الصالحة:** {file_info['invalid']}\n\n"
            f"📞 **الارقام المتاحة الآن:** {len(db.numbers['numbers'])}"
        )
        
        await wait_msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)
        
    except UnicodeDecodeError:
        await wait_msg.edit_text(
            "❌ **خطأ في ترميز الملف**\n\n"
            "تأكد من ان الملف بترميز UTF-8",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        await wait_msg.edit_text(f"❌ خطأ في قراءة الملف: {str(e)[:100]}")
    
    # العودة للوحة التحكم
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
    
    # التحقق من الحظر
    if db.is_banned(user_id):
        await update.message.reply_text("⛔️ أنت محظور من استخدام البوت")
        return States.MAIN_MENU.value
    
    # التحقق من حالة المستخدم الحالية
    current_state = context.user_data.get("state", States.MAIN_MENU.value)
    
    # معالجة حسب الحالة
    if current_state == States.WAITING_FOR_MEMBERS_COUNT.value:
        return await handle_members_count(update, context)
    
    elif current_state == States.WAITING_FOR_CHANNEL_LINK.value:
        return await handle_channel_link(update, context)
    
    # معالجة نصوص المديرين
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
    
    # رسالة افتراضية
    await update.message.reply_text(
        "❌ امر غير معروف\n"
        "استخدم /start للعودة للقائمة الرئيسية"
    )
    
    return States.MAIN_MENU.value

# ==================== معالج الاخطاء ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج الاخطاء الشامل"""
    try:
        error = context.error
        tb = traceback.format_exc()
        
        logger.error(f"❌ خطأ: {error}\n{tb}")
        
        # حفظ الخطأ في ملف
        error_log = LOGS_DIR / f"error_{datetime.now().strftime('%Y%m%d')}.log"
        async with aiofiles.open(error_log, 'a', encoding='utf-8') as f:
            await f.write(f"{datetime.now().isoformat()}\n")
            await f.write(f"Update: {update}\n")
            await f.write(f"Error: {error}\n")
            await f.write(f"Traceback: {tb}\n")
            await f.write("-" * 50 + "\n")
        
        # ابلاغ المديرين
        for admin_id in ADMIN_IDS:
            try:
                error_msg = f"⚠️ **خطأ في البوت**\n\n`{str(error)[:200]}`"
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=error_msg,
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
        
        # ابلاغ المستخدم
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ عذراً، حدث خطأ غير متوقع\n"
                "تم ابلاغ المطورين وسيتم حل المشكلة قريباً"
            )
            
    except Exception as e:
        logger.critical(f"خطأ في معالج الاخطاء نفسه: {e}")

# ==================== اعداد اوامر البوت ====================

async def set_bot_commands(application: Application) -> None:
    """اعداد اوامر البوت"""
    commands = [
        BotCommand("start", "بدء استخدام البوت"),
        BotCommand("help", "مساعدة"),
        BotCommand("points", "عرض نقاطي"),
        BotCommand("finance", "تمويل مشتركين"),
        BotCommand("stats", "احصائياتي"),
    ]
    
    await application.bot.set_my_commands(commands)

# ==================== وظائف دورية ====================

async def daily_cleanup_job(context: ContextTypes.DEFAULT_TYPE):
    """وظيفة التنظيف اليومية"""
    logger.info("🧹 بدء عملية التنظيف اليومية")
    
    # حذف الملفات المؤقتة القديمة
    now = datetime.now()
    for temp_file in TEMP_DIR.glob("*"):
        try:
            mtime = datetime.fromtimestamp(temp_file.stat().st_mtime)
            if (now - mtime) > timedelta(days=7):
                temp_file.unlink()
                logger.info(f"🗑 تم حذف {temp_file.name}")
        except:
            pass
    
    # حذف سجلات الاخطاء القديمة
    for log_file in LOGS_DIR.glob("error_*.log"):
        try:
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if (now - mtime) > timedelta(days=30):
                log_file.unlink()
                logger.info(f"🗑 تم حذف {log_file.name}")
        except:
            pass
    
    logger.info("✅ اكتملت عملية التنظيف اليومية")

async def backup_job(context: ContextTypes.DEFAULT_TYPE):
    """وظيفة النسخ الاحتياطي الدورية"""
    logger.info("💾 بدء النسخ الاحتياطي الدوري")
    backup_path = await db.create_backup()
    if backup_path:
        logger.info(f"✅ تم انشاء نسخة احتياطية: {backup_path.name}")
    else:
        logger.error("❌ فشل انشاء النسخة الاحتياطية")

# ==================== الدالة الرئيسية ====================

def main() -> None:
    """الدالة الرئيسية لتشغيل البوت"""
    
    print(f"{Fore.CYAN}{'='*60}{Fore.RESET}")
    print(f"{Fore.GREEN}🤖 بوت التمويل المتكامل{Fore.RESET}")
    print(f"{Fore.YELLOW}📌 الاصدار: 2.0{Fore.RESET}")
    print(f"{Fore.YELLOW}👤 المطور: System{Fore.RESET}")
    print(f"{Fore.CYAN}{'='*60}{Fore.RESET}")
    
    # انشاء التطبيق
    application = Application.builder()\
        .token(BOT_TOKEN)\
        .concurrent_updates(True)\
        .build()
    
    # اعداد اوامر البوت
    application.post_init = set_bot_commands
    
    # انشاء معالج المحادثة
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            # حالات المستخدمين
            States.MAIN_MENU.value: [
                CallbackQueryHandler(user_buttons_callback),
                CallbackQueryHandler(check_subscription_callback, pattern="^check_subscription$"),
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
            
            # حالات المديرين
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
        fallbacks=[
            CommandHandler("start", start),
            CallbackQueryHandler(user_buttons_callback),
            CallbackQueryHandler(admin_buttons_callback, pattern="^admin_"),
        ],
        per_message=False,
        name="main_conversation",
        persistent=False,
    )
    
    application.add_handler(conv_handler)
    
    # اضافة معالج للازرار خارج المحادثة
    application.add_handler(CallbackQueryHandler(admin_buttons_callback, pattern="^admin_"))
    application.add_handler(CallbackQueryHandler(user_buttons_callback))
    
    # اضافة معالج الاخطاء
    application.add_error_handler(error_handler)
    
    # اضافة وظائف دورية
    job_queue = application.job_queue
    
    if job_queue:
        # تنظيف يومي في الساعة 3 صباحاً
        job_queue.run_daily(
            daily_cleanup_job,
            time=datetime.strptime("03:00", "%H:%M").time(),
            name="daily_cleanup"
        )
        
        # نسخ احتياطي كل 6 ساعات
        job_queue.run_repeating(
            backup_job,
            interval=21600,  # 6 ساعات
            first=10,
            name="periodic_backup"
        )
    
    print(f"{Fore.GREEN}✅ البوت يعمل بنجاح...{Fore.RESET}")
    print(f"{Fore.YELLOW}📝 سجل الأحداث في bot.log{Fore.RESET}")
    print(f"{Fore.CYAN}{'='*60}{Fore.RESET}")
    
    # تشغيل البوت
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}👋 تم ايقاف البوت{Fore.RESET}")
    except Exception as e:
        print(f"{Fore.RED}❌ خطأ فادح: {e}{Fore.RESET}")
        traceback.print_exc()

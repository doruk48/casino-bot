import asyncio
import logging
import os
import secrets
import random
import shutil
import time
import uuid
from collections import Counter
from datetime import datetime

# MongoDB imports
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Dict, List, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, LabeledPrice, SuccessfulPayment
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
    PreCheckoutQueryHandler, MessageHandler, filters
)
from telegram.error import BadRequest

from PIL import Image, ImageDraw, ImageFont
import io
import re


# ═══════════════════════════════════════════════════════════════
#  BASE_DIR TANIMI
# ═══════════════════════════════════════════════════════════════

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ═══════════════════════════════════════════════════════════════
#  FONT BULMA FONKSİYONU (RAILWAY UYUMLU)
# ═══════════════════════════════════════════════════════════════

def get_font(font_size: int):
    """Sistemdeki fontları dene, hiçbiri yoksa default kullan"""
    
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        "/system/fonts/Roboto-Bold.ttf",
    ]
    
    for path in font_paths:
        try:
            font = ImageFont.truetype(path, font_size)
            print(f"✅ Font bulundu: {path} (boyut: {font_size})")
            return font
        except:
            continue
    
    print(f"⚠️ Font bulunamadı, default kullanılıyor (boyut: {font_size})")
    return ImageFont.load_default()
    from PIL import Image, ImageDraw, ImageFont
import io
import os

def get_font(size: int):
    """Railway için font yükle"""
    
    # Railway sistem fontları
    fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    
    for font_path in fonts:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except:
                continue
    
    print(f"⚠️ Font bulunamadı!")
    return ImageFont.load_default()
    
# ═══════════════════════════════════════════════════════════════
#  AYARLAR
# ═══════════════════════════════════════════════════════════════

BOT_TOKEN = os.getenv("BOT_TOKEN", "8646115906:AAEn4Rydo0TjRBm_iiaZqSRJ-KcIqUmNyZQ")
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://1botuser2:Barkın1234@cluster0.8zvjyjk.mongodb.net/")

STARTING_BALANCE = 1000000
CURRENCY_SYMBOL = "🪙"
BET_WINDOW = 25
BLACKJACK_TURN = 15
MAX_OPEN_GAMES = 5
LEADERBOARD_SIZE = 15
RATE_LIMIT_SECONDS = 1
BACKUP_DIR = "casinibot_backups"
LOG_FILE = "casinibot.log"

MAX_SAFE_BALANCE = 10**60
WARNING_LIMIT = 10**58

# Rulet
ROULETTE_MULTIPLIERS = {"red": 2, "black": 2, "green": 72, "number": 36}
ROULETTE_IMG_PATH = BASE_DIR

# Blackjack
BLACKJACK_IMG_PATH = BASE_DIR

# Kazı Kazan
KAPALI_KART_PATH = os.path.join(BASE_DIR, "kapali.jpg")
ACIK_KART_PATH = os.path.join(BASE_DIR, "acik.jpg")

# Transfer
TRANSFER_TEMPLATE_PATH = os.path.join(BASE_DIR, "transfer.png")
# Çarkıfelek
WHEEL_SEGMENTS = [
    # Tam kayıp PASS - 12 adet
    ("💀 PASS 💀", 0), ("💀 PASS 💀", 0), ("💀 PASS 💀", 0),
    ("💀 PASS 💀", 0), ("💀 PASS 💀", 0), ("💀 PASS 💀", 0),
    ("💀 PASS 💀", 0), ("💀 PASS 💀", 0), ("💀 PASS 💀", 0),
    ("💀 PASS 💀", 0), ("💀 PASS 💀", 0), ("💀 PASS 💀", 0),
    
    # İADE - 12 adet (bahis iade)
    ("🔄 İADE 🔄", 1), ("🔄 İADE 🔄", 1), ("🔄 İADE 🔄", 1),
    ("🔄 İADE 🔄", 1), ("🔄 İADE 🔄", 1), ("🔄 İADE 🔄", 1),
    ("🔄 İADE 🔄", 1), ("🔄 İADE 🔄", 1), ("🔄 İADE 🔄", 1),
    ("🔄 İADE 🔄", 1), ("🔄 İADE 🔄", 1), ("🔄 İADE 🔄", 1),
    
    # Küçük çarpanlar - 5 adet
    ("🟢 2x", 2), ("🟢 2x", 2), ("🟢 2x", 2),  # 3 adet 2x
    ("🟢 3x", 3), ("🟢 3x", 3),  # 2 adet 3x
    
    # Orta çarpanlar - 4 adet
    ("🔵 5x", 5), ("🔵 5x", 5),  # 2 adet 5x
    ("🔵 10x", 10),  # 1 adet 10x
    ("🔵 15x", 15),  # 1 adet 15x
    
    # Büyük çarpanlar - 3 adet
    ("🟣 25x", 25),  # 1 adet 25x
    ("🟣 50x", 50),  # 1 adet 50x
    ("🟡 100x", 100),  # 1 adet 100x
]

# Her oyunda rastgele karıştır
import random
random.shuffle(WHEEL_SEGMENTS)

# Kazı Kazan
SCRATCH_SYMBOLS = [
    (250, 1), (100, 2), (50, 3), (20, 5), (10, 10),
    (5, 15), (3, 20), (2, 29), (0, 15),
]
SCRATCH_POOL = []
for val, weight in SCRATCH_SYMBOLS:
    SCRATCH_POOL.extend([val] * weight)

SCRATCH_EMOJI = {
    250: "🔥👑💎🔥", 100: "💎💎💎✨", 50: "💎💎🌟", 20: "⭐🌟⭐",
    10: "🏆🥇🏆", 5: "🔹🔹🔹", 3: "🟤🟤🟤", 2: "💰💰", 0: "💀🌑💀"
}

# VIP Kasa
STARS_CONFIG = {
    10:   {"coin": 1000000,           "label": "🥉 BRONZ KESE",     "suffix": "1 Milyon"},
    25:   {"coin": 50000000,          "label": "🥈 GÜMÜŞ KASA",    "suffix": "50 Milyon"},
    50:   {"coin": 1000000000,        "label": "🥇 ALTIN KASA",    "suffix": "1 Milyar"},
    100:  {"coin": 10000000000,       "label": "💎 ELMAS KASA",    "suffix": "10 Milyar"},
    250:  {"coin": 100000000000,      "label": "🔥 PLATİN KASA",   "suffix": "100 Milyar"},
    500:  {"coin": 1000000000000,     "label": "🌌 KOZMİK KASA",   "suffix": "1 Trilyon"},
    1000: {"coin": 10000000000000,    "label": "👑 KRAL SERVETİ",  "suffix": "10 Trilyon"}
}

# Level
LEVELS = [
    (0, "Çırak", "🪵"),
    (1_000, "Bahisçi", "🎯"),
    (100_000, "Gümüş", "🥈"),
    (1_000_000, "Altın", "🥇"),
    (10_000_000, "Platin", "💠"),
    (100_000_000, "Elmas", "💎"),
    (1_000_000_000, "Diamond", "💎✨"),
    (10_000_000_000, "Epic", "👑"),
    (100_000_000_000, "Grand", "🔱"),
    (1_000_000_000_000, "Mythic", "🔥"),
    (10**13, "Legendary", "⭐"),
    (10**15, "Transcendent", "🌌"),
    (10**18, "Cosmic", "🪐"),
    (10**21, "Eternal", "♾️"),
    (10**24, "Omnipotent", "👑👑"),
    (10**30, "MUTLAK TANRI", "👑👑👑"),
]

# Rulet renkler
RED_NUMS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
ROUL_COLORS = {0: "green"}
for n in range(1, 37):
    ROUL_COLORS[n] = "red" if n in RED_NUMS else "black"
ROUL_EMOJI = {"red": "🔴", "black": "⚫", "green": "🟢"}

# Blackjack
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["♠️", "♥️", "♦️", "♣️"]
BJ_IMG_PATH = "/storage/emulated/0/Blackjack"
CARD_WIDTH, CARD_HEIGHT = 60, 84


# Admin
ADMIN_IDS = [6927797531]


# ═══════════════════════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

if os.path.exists(ROULETTE_IMG_PATH):
    logger.info(f"✅ Rulet görsel klasörü bulundu: {ROULETTE_IMG_PATH}")
else:
    logger.warning(f"⚠️ Rulet görsel klasörü bulunamadı: {ROULETTE_IMG_PATH}")


# ═══════════════════════════════════════════════════════════════
#  MONGODB BAĞLANTISI
# ═══════════════════════════════════════════════════════════════

_mongo_client = None
_db = None

async def get_db():
    global _mongo_client, _db
    if _db is None:
        _mongo_client = AsyncIOMotorClient(MONGO_URI)
        _db = _mongo_client['casinobot']
    return _db

async def init_db():
    db = await get_db()
    
    # Index'ler oluştur
    await db.users.create_index("telegram_id", unique=True)
    await db.transactions.create_index("from_id")
    await db.transactions.create_index("to_id")
    await db.games.create_index([("chat_id", 1), ("state", 1)])
    await db.game_participants.create_index("game_id")
    
    logger.info("🚀 MongoDB bağlantısı kuruldu!")
    
    
    
# ═══════════════════════════════════════════════════════════════
#  EKONOMİ FONKSİYONLARI (MONGODB)
# ═══════════════════════════════════════════════════════════════

_user_locks: dict[int, asyncio.Lock] = {}
_locks_meta = asyncio.Lock()

async def _get_lock(uid: int) -> asyncio.Lock:
    async with _locks_meta:
        if uid not in _user_locks:
            _user_locks[uid] = asyncio.Lock()
        return _user_locks[uid]

def get_level(balance: int) -> tuple[str, str]:
    result = (LEVELS[0][1], LEVELS[0][2])
    for min_bal, name, emoji in LEVELS:
        if balance >= min_bal:
            result = (name, emoji)
    return result

def format_amount(amount: int) -> str:
    """Büyük sayıları formatla"""
    if amount < 1000:
        return f"{amount}{CURRENCY_SYMBOL}"
    
    units = [
        (10**60, "Nvd"), (10**57, "Ocd"), (10**54, "Spt"), (10**51, "Sxd"),
        (10**48, "Qnd"), (10**45, "Qtd"), (10**42, "Trd"), (10**39, "Dcd"),
        (10**36, "Udc"), (10**33, "Dc"), (10**30, "N"), (10**27, "Ot"),
        (10**24, "Sp"), (10**21, "Sx"), (10**18, "Qt"), (10**15, "Q"),
        (10**12, "T"), (10**9, "B"), (10**6, "M"), (10**3, "K")
    ]
    
    for unit, suffix in units:
        if amount >= unit:
            value = amount / unit
            if value >= 100:
                formatted = f"{value:.0f}"
            elif value >= 10:
                formatted = f"{value:.1f}"
            else:
                formatted = f"{value:.2f}".rstrip('0').rstrip('.')
            return f"{formatted}{suffix}{CURRENCY_SYMBOL}"
    
    return f"{amount}{CURRENCY_SYMBOL}"

def parse_amount(text: str, balance: int) -> tuple[int | None, str]:
    if text.lower() == "allin":
        return (balance, "") if balance > 0 else (None, "Bakiyeniz yetersiz.")
    
    text = text.lower().replace(",", "").replace(".", "").strip()
    
    muls = {
        "k": 10**3, "m": 10**6, "b": 10**9, "t": 10**12, 
        "q": 10**15, "qt": 10**18, "sx": 10**21, "sp": 10**24
    }
    
    try:
        if len(text) > 2 and text[-2:] in muls:
            val = int(text[:-2]) * muls[text[-2:]]
        elif text[-1] in muls:
            val = int(text[:-1]) * muls[text[-1]]
        else:
            val = int(text)
    except (ValueError, IndexError):
        return None, "Geçersiz miktar. Örn: 100k, 5m, 1qt"
        
    if val <= 0:
        return None, "Miktar 0'dan büyük olmalı."
    if val > balance:
        return None, f"Yetersiz bakiye. Bakiyeniz: {format_amount(balance)}"
    return val, ""

async def get_or_create_user(uid: int, username, name: str) -> dict:
    db = await get_db()
    
    async with await _get_lock(uid):
        user = await db.users.find_one({"telegram_id": uid})
        
        if user is None:
            user_data = {
                "telegram_id": uid,
                "username": username,
                "display_name": name,
                "balance": STARTING_BALANCE,
                "total_wagered": 0,
                "total_won": 0,
                "games_played": 0,
                "last_daily": None,
                "daily_streak": 0,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            await db.users.insert_one(user_data)
            
            await db.transactions.insert_one({
                "to_id": uid,
                "amount": STARTING_BALANCE,
                "type": "bonus",
                "description": "Başlangıç",
                "created_at": datetime.now()
            })
            
            user = await db.users.find_one({"telegram_id": uid})
        else:
            if username != user.get("username") or name != user.get("display_name"):
                await db.users.update_one(
                    {"telegram_id": uid},
                    {"$set": {"username": username, "display_name": name, "updated_at": datetime.now()}}
                )
                user = await db.users.find_one({"telegram_id": uid})
    
    return dict(user)

async def get_user(uid: int) -> dict | None:
    db = await get_db()
    user = await db.users.find_one({"telegram_id": uid})
    return dict(user) if user else None

async def get_balance(uid: int) -> int:
    u = await get_user(uid)
    return u["balance"] if u else 0

async def add_balance(uid: int, amount: int, tx_type="win", desc="") -> bool:
    if amount <= 0:
        return False
    
    db = await get_db()
    lock = await _get_lock(uid)
    
    async with lock:
        result = await db.users.update_one(
            {"telegram_id": uid},
            {"$inc": {"balance": amount}, "$set": {"updated_at": datetime.now()}}
        )
        
        if result.modified_count > 0:
            await db.transactions.insert_one({
                "to_id": uid,
                "amount": amount,
                "type": tx_type,
                "description": desc,
                "created_at": datetime.now()
            })
            return True
    
    return False

async def remove_balance(uid: int, amount: int, tx_type="bet", desc="") -> bool:
    if amount <= 0:
        return False
    
    db = await get_db()
    lock = await _get_lock(uid)
    
    async with lock:
        user = await db.users.find_one({"telegram_id": uid})
        
        if not user or user["balance"] < amount:
            return False
        
        await db.users.update_one(
            {"telegram_id": uid},
            {"$inc": {"balance": -amount, "total_wagered": amount}, "$set": {"updated_at": datetime.now()}}
        )
        
        await db.transactions.insert_one({
            "from_id": uid,
            "amount": amount,
            "type": tx_type,
            "description": desc,
            "created_at": datetime.now()
        })
        
        return True

async def update_stats(uid: int, won: int):
    db = await get_db()
    
    async with await _get_lock(uid):
        await db.users.update_one(
            {"telegram_id": uid},
            {"$inc": {"total_won": won, "games_played": 1}, "$set": {"updated_at": datetime.now()}}
        )
        
        
        
async def update_win_rate(uid: int, game_type: str, won: bool):
    """Win rate güncelle - Minimal versiyon"""
    try:
        db = await get_db()
        
        # Basitçe sayıları artır
        if won:
            await db.user_stats.update_one(
                {"telegram_id": uid},
                {"$inc": {f"{game_type}_total": 1, f"{game_type}_wins": 1}},
                upsert=True
            )
        else:
            await db.user_stats.update_one(
                {"telegram_id": uid},
                {"$inc": {f"{game_type}_total": 1}},
                upsert=True
            )
    except Exception as e:
        logger.error(f"Win rate güncellenemedi: {e}")
        # Hata olursa sessizce geç, bot çalışmaya devam etsin
    
            

async def get_leaderboard(limit=15) -> list[dict]:
    db = await get_db()
    cursor = db.users.find().sort("balance", -1).limit(limit)
    users = await cursor.to_list(length=limit)
    return users
    
    
# ═══════════════════════════════════════════════════════════════
#  STATE MANAGER & OYUN YÖNETİMİ (MONGODB)
# ═══════════════════════════════════════════════════════════════

import uuid
import time
import json

_active_games: dict[int, dict[str, dict]] = {}
_state_lock = asyncio.Lock()

async def can_open_game(chat_id: int, game_type: str) -> tuple[bool, str]:
    async with _state_lock:
        games = _active_games.get(chat_id, {})
        active = [g for g in games.values() if g["state"] != "FINISHED"]
        if len(active) >= MAX_OPEN_GAMES:
            return False, f"Bu grupta zaten {MAX_OPEN_GAMES} aktif oyun var."
        if any(g["game_type"] == game_type for g in active):
            return False, f"Bu grupta zaten açık bir {game_type} oyunu var."
        return True, ""

async def create_game(chat_id: int, game_type: str, message_id: int = 0) -> dict:
    game_id = str(uuid.uuid4())[:8].upper()
    game = {
        "game_id": game_id,
        "chat_id": chat_id,
        "game_type": game_type,
        "state": "OPEN",
        "message_id": message_id,
        "participants": {},
        "result": None,
        "task": None,
    }
    
    async with _state_lock:
        _active_games.setdefault(chat_id, {})[game_id] = game
    
    db = await get_db()
    await db.games.insert_one({
        "game_id": game_id,
        "chat_id": chat_id,
        "game_type": game_type,
        "state": "OPEN",
        "message_id": message_id,
        "result": None,
        "created_at": datetime.now(),
        "finished_at": None
    })
    
    return game

async def get_active_game(chat_id: int, game_type: str) -> dict | None:
    async with _state_lock:
        for g in _active_games.get(chat_id, {}).values():
            if g["game_type"] == game_type and g["state"] != "FINISHED":
                return g
    return None

async def add_participant(chat_id: int, game_id: str, uid: int, bet: int, bet_data: dict):
    """Oyuncu bahislerini EKLE"""
    async with _state_lock:
        game = _active_games.get(chat_id, {}).get(game_id)
        if not game:
            return
        
        if uid in game["participants"]:
            game["participants"][uid]["bet"] += bet
            
            existing_data = game["participants"][uid]["bet_data"]
            existing_type = existing_data.get("type")
            new_type = bet_data.get("type")
            
            if existing_type and new_type and existing_type == new_type:
                if new_type == "color":
                    if "color" in existing_data and existing_data["color"]:
                        colors = [existing_data["color"]]
                        existing_data.pop("color", None)
                    else:
                        colors = existing_data.get("colors", [])
                    
                    if bet_data["color"] not in colors:
                        colors.append(bet_data["color"])
                    
                    existing_data["colors"] = colors
                    existing_data["name"] = bet_data["name"]
                    existing_data["type"] = "color"
                    
                elif new_type == "number":
                    if "numbers" not in existing_data:
                        existing_data["numbers"] = []
                    existing_data["numbers"].extend(bet_data["numbers"])
                    existing_data["numbers"] = list(set(existing_data["numbers"]))
                    existing_data["name"] = bet_data["name"]
                    existing_data["type"] = "number"
            
            game["participants"][uid]["bet_data"] = existing_data
        else:
            game["participants"][uid] = {"bet": bet, "bet_data": bet_data}
    
    # MongoDB güncelleme
    db = await get_db()
    participant = await db.game_participants.find_one({"game_id": game_id, "telegram_id": uid})
    
    if participant:
        old_bet = participant["bet_amount"]
        new_total_bet = old_bet + bet
        await db.game_participants.update_one(
            {"_id": participant["_id"]},
            {"$set": {"bet_amount": new_total_bet}}
        )
    else:
        await db.game_participants.insert_one({
            "game_id": game_id,
            "telegram_id": uid,
            "bet_amount": bet,
            "bet_data": bet_data,
            "payout": 0,
            "created_at": datetime.now()
        })

async def get_participants(chat_id: int, game_id: str) -> dict:
    async with _state_lock:
        game = _active_games.get(chat_id, {}).get(game_id)
        return dict(game["participants"]) if game else {}

async def finish_game(chat_id: int, game_id: str, result: str = ""):
    async with _state_lock:
        if game_id in _active_games.get(chat_id, {}):
            _active_games[chat_id][game_id]["state"] = "FINISHED"
    
    db = await get_db()
    await db.games.update_one(
        {"game_id": game_id},
        {"$set": {"state": "FINISHED", "result": result, "finished_at": datetime.now()}}
    )

async def cleanup(chat_id: int):
    async with _state_lock:
        if chat_id in _active_games:
            _active_games[chat_id] = {
                gid: g for gid, g in _active_games[chat_id].items()
                if g["state"] != "FINISHED"
            }
            
            
            
            
# ═══════════════════════════════════════════════════════════════
#  RATE LIMITER
# ═══════════════════════════════════════════════════════════════

_last_cmd: dict[int, float] = {}

def is_rate_limited(uid: int) -> bool:
    now = time.monotonic()
    if now - _last_cmd.get(uid, 0) < RATE_LIMIT_SECONDS:
        return True
    _last_cmd[uid] = now
    return False
    
    
    
    
# ═══════════════════════════════════════════════════════════════
#  GENEL KOMUTLAR
# ═══════════════════════════════════════════════════════════════

_lb_cache: dict = {"data": None, "ts": 0}

def clean_name(name: str) -> str:
    """Sadece harf, rakam ve boşluk bırakır (Görselde hata vermemesi için)"""
    cleaned = re.sub(r'[^a-zA-Z0-9ğüşıöçĞÜŞİÖÇ\s]', '', name)
    return cleaned.strip()

async def get_display_name(uid: int) -> str:
    """Kullanıcının görünen ismini temizlenmiş halde getirir (MongoDB)"""
    u = await get_user(uid)
    if u and u.get('display_name'):
        return clean_name(u['display_name'])
    return str(uid)

def create_transfer_image(sender: str, receiver: str, amount: int) -> io.BytesIO:
    """Transfer görseli - İtalik + Gölgeli"""
    
    transfer_template = os.path.join(BASE_DIR, "transfer.png")
    
    if not os.path.exists(transfer_template):
        raise FileNotFoundError(f"Transfer şablonu bulunamadı: {transfer_template}")
    
    img = Image.open(transfer_template).convert('RGBA')
    img.thumbnail((800, 600), Image.Resampling.LANCZOS)
    
    width, height = img.size
    txt_layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)
    
    # ✅ İTALİK fontlar yükle
    try:
        # İtalik Bold font dene
        font_isim = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf", int(height * 0.10))
        font_miktar = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf", int(height * 0.13))
        font_token = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf", int(height * 0.067))
    except:
        # Fallback
        font_isim = get_font(int(height * 0.10))
        font_miktar = get_font(int(height * 0.13))
        font_token = get_font(int(height * 0.067))
    
    # ✅ Mat altın renk (görseldeki gibi)
    gold_color = "#B8860B"  # Koyu altın
    shadow_color = "#4a3a1a"  # Koyu gölge
    
    # İsimler (beyaz)
    draw.text((width * 0.57, height * 0.19), sender, fill="#F5F5F5", font=font_isim, anchor="mm")
    draw.text((width * 0.57, height * 0.53), receiver, fill="#F5F5F5", font=font_isim, anchor="mm")
    
    # Miktar (gölgeli altın)
    amount_text = format_amount(amount).replace(CURRENCY_SYMBOL, "").strip()
    
    # Önce gölge (biraz sağda-aşağıda)
    draw.text((width * 0.47 + 3, height * 0.86 + 3), amount_text, fill=shadow_color, font=font_miktar, anchor="lm")
    # Sonra asıl yazı
    draw.text((width * 0.47, height * 0.86), amount_text, fill=gold_color, font=font_miktar, anchor="lm")
    
    # Token yazısı (gölgeli)
    try:
        text_w = draw.textlength(amount_text, font=font_miktar)
        # Gölge
        draw.text((width * 0.47 + text_w + 20 + 3, height * 0.87 + 3), "Token", fill=shadow_color, font=font_token, anchor="lm")
        # Asıl yazı
        draw.text((width * 0.47 + text_w + 20, height * 0.87), "Token", fill=gold_color, font=font_token, anchor="lm")
    except:
        pass
    
    img = Image.alpha_composite(img, txt_layer).convert('RGB')
    bio = io.BytesIO()
    img.save(bio, format='PNG', quality=95)
    bio.seek(0)
    return bio


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Başlangıç komutu - Kullanıcıyı kaydeder"""
    user = update.effective_user
    
    # Kullanıcıyı oluştur veya getir
    u = await get_or_create_user(user.id, user.username, user.full_name)
    lvl, emoji = get_level(u["balance"])
    
    await update.message.reply_text(
        f"🎰 <b>CasiniBot'a Hoş Geldiniz!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{user.full_name}</b> [{lvl}] {emoji}\n"
        f"💳 Başlangıç bakiyeniz: {format_amount(u['balance'])}\n\n"
        f"🍀 Bol şans!\n"
        f"📌 Komutlar için /help\n"
        f"🎮 Oyunlar için /menu",
        parse_mode="HTML"
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Yardım komutu"""
    help_text = (
        "🎰 <b>CASİNİBOT KOMUTLAR</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👤 <b>HESAP</b>\n"
        "/start — Kayıt / Hoş geldin\n"
        "/balance — Bakiyeni göster\n"
        "/daily — Günlük bonus\n"
        "/moneys — Para gönder\n"
        "/leaderboard — Liderlik tablosu\n\n"
        "🎡 <b>RULET</b>\n"
        "/rulet — Rulet başlat\n"
        "/red /black /green /number\n\n"
        "🃏 <b>BLACKJACK</b>\n"
        "/blackjack — Başlat\n"
        "/bj — Bahis yap\n\n"
        "🎲 <b>ZAR (PvP)</b>\n"
        "/dicebet — Başlat\n"
        "/dice — Katıl\n\n"
        "🎡 <b>ÇARKIFELEK</b>\n"
        "/wheelbet — Başlat\n"
        "/wheel — Bahis\n\n"
        "🎟 <b>KAZI KAZAN</b>\n"
        "/kazisolo — Tek kişilik\n"
        "/kazibet — Turnuva\n\n"
        "💰 <b>SATIN AL</b>\n"
        "/buy — Stars ile satın al"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")


async def cmd_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Bakiye sorgula - Oyun istatistikleriyle"""
    user = update.effective_user
    if is_rate_limited(user.id): return
    
    u = await get_user(user.id)
    if not u:
        await update.message.reply_text("❌ Kullanıcı bulunamadı. /start yazın.")
        return
    
    lvl, emoji = get_level(u["balance"])
    
    # Oyun istatistiklerini al
    db = await get_db()
    stats = await db.user_stats.find_one({"telegram_id": user.id})
    
    if not stats:
        # İstatistik yoksa varsayılan değerler
        rulet_win_rate = 0
        blackjack_win_rate = 0
        dice_win_rate = 0
        wheel_win_rate = 0
        scratch_win_rate = 0
        total_win_rate = 0
    else:
        # Her oyun için kazanma oranı (% olarak)
        rulet_win_rate = stats.get("rulet_win_rate", 0)
        blackjack_win_rate = stats.get("blackjack_win_rate", 0)
        dice_win_rate = stats.get("dice_win_rate", 0)
        wheel_win_rate = stats.get("wheel_win_rate", 0)
        scratch_win_rate = stats.get("scratch_win_rate", 0)
        
        # Genel toplam kazanma oranı
        total_win_rate = stats.get("total_win_rate", 0)
    
    await update.message.reply_text(
        f"📌 <b>Verilerim</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {user.full_name}\n"
        f"🤴 Seviye {lvl} {emoji}\n"
        f"🏧 Bakiye {format_amount(u['balance'])} 🪙\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Oyun İstatistikleri</b>\n"
        f"🎡 Rulet: %{rulet_win_rate}\n"
        f"🃏 Blackjack: %{blackjack_win_rate}\n"
        f"🎲 Zar: %{dice_win_rate}\n"
        f"🎡 Çarkıfelek: %{wheel_win_rate}\n"
        f"🎟 Kazı Kazan: %{scratch_win_rate}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 <b>Toplam Kazanma Oranı: %{total_win_rate}</b>",
        parse_mode="HTML"
    )


async def cmd_changename(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """İsim değiştir"""
    user = update.effective_user
    if is_rate_limited(user.id): return
    
    if not ctx.args:
        await update.message.reply_text("✏️ Kullanım: /changename <yeni isim>")
        return
    
    name = " ".join(ctx.args)[:32]
    if len(name) < 2:
        await update.message.reply_text("❌ En az 2 karakter.")
        return
    
    db = await get_db()
    await db.users.update_one(
        {"telegram_id": user.id},
        {"$set": {"display_name": name}}
    )
    await update.message.reply_text(f"✅ İsminiz <b>{name}</b> olarak güncellendi!", parse_mode="HTML")


async def cmd_moneys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Para transferi - Görselli"""
    user = update.effective_user
    
    if is_rate_limited(user.id):
        return
    
    args = ctx.args
    reply = update.message.reply_to_message
    
    target = None
    amount_str = ""
    
    if reply:
        target = reply.from_user
        amount_str = args[0] if args else ""
    elif len(args) >= 2 and args[0].startswith("@"):
        username = args[0][1:]
        db = await get_db()
        user_data = await db.users.find_one({"username": username})
        if not user_data:
            await update.message.reply_text("❌ Kullanıcı bulunamadı.")
            return
        target = type('User', (), {'id': user_data['telegram_id'], 'full_name': user_data['display_name']})()
        amount_str = args[1]
    elif len(args) >= 2:
        try:
            target_id = int(args[0])
            db = await get_db()
            user_data = await db.users.find_one({"telegram_id": target_id})
            if not user_data:
                await update.message.reply_text("❌ Kullanıcı bulunamadı.")
                return
            target = type('User', (), {'id': user_data['telegram_id'], 'full_name': user_data['display_name']})()
            amount_str = args[1]
        except:
            await update.message.reply_text("❌ Kullanım: /moneys <@kullanici> <miktar>")
            return
    else:
        await update.message.reply_text("❌ Kullanım: /moneys <@kullanici> <miktar>")
        return
    
    await get_or_create_user(user.id, user.username, user.full_name)
    bal = await get_balance(user.id)
    amount, err = parse_amount(amount_str, bal)
    if err:
        await update.message.reply_text(f"❌ {err}")
        return
    
    if amount > bal:
        await update.message.reply_text(f"❌ Yetersiz bakiye! Mevcut: {format_amount(bal)}")
        return
    
    db = await get_db()
    
    # Transfer işlemi
    await db.users.update_one({"telegram_id": user.id}, {"$inc": {"balance": -amount}})
    await db.users.update_one({"telegram_id": target.id}, {"$inc": {"balance": amount}})
    
    await db.transactions.insert_one({
        "from_id": user.id,
        "to_id": target.id,
        "amount": amount,
        "type": "transfer",
        "created_at": datetime.now()
    })
    
    new_bal = await get_balance(user.id)
    
    # Görsel göndermeyi dene
    try:
        sender_name = clean_name(user.full_name)
        receiver_name = clean_name(target.full_name)
        transfer_img = create_transfer_image(sender_name, receiver_name, amount)
        
        await update.message.reply_photo(
            photo=transfer_img,
            caption=f"✅ <b>Transfer Başarılı!</b>\n💰 {format_amount(amount)}\n💳 Yeni bakiyeniz: {format_amount(new_bal)}",
            parse_mode="HTML"
        )
    except:
        # Görsel yoksa normal mesaj
        await update.message.reply_text(
            f"✅ <b>Transfer Başarılı!</b>\n"
            f"📤 {user.full_name} → 📥 {target.full_name}\n"
            f"💰 {format_amount(amount)}\n"
            f"💳 Yeni bakiyeniz: {format_amount(new_bal)}",
            parse_mode="HTML"
        )


async def cmd_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Liderlik tablosu"""
    if is_rate_limited(update.effective_user.id): return
    
    rows = await get_leaderboard(LEADERBOARD_SIZE)
    
    # Grup adını buradan al (örnek: ctx.bot.username veya sabit)
    group_name = "Casino Bot"  # Burayı grubun adıyla değiştir
    
    # Token birimi
    token_symbol = "🪙"  # Burayı istediğin sembolle değiştir
    
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"🏆 {group_name} En Zengin 10 Kullanıcı 🏆", "━━━━━━━━━━━━━━━━━━━━━"]
    
    for i, r in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i+1}️⃣"
        name = r.get("display_name", "Bilinmeyen")[:15]
        balance = r['balance']
        lvl, emoji = get_level(balance)
        lines.append(f"{medal} {name} ❇️  {format_amount(balance)} {token_symbol} {emoji}{lvl}")
    
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    
    
# ═══════════════════════════════════════════════════════════════
#  GÜNLÜK BONUS
# ═══════════════════════════════════════════════════════════════

def get_daily_bonus(streak: int) -> int:
    if streak < 0:
        streak = 0
    streak = min(streak, 10)
    return 50000 * (2 ** streak)

def can_claim_daily(last_daily: str) -> tuple[bool, int]:
    if not last_daily:
        return True, 0
    
    last = datetime.fromisoformat(last_daily)
    now = datetime.now()
    delta = now - last
    
    if delta.days >= 1:
        return True, 0
    else:
        hours_left = 24 - delta.seconds // 3600
        return False, hours_left

async def cmd_daily(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if is_rate_limited(user.id):
        return
    
    u = await get_or_create_user(user.id, user.username, user.full_name)
    db = await get_db()
    lock = await _get_lock(user.id)
    
    async with lock:
        user_data = await db.users.find_one({"telegram_id": user.id})
        last_daily = user_data.get("last_daily")
        current_streak = user_data.get("daily_streak", 0)
        
        can_claim, hours_left = can_claim_daily(last_daily)
        
        if not can_claim:
            await update.message.reply_text(
                f"⏰ <b>Günlük bonusunuzu zaten aldınız!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎁 Sonraki bonus: <b>{hours_left} saat</b> sonra\n"
                f"📈 Mevcut seri: <b>{current_streak} gün</b>",
                parse_mode="HTML"
            )
            return
        
        new_streak = current_streak + 1
        bonus_amount = get_daily_bonus(current_streak)
        
        await db.users.update_one(
            {"telegram_id": user.id},
            {"$inc": {"balance": bonus_amount},
             "$set": {"last_daily": datetime.now().isoformat(), "daily_streak": new_streak, "updated_at": datetime.now()}}
        )
        
        await db.transactions.insert_one({
            "to_id": user.id,
            "amount": bonus_amount,
            "type": "daily",
            "description": f"{new_streak}. gün bonusu",
            "created_at": datetime.now()
        })
        
        new_balance = await get_balance(user.id)
        next_bonus = get_daily_bonus(new_streak)
        
        await update.message.reply_text(
            f"🎁 <b>GÜNLÜK BONUS!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>{user.full_name}</b>\n"
            f"📅 Seri: <b>{new_streak}</b> gün\n"
            f"💰 Kazanılan: <b>+{format_amount(bonus_amount)}</b>\n"
            f"💳 Yeni bakiye: <b>{format_amount(new_balance)}</b>\n\n"
            f"🎯 Yarınki bonus: <b>{format_amount(next_bonus)}</b>",
            parse_mode="HTML"
        )
        
        
        
        
# ═══════════════════════════════════════════════════════════════
#  RULET (TAMAMEN YENİ - ÇOKLU BAHİS DESTEKLİ)
# ═══════════════════════════════════════════════════════════════

def format_number_with_emoji(number: int) -> str:
    emoji_digits = {
        '0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
        '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'
    }
    return ''.join(emoji_digits[d] for d in str(number))

def get_rank_emoji(rank: int) -> str:
    if rank == 1:
        return "🥇"
    elif rank == 2:
        return "🥈"
    elif rank == 3:
        return "🥉"
    else:
        return "📍"

def get_roulette_image(number: int) -> str:
    img_path = os.path.join(BASE_DIR, f"{number}.jpg")
    if not os.path.exists(img_path):
        spin_path = os.path.join(BASE_DIR, "spin.jpg")
        if os.path.exists(spin_path):
            img_path = spin_path
    return img_path

async def cmd_rulet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if is_rate_limited(user.id): return
    
    ok, err = await can_open_game(chat_id, "roulette")
    if not ok:
        await update.message.reply_text(f"❌ {err}")
        return
    
    # Önce oyunu oluştur (game_id almak için)
    game = await create_game(chat_id, "roulette", 0)
    
    spin_img_path = os.path.join(BASE_DIR, "spin.jpg")
    caption = (
        f"🎰 <b>AVRUPA RULETİ BAŞLADI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 GAME ID: <code>{game['game_id']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>{BET_WINDOW} saniye</b> içinde bahis yapın!\n\n"
        f"🔴 /red &lt;miktar&gt;\n"
        f"⚫ /black &lt;miktar&gt;\n"
        f"🟢 /green &lt;miktar&gt;\n"
        f"🔢 /number &lt;sayı 0-36&gt; &lt;miktar&gt;\n"
        f"🔢 /numbers &lt;1,2,3,...&gt; &lt;miktar&gt;\n\n"
        f"💡 Aynı oyuna istediğiniz kadar bahis yapabilirsiniz!"
    )
    
    try:
        if os.path.exists(spin_img_path):
            with open(spin_img_path, "rb") as photo:
                msg = await update.message.reply_photo(photo=photo, caption=caption, parse_mode="HTML")
        else:
            msg = await update.message.reply_text(caption, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Spin görseli gönderilemedi: {e}")
        msg = await update.message.reply_text(caption, parse_mode="HTML")
    
    # Mesaj ID'sini güncelle
    async with _state_lock:
        if chat_id in _active_games and game['game_id'] in _active_games[chat_id]:
            _active_games[chat_id][game['game_id']]['message_id'] = msg.message_id
    
    await asyncio.create_task(_roulette_timer(ctx, chat_id, game["game_id"], msg))
async def _roulette_timer(ctx, chat_id, game_id, msg):
    await asyncio.sleep(BET_WINDOW)
    game = await get_active_game(chat_id, "roulette")
    if not game or game["game_id"] != game_id: 
        return
    game["state"] = "CALCULATING"
    
    winning = random.randint(0, 36)
    color = ROUL_COLORS[winning]
    color_emoji = ROUL_EMOJI[color]
    
    try:
        await ctx.bot.delete_message(chat_id, msg.message_id)
    except BadRequest:
        pass
    
    parts = await get_participants(chat_id, game_id)
    winner_list = []
    total_payout = 0
    
    for uid, data in parts.items():
        bet_data_list = data.get("bet_data_list", [])
        total_bet = data["bet"]
        
        if not bet_data_list:
            # Eski format tek bahis
            bd = data["bet_data"]
            bet_data_list = [bd]
        
        player_name = data["bet_data"].get('name', 'Bilinmeyen')
        player_won = False
        player_payout = 0
        
        for single_bet in bet_data_list:
            bet_amount = single_bet.get("bet_amount", total_bet // len(bet_data_list))
            payout = 0
            
            if single_bet.get("type") == "color":
                if single_bet.get("color") == color:
                    multiplier = ROULETTE_MULTIPLIERS[color]
                    payout = bet_amount * multiplier
                    player_payout += payout
                    player_won = True
                    
            elif single_bet.get("type") == "number":
                if winning in single_bet.get("numbers", []):
                    per_number_bet = bet_amount // len(single_bet["numbers"])
                    multiplier = ROULETTE_MULTIPLIERS["number"]
                    payout = per_number_bet * multiplier
                    player_payout += payout
                    player_won = True
        
        if player_payout > 0:
            await add_balance(uid, player_payout, "win", f"Rulet game:{game_id}")
            await update_stats(uid, player_payout)
            total_payout += player_payout
            winner_list.append((player_name, color, player_payout))
        
        await update_win_rate(uid, "roulette", player_won)
    
    # Sonuç mesajı
    result_text = f"🆔 GAME ID: <code>{game_id}</code>\n"
    result_text += f"━━━━━━━━━━━━━━━━━━━━━\n"
    result_text += f"🏆 Kazanan Sayı: {format_number_with_emoji(winning)} {color_emoji}\n"
    result_text += f"━━━━━━━━━━━━━━━━━━━━━\n"
    
    if winner_list:
        result_text += f"🏧 <b>KAZANANLAR</b>\n"
        for i, (name, win_color, payout) in enumerate(winner_list[:15], 1):
            rank_emoji = get_rank_emoji(i)
            result_text += f"{rank_emoji} {name} {color_emoji} {format_amount(payout)}🪙\n"
        result_text += f"━━━━━━━━━━━━━━━━━━━━━\n"
        result_text += f"💰 Toplam Dağıtılan: {format_amount(total_payout)}🪙\n"
    else:
        result_text += f"💀 <b>Kazanan olmadı!</b>\n"
    
    try:
        img_path = get_roulette_image(winning)
        if os.path.exists(img_path):
            with open(img_path, "rb") as photo:
                await ctx.bot.send_photo(chat_id, photo=photo, caption=result_text, parse_mode="HTML")
        else:
            await ctx.bot.send_message(chat_id, result_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Rulet sonuç görseli gönderilemedi: {e}")
        await ctx.bot.send_message(chat_id, result_text, parse_mode="HTML")
    
    await finish_game(chat_id, game_id, str(winning))
    await cleanup(chat_id)

async def _rulet_bet(update: Update, bet_type: str, color=None, numbers=None, amount_str="0"):
    user = update.effective_user
    chat_id = update.effective_chat.id
    if is_rate_limited(user.id): 
        return
    
    await get_or_create_user(user.id, user.username, user.full_name)
    bal = await get_balance(user.id)
    amount, err = parse_amount(amount_str, bal)
    if err:
        await update.message.reply_text(f"❌ {err}")
        return
    
    game = await get_active_game(chat_id, "roulette")
    if not game or game["state"] != "OPEN":
        await update.message.reply_text("❌ Açık rulet yok veya süre doldu.")
        return
    
    ok = await remove_balance(user.id, amount, "bet", f"Rulet game:{game['game_id']}")
    if not ok:
        await update.message.reply_text("❌ Yetersiz bakiye.")
        return
    
    if bet_type == "color":
        bd = {
            "type": "color", 
            "color": color, 
            "numbers": [], 
            "name": user.full_name,
            "bet_amount": amount
        }
        color_emoji = {"red": "🔴", "black": "⚫", "green": "🟢"}.get(color, "🔵")
    else:
        bd = {
            "type": "number", 
            "color": None, 
            "numbers": numbers or [], 
            "name": user.full_name,
            "bet_amount": amount
        }
        color_emoji = "🔵"
    
    await add_participant_multi(chat_id, game["game_id"], user.id, amount, bd)
    
    await update.message.reply_text(
        f"🕹 <b>{user.full_name}</b> {color_emoji} {format_amount(amount)}🪙 bahis yaptı",
        parse_mode="HTML"
    )

async def add_participant_multi(chat_id: int, game_id: str, uid: int, bet: int, bet_data: dict):
    """Çoklu bahis destekli katılımcı ekleme"""
    async with _state_lock:
        game = _active_games.get(chat_id, {}).get(game_id)
        if not game:
            return
        
        if uid not in game["participants"]:
            # İlk bahis
            game["participants"][uid] = {
                "bet": bet,
                "bet_data": bet_data,
                "bet_data_list": [bet_data]
            }
        else:
            # Ek bahis
            existing = game["participants"][uid]
            existing["bet"] += bet
            
            if "bet_data_list" not in existing:
                existing["bet_data_list"] = [existing["bet_data"]]
            existing["bet_data_list"].append(bet_data)
    
    # MongoDB güncelleme
    db = await get_db()
    participant = await db.game_participants.find_one({"game_id": game_id, "telegram_id": uid})
    
    if participant:
        await db.game_participants.update_one(
            {"_id": participant["_id"]},
            {"$inc": {"bet_amount": bet}}
        )
    else:
        await db.game_participants.insert_one({
            "game_id": game_id,
            "telegram_id": uid,
            "bet_amount": bet,
            "bet_data": bet_data,
            "payout": 0,
            "created_at": datetime.now()
        })

# Rulet komutları
async def cmd_green(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _rulet_bet(update, "color", color="green", amount_str=ctx.args[0] if ctx.args else "0")

async def cmd_red(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _rulet_bet(update, "color", color="red", amount_str=ctx.args[0] if ctx.args else "0")

async def cmd_black(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _rulet_bet(update, "color", color="black", amount_str=ctx.args[0] if ctx.args else "0")

async def cmd_number(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("❌ Kullanım: /number <sayı> <miktar>")
        return
    try:
        n = int(ctx.args[0])
        if 0 <= n <= 36:
            await _rulet_bet(update, "number", numbers=[n], amount_str=ctx.args[1])
        else:
            await update.message.reply_text("❌ Geçersiz sayı (0-36).")
    except:
        await update.message.reply_text("❌ Geçersiz sayı (0-36).")

async def cmd_numbers(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("❌ Kullanım: /numbers <1,2,3> <miktar>")
        return
    try:
        nums = [int(x.strip()) for x in ctx.args[0].split(",")]
        if not all(0 <= n <= 36 for n in nums) or len(nums) < 2:
            await update.message.reply_text("❌ Geçersiz sayı listesi.")
            return
    except:
        await update.message.reply_text("❌ Geçersiz sayı listesi.")
        return
    await _rulet_bet(update, "number", numbers=nums, amount_str=ctx.args[1])
    
    
# ═══════════════════════════════════════════════════════════════
#  VIP KASA (STARS SATIN ALMA)
# ═══════════════════════════════════════════════════════════════

async def cmd_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for stars, config in STARS_CONFIG.items():
        keyboard.append([
            InlineKeyboardButton(
                f"🌟 {stars} Stars → {config['label']} {format_amount(config['coin'])}🪙",
                callback_data=f"buy_{stars}"
            )
        ])
    
    await update.message.reply_text(
        "🌟 <b>VIP KASA - Telegram Stars ile Satın Al</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Aşağıdaki paketlerden birini seçin:\n\n"
        "💡 Telegram Stars satın almak için: @PremiumBot\n"
        "⚠️ Bu sanal oyun parasıdır, gerçek para değeri yoktur.\n"
        "✅ Satın alınca coinler anında hesabınıza eklenir!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def buy_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    stars = int(query.data.split("_")[1])
    config = STARS_CONFIG[stars]
    coin_amount = config["coin"]
    user = query.from_user
    
    await ctx.bot.send_invoice(
        chat_id=user.id,
        title=f"{stars} Telegram Stars",
        description=f"{config['label']} - {format_amount(coin_amount)}🪙",
        payload=f"stars_{stars}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{stars} Stars", amount=stars)],
        start_parameter="vip_kasa",
        need_name=False,
        need_phone_number=False,
        need_email=False
    )

async def pre_checkout_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    payload = update.message.successful_payment.invoice_payload
    stars = int(payload.split("_")[1])
    
    coin_amount = STARS_CONFIG[stars]["coin"]
    
    await add_balance(user.id, coin_amount, "stars_purchase", f"{stars} Stars ile VIP Kasa")
    new_balance = await get_balance(user.id)
    
    await update.message.reply_text(
        f"✅ <b>SATIN ALMA BAŞARILI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌟 {stars} Stars → {format_amount(coin_amount)}🪙\n"
        f"💰 Yeni bakiyeniz: {format_amount(new_balance)}\n\n"
        f"🎉 İyi eğlenceler!",
        parse_mode="HTML"
    )
    
    
# ═══════════════════════════════════════════════════════════════
#  BLACKJACK - TAM FONKSİYONLAR (MongoDB)
# ═══════════════════════════════════════════════════════════════

_bj: Dict[int, dict] = {}

def get_card_image(card: tuple) -> Image.Image:
    rank, suit = card
    rank_map = {"A": "ace", "2": "2", "3": "3", "4": "4", "5": "5", "6": "6", "7": "7", "8": "8", "9": "9", "10": "10", "J": "jack", "Q": "queen", "K": "king"}
    suit_map = {"♠️": "spades", "♥️": "hearts", "♦️": "diamonds", "♣️": "clubs"}
    filename = f"{rank_map.get(rank, rank)}_of_{suit_map.get(suit, 'spades')}.png"
    img_path = os.path.join(BASE_DIR, filename)
    
    if os.path.exists(img_path):
        img = Image.open(img_path)
        img = img.resize((CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS)
        return img
    return Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), color='#2c2c2c')
def get_face_down_card() -> Image.Image:
    back_path = os.path.join(BJ_IMG_PATH, "back.png")
    if os.path.exists(back_path):
        img = Image.open(back_path)
        img = img.resize((CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS)
        return img
    return Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), color='#2c2c2c')

def combine_cards(cards: list) -> io.BytesIO:
    if not cards:
        return None
    total_width = len(cards) * CARD_WIDTH
    combined = Image.new('RGB', (total_width, CARD_HEIGHT), color='#1a1a2e')
    for i, card in enumerate(cards):
        combined.paste(get_card_image(card), (i * CARD_WIDTH, 0))
    bio = io.BytesIO()
    combined.save(bio, format='PNG')
    bio.seek(0)
    return bio

def combine_cards_with_hidden(cards: list) -> io.BytesIO:
    if not cards:
        return None
    total_width = len(cards) * CARD_WIDTH
    combined = Image.new('RGB', (total_width, CARD_HEIGHT), color='#1a1a2e')
    combined.paste(get_face_down_card(), (0, 0))
    for i, card in enumerate(cards[1:], 1):
        combined.paste(get_card_image(card), (i * CARD_WIDTH, 0))
    bio = io.BytesIO()
    combined.save(bio, format='PNG')
    bio.seek(0)
    return bio

def _new_deck() -> List[Tuple[str, str]]:
    deck = [(r, s) for r in RANKS for s in SUITS]
    random.shuffle(deck)
    return deck

def _card_val(rank: str) -> int:
    if rank in ("J", "Q", "K"):
        return 10
    if rank == "A":
        return 11
    return int(rank)

def _hand_val(hand: List[Tuple[str, str]]) -> int:
    total = sum(_card_val(r) for r, s in hand)
    aces = sum(1 for r, s in hand if r == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

def hand_to_emoji(hand: list) -> str:
    if not hand:
        return "❌"
    result = []
    for r, s in hand:
        suit_emoji = {"♠️": "♠", "♥️": "♥", "♦️": "♦", "♣️": "♣"}.get(s, s)
        result.append(f"{r}{suit_emoji}")
    return " ".join(result)

def _bj_kb(game_id: str):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🃏 Hit", callback_data=f"bj_hit:{game_id}"),
        InlineKeyboardButton("✋ Stand", callback_data=f"bj_stand:{game_id}"),
    ]])

async def cmd_blackjack(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if is_rate_limited(user.id): return
    ok, err = await can_open_game(chat_id, "blackjack")
    if not ok:
        await update.message.reply_text(f"❌ {err}")
        return
    msg = await update.message.reply_text(
        f"🃏 <b>BLACKJACK BAŞLADI!</b>\n━━━━━━━━━━━━━━━━━━━━━\n⏱ <b>{BET_WINDOW} saniye</b> içinde bahis yapın!\n\n📌 /bj &lt;miktar&gt;\n• 21'i geç → kaybedersin\n• Kurpiyer 17'de durur\n• Kazanırsan 2x alırsın",
        parse_mode="HTML"
    )
    game = await create_game(chat_id, "blackjack", msg.message_id)
    gid = game["game_id"]
    _bj[chat_id] = {"game_id": gid, "state": "BETTING", "players": {}, "order": [], "dealer": [], "deck": [], "current": 0}
    asyncio.create_task(_bj_bet_timer(ctx, chat_id, gid))

async def cmd_bj(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    bj = _bj.get(chat_id)
    if not bj or bj["state"] != "BETTING":
        await update.message.reply_text("❌ Açık blackjack yok veya bahis süresi doldu.")
        return
    if not ctx.args:
        await update.message.reply_text("❌ Kullanım: /bj <miktar>")
        return
    await get_or_create_user(user.id, user.username, user.full_name)
    bal = await get_balance(user.id)
    amount, err = parse_amount(ctx.args[0], bal)
    if err:
        await update.message.reply_text(f"❌ {err}")
        return
    ok = await remove_balance(user.id, amount, "bet", f"BJ game:{bj['game_id']}")
    if not ok:
        await update.message.reply_text("❌ Yetersiz bakiye.")
        return
    if user.id in bj["players"]:
        bj["players"][user.id]["bet"] += amount
        await update.message.reply_text(f"🕹 <b>{user.full_name}</b> 🃏 +{format_amount(amount)}🪙 (Toplam: {format_amount(bj['players'][user.id]['bet'])})", parse_mode="HTML")
    else:
        bj["players"][user.id] = {"bet": amount, "hand": [], "state": "WAITING", "name": user.full_name}
        bj["order"].append(user.id)
        await update.message.reply_text(f"🕹 <b>{user.full_name}</b> 🃏 {format_amount(amount)}🪙 bahis yaptı", parse_mode="HTML")

async def _bj_bet_timer(ctx, chat_id, game_id):
    await asyncio.sleep(BET_WINDOW)
    bj = _bj.get(chat_id)
    if not bj or bj["game_id"] != game_id:
        return
    if not bj["players"]:
        await ctx.bot.send_message(chat_id, "❌ Blackjack iptal — kimse katılmadı.")
        await finish_game(chat_id, game_id, "iptal")
        await cleanup(chat_id)
        return
    
    bj["state"] = "DEALING"
    deck = _new_deck()
    bj["deck"] = deck
    
    # Kartları dağıt
    for uid in bj["order"]:
        bj["players"][uid]["hand"] = [deck.pop(), deck.pop()]
        bj["players"][uid]["state"] = "PLAYING"
        bj["players"][uid]["cards_sent"] = False  # Yeni: kart gönderilmedi olarak işaretle
    
    bj["dealer"] = [deck.pop(), deck.pop()]
    bj["current"] = 0
    
    # Kurpiyerin açık kartını göster
    dealer_img = combine_cards_with_hidden(bj["dealer"])
    first_card_value = _card_val(bj["dealer"][0][0])
    await ctx.bot.send_photo(
        chat_id, 
        photo=dealer_img, 
        caption=f"🎩 <b>KURPİYER</b>\n━━━━━━━━━━━━━━━━━━━━━\nAçık kart: {first_card_value}\nKapalı kart: ?",
        parse_mode="HTML"
    )
    
    # Oyuncuların kartlarını göster
    for uid in bj["order"]:
        p = bj["players"][uid]
        hand_img = combine_cards(p["hand"])
        await ctx.bot.send_photo(
            chat_id, 
            photo=hand_img, 
            caption=f"🃏 <b>{p['name']}</b>\n━━━━━━━━━━━━━━━━━━━━━\n🃏 Eliniz: {_hand_val(p['hand'])}",
            parse_mode="HTML"
        )
        p["cards_sent"] = True  # Kartlar gönderildi olarak işaretle
    
    await _bj_next(ctx, chat_id, game_id)

async def _bj_next(ctx, chat_id, game_id):
    bj = _bj.get(chat_id)
    if not bj or bj["game_id"] != game_id:
        return
    
    if bj["current"] >= len(bj["order"]):
        await _bj_dealer(ctx, chat_id, game_id)
        return
    
    uid = bj["order"][bj["current"]]
    p = bj["players"][uid]
    
    if p["state"] != "PLAYING":
        bj["current"] += 1
        await _bj_next(ctx, chat_id, game_id)
        return
    
    val = _hand_val(p["hand"])
    
    # Sadece ilk kez kartları göster
    if not p.get("cards_sent", False):
        hand_img = combine_cards(p["hand"])
        await ctx.bot.send_photo(
            chat_id, 
            photo=hand_img, 
            caption=f"🃏 <b>{p['name']}</b>\n━━━━━━━━━━━━━━━━━━━━━\n🃏 Eliniz: {val}",
            reply_markup=_bj_kb(game_id),
            parse_mode="HTML"
        )
        p["cards_sent"] = True
    else:
        # Sonraki turlarda sadece mesaj gönder
        await ctx.bot.send_message(
            chat_id,
            f"🃏 <b>{p['name']}</b> sırası!\n━━━━━━━━━━━━━━━━━━━━━\n🃏 Eliniz: {val}\n\n⏱ {BLACKJACK_TURN} saniyen var!",
            reply_markup=_bj_kb(game_id),
            parse_mode="HTML"
        )
    
    p["task"] = asyncio.create_task(_bj_timeout(ctx, chat_id, game_id, uid))
    
async def _bj_timeout(ctx, chat_id, game_id, uid):
    await asyncio.sleep(BLACKJACK_TURN)
    bj = _bj.get(chat_id)
    if not bj or bj["game_id"] != game_id:
        return
    p = bj["players"].get(uid)
    if not p or p["state"] != "PLAYING":
        return
    p["state"] = "STAND"
    bj["current"] += 1
    await _bj_next(ctx, chat_id, game_id)

async def bj_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        action, game_id = query.data.split(":", 1)
    except:
        await query.answer("Hata!", show_alert=True)
        return
    
    user = query.from_user
    chat_id = query.message.chat_id
    bj = _bj.get(chat_id)
    
    if not bj or bj["game_id"] != game_id:
        await query.answer("Oyun bitti.", show_alert=True)
        return
    
    if bj["current"] >= len(bj["order"]) or bj["order"][bj["current"]] != user.id:
        await query.answer("Şu an sıranız değil!", show_alert=True)
        return
    
    p = bj["players"].get(user.id)
    if not p or p["state"] != "PLAYING":
        await query.answer("Sıranız bitti.", show_alert=True)
        return
    
    # Zamanlayıcıyı iptal et
    if p.get("task"):
        p["task"].cancel()
    
    if action == "bj_hit":
        # Yeni kart çek
        card = bj["deck"].pop()
        p["hand"].append(card)
        val = _hand_val(p["hand"])
        
        # Kart görselini oluştur
        hand_img = combine_cards(p["hand"])
        
        if val > 21:
            # BUST - Kaybetti
            await query.edit_message_media(
                media=InputMediaPhoto(
                    media=hand_img,
                    caption=f"💥 <b>BUST!</b>\n━━━━━━━━━━━━━━━━━━━━━\n👤 {p['name']}\n🃏 Eliniz: {val}\n❌ Kaybettiniz!",
                    parse_mode="HTML"
                )
            )
            p["state"] = "BUST"
            bj["current"] += 1
            await _bj_next(ctx, chat_id, game_id)
            
        elif val == 21:
            # Blackjack - Otomatik stand
            await query.edit_message_media(
                media=InputMediaPhoto(
                    media=hand_img,
                    caption=f"🎉 <b>BLACKJACK! 21</b>\n━━━━━━━━━━━━━━━━━━━━━\n👤 {p['name']}\n✅ Otomatik Stand",
                    parse_mode="HTML"
                )
            )
            p["state"] = "STAND"
            bj["current"] += 1
            await _bj_next(ctx, chat_id, game_id)
            
        else:
            # Devam ediyor - mevcut mesajı düzenle
            await query.edit_message_media(
                media=InputMediaPhoto(
                    media=hand_img,
                    caption=f"🃏 <b>SIRA SENDE</b>\n━━━━━━━━━━━━━━━━━━━━━\n👤 {p['name']}\n🃏 Eliniz: {val}\n⏳ {BLACKJACK_TURN} saniyen var!",
                    parse_mode="HTML"
                ),
                reply_markup=_bj_kb(game_id)
            )
            # Yeni zamanlayıcı başlat
            p["task"] = asyncio.create_task(_bj_timeout(ctx, chat_id, game_id, user.id))
    
    elif action == "bj_stand":
        hand_val = _hand_val(p["hand"])
        p["state"] = "STAND"
        bj["current"] += 1
        
        # Stand yaptığını göster - fotoğrafı düzenle
        hand_img = combine_cards(p["hand"])
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=hand_img,
                caption=f"✋ <b>STAND</b>\n━━━━━━━━━━━━━━━━━━━━━\n👤 {p['name']}\n🃏 Eliniz: {hand_val} ile durdu.",
                parse_mode="HTML"
            )
        )
        await _bj_next(ctx, chat_id, game_id)

async def _bj_dealer(ctx, chat_id, game_id):
    bj = _bj.get(chat_id)
    if not bj or bj["game_id"] != game_id:
        return
    hand = bj["dealer"]
    while _hand_val(hand) < 17:
        hand.append(bj["deck"].pop())
    dval = _hand_val(hand)
    dealer_img = combine_cards(hand)
    await ctx.bot.send_photo(chat_id, photo=dealer_img, caption=f"🎩 KURPİYER\n━━━━━━━━━━━━━━━━━━━━━\n📊 Toplam: {dval}", parse_mode="HTML")
    results = ["🏁 BLACKJACK - FİNAL TABLOSU", "━━━━━━━━━━━━━━━━━━━━━"]
    total_payout = 0
    for uid in bj["order"]:
        p = bj["players"][uid]
        pval = _hand_val(p["hand"])
        bet = p["bet"]
        if p["state"] == "BUST":
            results.append(f"❌ {p['name']}: {pval} (BUST) → -{format_amount(bet)}")
            # ⬇️ KAYIP için win rate güncelle ⬇️
            await update_win_rate(uid, "blackjack", False)
        elif dval > 21:
            payout = bet * 2
            await add_balance(uid, payout, "win", f"BJ game:{game_id}")
            await update_stats(uid, payout)
            total_payout += payout
            results.append(f"✅ {p['name']}: {pval} vs {dval} (BUST) → +{format_amount(payout)}")
            # ⬇️ KAZANÇ için win rate güncelle ⬇️
            await update_win_rate(uid, "blackjack", True)
        elif pval > dval:
            payout = bet * 2
            await add_balance(uid, payout, "win", f"BJ game:{game_id}")
            await update_stats(uid, payout)
            total_payout += payout
            results.append(f"✅ {p['name']}: {pval} vs {dval} → +{format_amount(payout)}")
            # ⬇️ KAZANÇ için win rate güncelle ⬇️
            await update_win_rate(uid, "blackjack", True)
        elif pval == dval:
            await add_balance(uid, bet, "refund", f"BJ game:{game_id}")
            results.append(f"🤝 {p['name']}: {pval} vs {dval} → İADE")
            # ⬇️ BERABERLİKTE HİÇBİR ŞEY YAPMA! ⬇️
            pass
        else:
            results.append(f"❌ {p['name']}: {pval} vs {dval} → -{format_amount(bet)}")
            # ⬇️ KAYIP için win rate güncelle ⬇️
            await update_win_rate(uid, "blackjack", False)
    results.append("━━━━━━━━━━━━━━━━━━━━━")
    results.append(f"🏧 DAĞITILAN TOPLAM: {format_amount(total_payout)}")
    results.append("✨ Yeni oyun için /blackjack yazın!")
    await ctx.bot.send_message(chat_id, "\n".join(results), parse_mode="HTML")
    del _bj[chat_id]
    await finish_game(chat_id, game_id, f"dealer:{dval}")
    await cleanup(chat_id)


# ═══════════════════════════════════════════════════════════════
#  ZAR OYUNU (PvP)
# ═══════════════════════════════════════════════════════════════

async def cmd_dicebet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if is_rate_limited(user.id): return
    
    ok, err = await can_open_game(chat_id, "dice")
    if not ok:
        await update.message.reply_text(f"❌ {err}")
        return
    
    msg = await update.message.reply_text(
        f"🎲 <b>ZAR OYUNU BAŞLADI! (PvP)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>{BET_WINDOW} saniye</b> içinde katılın!\n\n"
        f"📌 /dice &lt;miktar&gt; veya /dice allin\n"
        f"🎯 En yüksek zar toplamı kazanır!\n"
        f"🤝 Beraberlikte havuz bölüşülür.",
        parse_mode="HTML")
    
    game = await create_game(chat_id, "dice", msg.message_id)
    asyncio.create_task(_dice_bet_timer(ctx, chat_id, game["game_id"]))

async def cmd_dice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    if is_rate_limited(user.id): return
    
    if not ctx.args:
        await update.message.reply_text("❌ Kullanım: /dice <miktar>")
        return
    
    await get_or_create_user(user.id, user.username, user.full_name)
    bal = await get_balance(user.id)
    amount, err = parse_amount(ctx.args[0], bal)
    if err:
        await update.message.reply_text(f"❌ {err}")
        return
    
    game = await get_active_game(chat_id, "dice")
    if not game or game["state"] != "OPEN":
        await update.message.reply_text("❌ Açık zar oyunu yok.")
        return
    
    parts = await get_participants(chat_id, game["game_id"])
    if not parts:
        game["min_bet"] = amount
    elif amount < game.get("min_bet", 0):
        await update.message.reply_text(f"❌ En az {format_amount(game['min_bet'])} gerekli.")
        return
    
    ok = await remove_balance(user.id, amount, "bet", f"Zar game:{game['game_id']}")
    if not ok:
        await update.message.reply_text("❌ Yetersiz bakiye.")
        return
    
    await add_participant(chat_id, game["game_id"], user.id, amount, {"name": user.full_name})
    bal = await get_balance(user.id)
    count = len(await get_participants(chat_id, game["game_id"]))
    
    await update.message.reply_text(
        f"🎲 <b>{user.full_name}</b> — {format_amount(amount)} katıldı!\n"
        f"👥 Oyuncu: {count} | 💳 {format_amount(bal)}",
        parse_mode="HTML")

async def _dice_bet_timer(ctx, chat_id, game_id):
    await asyncio.sleep(BET_WINDOW)
    
    game = await get_active_game(chat_id, "dice")
    if not game or game["game_id"] != game_id:
        return
    
    parts = await get_participants(chat_id, game_id)
    
    if len(parts) < 2:
        await ctx.bot.send_message(
            chat_id, 
            "❌ <b>Zar oyunu iptal!</b>\nEn az 2 oyuncu gerekli. Bahisler iade edildi.",
            parse_mode="HTML")
        for uid, data in parts.items():
            await add_balance(uid, data["bet"], "refund", f"Zar iade game:{game_id}")
        await finish_game(chat_id, game_id, "iptal")
        await cleanup(chat_id)
        return
    
    game["state"] = "ROLLING"
    game["order"] = list(parts.keys())
    game["players_rolled"] = {}
    game["current_player_index"] = 0
    game["pool"] = sum(data["bet"] for data in parts.values())
    game["participants_data"] = parts
    
    await _dice_next_player(ctx, chat_id, game_id)

async def _dice_next_player(ctx, chat_id, game_id):
    game = await get_active_game(chat_id, "dice")
    if not game or game["game_id"] != game_id:
        return
    
    idx = game["current_player_index"]
    order = game["order"]
    
    if idx >= len(order):
        await _dice_calculate_results(ctx, chat_id, game_id)
        return
    
    uid = order[idx]
    parts = game["participants_data"]
    player_name = parts[uid]["bet_data"]["name"]
    
    # Zar at
    dice1 = random.randint(1, 6)
    dice2 = random.randint(1, 6)
    total = dice1 + dice2
    
    game["players_rolled"][uid] = {
        "total": total,
        "dice1": dice1,
        "dice2": dice2,
        "name": player_name,
        "bet": parts[uid]["bet"]
    }
    
    await ctx.bot.send_message(
        chat_id,
        f"🎲 <b>{player_name}</b> zar attı!\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎲 {dice1} + {dice2} = <b>{total}</b>",
        parse_mode="HTML"
    )
    
    game["current_player_index"] += 1
    await asyncio.sleep(2)  # Her atış arasında 2 saniye bekle
    await _dice_next_player(ctx, chat_id, game_id)

async def _dice_calculate_results(ctx, chat_id, game_id):
    game = await get_active_game(chat_id, "dice")
    if not game or game["game_id"] != game_id:
        return
    
    players = game["players_rolled"]
    pool = game["pool"]
    
    # En yüksek skoru bul
    max_score = max(p["total"] for p in players.values())
    
    # En yüksek skoru yapanları bul
    winners = [(uid, data) for uid, data in players.items() if data["total"] == max_score]
    
    # Kazananlara ödeme yap
    prize_per_winner = pool // len(winners)
    remaining = pool - (prize_per_winner * len(winners))
    
    results = ["🎲 <b>ZAR OYUNU SONUÇLARI</b>", "━━━━━━━━━━━━━━━━━━━━━"]
    
    # Tüm oyuncuların skorlarını göster
    for uid, data in players.items():
        results.append(f"🎲 {data['name']}: {data['total']}")
    
    results.append("━━━━━━━━━━━━━━━━━━━━━")
    
    if len(winners) == 1:
        uid, data = winners[0]
        payout = prize_per_winner + remaining
        await add_balance(uid, payout, "win", f"Zar game:{game_id}")
        await update_stats(uid, payout)
        await update_win_rate(uid, "dice", True)
        
        results.append(f"🏆 <b>KAZANAN: {data['name']}</b>")
        results.append(f"💰 Kazanç: {format_amount(payout)}")
        
        # Diğer oyuncular kaybetti
        for uid2, data2 in players.items():
            if uid2 != uid:
                await update_win_rate(uid2, "dice", False)
    else:
        # Beraberlik - havuz bölüşülüyor
        results.append(f"🤝 <b>BERABERLİK! {len(winners)} kazanan</b>")
        for uid, data in winners:
            await add_balance(uid, prize_per_winner, "win", f"Zar game:{game_id} (beraberlik)")
            await update_stats(uid, prize_per_winner)
            await update_win_rate(uid, "dice", True)
            results.append(f"💰 {data['name']}: +{format_amount(prize_per_winner)}")
        
        # Kaybedenler için
        for uid2, data2 in players.items():
            if uid2 not in [w[0] for w in winners]:
                await update_win_rate(uid2, "dice", False)
        
        if remaining > 0:
            results.append(f"📦 Kalan: {format_amount(remaining)} (sistemde kaldı)")
    
    results.append("━━━━━━━━━━━━━━━━━━━━━")
    results.append("✨ Yeni oyun için /dicebet")
    
    await ctx.bot.send_message(chat_id, "\n".join(results), parse_mode="HTML")
    
    await finish_game(chat_id, game_id, f"kazanan:{len(winners)}")
    await cleanup(chat_id)
    
    
    
    
# ═══════════════════════════════════════════════════════════════
#  KAZI KAZAN - MONGODB UYUMLU
# ═══════════════════════════════════════════════════════════════

# ✅ Görsel yolları düzeltildi - BASE_DIR kullanıyor
KAPALI_KART_PATH = os.path.join(BASE_DIR, "Kapali.jpg")
ACIK_KART_PATH = os.path.join(BASE_DIR, "acik.jpg")

def create_scratch_result_image(board: list, winner_mult: int) -> io.BytesIO:
    """Açık kart görseline sonuçları yaz - GÖRSELİ KÜÇÜLT"""
    
    acik_kart = os.path.join(BASE_DIR, "acik.jpg")
    
    if not os.path.exists(acik_kart):
        raise Exception(f"Açık kart görseli bulunamadı: {acik_kart}")
    
    # Görseli AÇ
    img = Image.open(acik_kart)
    
    # ✅ Görseli KÜÇÜLT (telefonda çözülen yöntem)
    img.thumbnail((800, 600), Image.Resampling.LANCZOS)
    
    draw = ImageDraw.Draw(img)
    
    # Font bul (artık küçük görselde büyük durur)
    font = get_font(100)  # 120 bile yeterli olabilir
    
    # Görselin yeni boyutları
    width, height = img.size
    print(f"📐 Yeni görsel boyutu: {width}x{height}")
    
    # Koordinatları yeniden hesapla (görsel küçüldü)
    boxes = [
        {"center": (width * 0.16, height * 0.25), "index": 0},   # 170/1080 ≈ 0.16
        {"center": (width * 0.51, height * 0.25), "index": 1},   # 550/1080 ≈ 0.51
        {"center": (width * 0.83, height * 0.25), "index": 2},   # 900/1080 ≈ 0.83
        {"center": (width * 0.16, height * 0.69), "index": 3},   # 170/1080, 550/800 ≈ 0.69
        {"center": (width * 0.51, height * 0.69), "index": 4},
        {"center": (width * 0.83, height * 0.69), "index": 5},
    ]
    
    for box in boxes:
        center_x = int(box["center"][0])
        center_y = int(box["center"][1])
        value = board[box["index"]]
        
        if value == winner_mult and winner_mult > 0:
            text_color = (0, 255, 0)
        elif value == 0:
            text_color = (255, 0, 0)
        else:
            text_color = (255, 255, 255)
        
        text = f"{value}x"
        
        # Yazıyı ortala
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        
        draw.text(
            (center_x - tw/2, center_y - th/2),
            text,
            fill=text_color,
            font=font,
            stroke_width=3,
            stroke_fill=(0, 0, 0)
        )
    
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    return bio


async def cmd_kazisolo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Tek kişilik Kazı Kazan - MongoDB uyumlu"""
    user = update.effective_user
    if is_rate_limited(user.id):
        return
    
    if not ctx.args:
        await update.message.reply_text(
            "🎟 <b>KAZI KAZAN (SOLO)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "📌 Kullanım: <code>/kazisolo &lt;miktar&gt;</code>\n"
            "veya <code>/kazisolo allin</code>\n\n"
            "🏆 3 aynı çarpan = KAZANÇ!",
            parse_mode="HTML"
        )
        return
    
    await get_or_create_user(user.id, user.username, user.full_name)
    bal = await get_balance(user.id)
    amount, err = parse_amount(ctx.args[0], bal)
    if err:
        await update.message.reply_text(f"❌ {err}")
        return
    
    # Bahsi düş
    ok = await remove_balance(user.id, amount, "bet", "Kazı Kazan Solo")
    if not ok:
        await update.message.reply_text("❌ Yetersiz bakiye.")
        return
    
    # Başlangıç görseli (kapalı kart)
    kapali_kart = os.path.join(BASE_DIR, "Kapali.jpg")
    if os.path.exists(kapali_kart):
        with open(kapali_kart, "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=f"🎟 <b>KAZI KAZAN (SOLO)</b>\n━━━━━━━━━━━━━━━━━━━━━\n💰 Bahis: {format_amount(amount)}\n✨ KAZIYORSUN... ✨",
                parse_mode="HTML"
            )
    else:
        await update.message.reply_text(
            f"🎟 <b>KAZI KAZAN (SOLO)</b>\n━━━━━━━━━━━━━━━━━━━━━\n💰 Bahis: {format_amount(amount)}\n✨ KAZIYORSUN... ✨",
            parse_mode="HTML"
        )
    
    await asyncio.sleep(1.5)
    
    # Kazı Kazan mantığı
    board = [secrets.choice(SCRATCH_POOL) for _ in range(6)]
    counts = Counter(board)
    winner_mult = 0
    for mult, count in counts.most_common():
        if count >= 3 and mult > 0:
            winner_mult = mult
            break

    try:
        result_img = create_scratch_result_image(board, winner_mult)
        payout = amount * winner_mult if winner_mult > 0 else 0
        
        if winner_mult > 0:
            await add_balance(user.id, payout, "win", f"Kazı Solo {winner_mult}x")
            await update_stats(user.id, payout)
            msg = f"✅ <b>{winner_mult}x</b> bulundu!\n🎉 KAZANDIN! +{format_amount(payout - amount)}"
            await update_win_rate(user.id, "scratch", True)
        else:
            await update_stats(user.id, 0)
            msg = f"❌ Eşleşme yok!\n💀 KAYBETTİN! -{format_amount(amount)}"
            await update_win_rate(user.id, "scratch", False)
        
        new_bal = await get_balance(user.id)
        
        await update.message.reply_photo(
            photo=result_img,
            caption=f"🎟 <b>KAZI KAZAN (SOLO)</b>\n━━━━━━━━━━━━━━━━━━━━━\n{msg}\n💳 Yeni bakiye: {format_amount(new_bal)}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Kazı Kazan görsel hatası: {e}")
        new_bal = await get_balance(user.id)
        if winner_mult > 0:
            await add_balance(user.id, payout, "win", f"Kazı Solo {winner_mult}x")
            await update_stats(user.id, payout)
            await update_win_rate(user.id, "scratch", True)
            await update.message.reply_text(
                f"🎟 <b>KAZI KAZAN (SOLO)</b>\n━━━━━━━━━━━━━━━━━━━━━\n✅ {winner_mult}x bulundu!\n🎉 KAZANDIN! +{format_amount(payout - amount)}\n💳 Yeni bakiye: {format_amount(new_bal)}",
                parse_mode="HTML"
            )
        else:
            await update_stats(user.id, 0)
            await update_win_rate(user.id, "scratch", False)
            await update.message.reply_text(
                f"🎟 <b>KAZI KAZAN (SOLO)</b>\n━━━━━━━━━━━━━━━━━━━━━\n❌ Eşleşme yok!\n💀 KAYBETTİN! -{format_amount(amount)}",
                parse_mode="HTML"
        )

    
                                                             # ← 8 boşluk
    
        
        


async def cmd_kazibet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Kazı Kazan Turnuvası başlat"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    if is_rate_limited(user.id):
        return
    
    ok, err = await can_open_game(chat_id, "scratch_tournament")
    if not ok:
        await update.message.reply_text(f"❌ {err}")
        return
    
    caption = (
        f"🎟 <b>KAZI KAZAN TURNUVASI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>{BET_WINDOW} saniye</b> içinde katıl!\n"
        f"📌 /kazi &lt;miktar&gt;\n"
        f"🎯 Herkes aynı kartı kazır!\n"
        f"🏆 3 aynı çarpan = HERKES KAZANIR!"
    )
    
    kapali_kart = os.path.join(BASE_DIR, "Kapali.jpg")
    if os.path.exists(kapali_kart):
        with open(kapali_kart, "rb") as photo:
            msg = await update.message.reply_photo(photo=photo, caption=caption, parse_mode="HTML")
    else:
        msg = await update.message.reply_text(caption, parse_mode="HTML")
    
    game = await create_game(chat_id, "scratch_tournament", msg.message_id)
    
    # Oyun verilerini sakla
    async with _state_lock:
        if chat_id in _active_games and game["game_id"] in _active_games[chat_id]:
            _active_games[chat_id][game["game_id"]]["min_bet"] = 0
            _active_games[chat_id][game["game_id"]]["pool"] = 0
            _active_games[chat_id][game["game_id"]]["players"] = {}
    
    asyncio.create_task(_scratch_countdown(ctx, chat_id, game["game_id"], msg.message_id))
    asyncio.create_task(_scratch_tournament_timer(ctx, chat_id, game["game_id"]))


async def cmd_kazi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Kazı Kazan Turnuvasına katıl"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    if is_rate_limited(user.id):
        return
    
    if not ctx.args:
        await update.message.reply_text("❌ Kullanım: /kazi <miktar>")
        return
    
    game = await get_active_game(chat_id, "scratch_tournament")
    if not game or game["state"] != "OPEN":
        await update.message.reply_text("❌ Açık turnuva yok.")
        return
    
    await get_or_create_user(user.id, user.username, user.full_name)
    bal = await get_balance(user.id)
    amount, err = parse_amount(ctx.args[0], bal)
    if err:
        await update.message.reply_text(f"❌ {err}")
        return
    
    # Oyun verilerini al
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game["game_id"])
        if not game_data:
            await update.message.reply_text("❌ Oyun bulunamadı.")
            return
        
        players = game_data.get("players", {})
        min_bet = game_data.get("min_bet", 0)
        
        if not players:
            game_data["min_bet"] = amount
        elif amount < min_bet:
            await update.message.reply_text(f"❌ Minimum bahis: {format_amount(min_bet)}")
            return
    
    # Bahsi düş
    ok = await remove_balance(user.id, amount, "bet", f"Kazi Turnuva {game['game_id']}")
    if not ok:
        await update.message.reply_text("❌ Yetersiz bakiye.")
        return
    
    # Oyuncuyu ekle
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game["game_id"])
        if game_data:
            if user.id in game_data["players"]:
                game_data["players"][user.id]["bet"] += amount
            else:
                game_data["players"][user.id] = {"bet": amount, "name": user.full_name}
            game_data["pool"] = game_data.get("pool", 0) + amount
    
    await update.message.reply_text(
        f"🕹 <b>{user.full_name}</b> 🎟️ {format_amount(amount)} ile katıldı.",
        parse_mode="HTML"
    )


async def _scratch_countdown(ctx, chat_id, game_id, message_id):
    """Gerisayım"""
    for remaining in range(BET_WINDOW, 0, -5):
        await asyncio.sleep(5)
        game = await get_active_game(chat_id, "scratch_tournament")
        if not game or game["game_id"] != game_id or game["state"] != "OPEN":
            return
        
        async with _state_lock:
            game_data = _active_games.get(chat_id, {}).get(game_id)
            if not game_data:
                return
            players_count = len(game_data.get("players", {}))
            pool = game_data.get("pool", 0)
        
        try:
            await ctx.bot.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=f"🎟 <b>KAZI KAZAN TURNUVASI</b>\n━━━━━━━━━━━━━━━━━━━━━\n⏱ Kalan: {remaining} sn\n👥 Katılımcı: {players_count}\n💰 Havuz: {format_amount(pool)}",
                parse_mode="HTML"
            )
        except:
            pass


async def _scratch_tournament_timer(ctx, chat_id, game_id):
    """Turnuva sonucu hesapla"""
    await asyncio.sleep(BET_WINDOW)
    
    game = await get_active_game(chat_id, "scratch_tournament")
    if not game or game["game_id"] != game_id:
        return
    
    # Oyuncuları al
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data:
            return
        players = game_data.get("players", {}).copy()
    
    if len(players) < 2:
        # İade yap
        for uid, d in players.items():
            await add_balance(uid, d["bet"], "refund", "Kazi Turnuva İptal")
        await ctx.bot.send_message(
            chat_id,
            "❌ <b>KAZI KAZAN TURNUVASI İPTAL!</b>\nEn az 2 oyuncu gerekli. Bahisler iade edildi.",
            parse_mode="HTML"
        )
        await finish_game(chat_id, game_id, "iptal")
        await cleanup(chat_id)
        return
    
    # Kartları oluştur
    board = [secrets.choice(SCRATCH_POOL) for _ in range(6)]
    counts = Counter(board)
    winner_mult = 0
    for mult, count in counts.most_common():
        if count >= 3 and mult > 0:
            winner_mult = mult
            break
    
    try:
        result_img = create_scratch_result_image(board, winner_mult)
        lines = [f"🎟 <b>KAZI KAZAN SONUCU</b>", "━━━━━━━━━━━━━━━━━━━━━"]
        
        if winner_mult > 0:
            lines.append(f"✅ <b>{winner_mult}x</b> eşleşmesi bulundu!\n🎉 <b>HERKES KAZANDI!</b>\n")
            total_payout = 0
            for uid, d in players.items():
                payout = d["bet"] * winner_mult
                await add_balance(uid, payout, "win", f"Kazi Turnuva {winner_mult}x")
                await update_stats(uid, payout)
                lines.append(f"✅ {d['name']}: +{format_amount(payout - d['bet'])}")
                total_payout += payout
                await update_win_rate(uid, "scratch", True)
            lines.append(f"\n💰 Toplam dağıtılan: {format_amount(total_payout)}")
        else:
            lines.append(f"❌ Eşleşme yok!\n😢 <b>HERKES KAYBETTİ!</b>\n")
            for uid, d in players.items():
                await update_stats(uid, 0)
                lines.append(f"❌ {d['name']}: -{format_amount(d['bet'])}")
                await update_win_rate(uid, "scratch", False)
        
        await ctx.bot.send_photo(
            chat_id,
            photo=result_img,
            caption="\n".join(lines),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Kazi turnuva görsel hatası: {e}")
        # Görsel hatasında mesaj olarak gönder
        msg = f"🎟 <b>KAZI KAZAN SONUCU</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
        if winner_mult > 0:
            msg += f"✅ {winner_mult}x eşleşmesi! HERKES KAZANDI!\n"
            for uid, d in players.items():
                payout = d["bet"] * winner_mult
                await add_balance(uid, payout, "win", f"Kazi Turnuva {winner_mult}x")
                await update_stats(uid, payout)
                msg += f"✅ {d['name']}: +{format_amount(payout)}\n"
        else:
            msg += f"❌ Eşleşme yok! HERKES KAYBETTİ!\n"
        await ctx.bot.send_message(chat_id, msg, parse_mode="HTML")
    
    await finish_game(chat_id, game_id, "kazikazan")
    await cleanup(chat_id)
        
    
    
# ═══════════════════════════════════════════════════════════════
#  ÇARKIFELEK
# ═══════════════════════════════════════════════════════════════

async def cmd_wheelbet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if is_rate_limited(user.id): return
    
    ok, err = await can_open_game(chat_id, "wheel")
    if not ok:
        await update.message.reply_text(f"❌ {err}")
        return
    
    msg = await update.message.reply_text(
        f"🎡 <b>ÇARKIFELEK BAŞLADI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>{BET_WINDOW} saniye</b>\n\n"
        f"📌 /wheel &lt;miktar&gt; veya /wheel allin\n\n"
        f"💀 PASS | 🔄 İADE | 2x | 3x | 5x | 10x | 15x | 25x | 50x | 100x",
        parse_mode="HTML")
    
    game = await create_game(chat_id, "wheel", msg.message_id)
    asyncio.create_task(_wheel_timer(ctx, chat_id, game["game_id"]))

async def cmd_wheel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    if is_rate_limited(user.id): return
    
    if not ctx.args:
        await update.message.reply_text("❌ Kullanım: /wheel <miktar>")
        return
    
    await get_or_create_user(user.id, user.username, user.full_name)
    bal = await get_balance(user.id)
    amount, err = parse_amount(ctx.args[0], bal)
    if err:
        await update.message.reply_text(f"❌ {err}")
        return
    
    game = await get_active_game(chat_id, "wheel")
    if not game or game["state"] != "OPEN":
        await update.message.reply_text("❌ Açık çarkıfelek yok.")
        return
    
    ok = await remove_balance(user.id, amount, "bet", f"Çark game:{game['game_id']}")
    if not ok:
        await update.message.reply_text("❌ Yetersiz bakiye.")
        return
    
    await add_participant(chat_id, game["game_id"], user.id, amount, {"name": user.full_name})
    bal = await get_balance(user.id)
    
    await update.message.reply_text(
        f"🕹 <b>{user.full_name}</b> 🎡 {format_amount(amount)}🪙 bahis yaptı",
        parse_mode="HTML")

async def _wheel_timer(ctx, chat_id, game_id):
    await asyncio.sleep(BET_WINDOW)
    
    game = await get_active_game(chat_id, "wheel")
    if not game or game["game_id"] != game_id:
        return
    
    game["state"] = "CALCULATING"
    
    # Her oyunda rastgele karıştır (tahmin edilemez olması için)
    shuffled_segments = random.sample(WHEEL_SEGMENTS, len(WHEEL_SEGMENTS))
    label, mult = secrets.choice(shuffled_segments)
    parts = await get_participants(chat_id, game_id)
    
    lines = [f"🎡 <b>ÇARK DÖNDÜ!</b>", f"━━━━━━━━━━━━━━━━━━━━━",
             f"🎯 Sonuç: <b>{label}</b>", f"🆔 <code>{game_id}</code>", ""]
    
    total_payout = 0
    
    if not parts:
        lines.append("😴 Kimse bahis yapmadı.")
    elif mult == 0:
        # PASS - tam kayıp
        lines.append("💀 <b>PASS!</b> Herkes kaybetti.")
        for uid, d in parts.items():
            await update_stats(uid, 0)
            await update_win_rate(uid, "wheel", False)
            lines.append(f"  ❌ {d['bet_data']['name']} -{format_amount(d['bet'])}")
    elif mult == 1:
        # İADE - bahis iade
        lines.append("🔄 <b>İADE!</b> Bahisler geri ödendi.")
        for uid, d in parts.items():
            await add_balance(uid, d["bet"], "refund", f"Çark iade game:{game_id}")
            await update_stats(uid, 0)
            await update_win_rate(uid, "wheel", True)  # İade de kazanç sayılıyor
            lines.append(f"  🔄 {d['bet_data']['name']} +0 (iade)")
    else:
        # Kazanç var
        lines.append(f"🏆 <b>{label} ({mult}x)</b>")
        for uid, d in parts.items():
            payout = d["bet"] * mult
            await add_balance(uid, payout, "win", f"Çark game:{game_id}")
            await update_stats(uid, payout)
            await update_win_rate(uid, "wheel", True)
            total_payout += payout
            lines.append(f"  ✅ {d['bet_data']['name']} +{format_amount(payout - d['bet'])}")
    
    if mult > 0 and mult != 1:
        lines.append(f"\n💰 Toplam dağıtılan: {format_amount(total_payout)}")
    
    await ctx.bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")
    await finish_game(chat_id, game_id, label)
    await cleanup(chat_id)
    
    
# ═══════════════════════════════════════════════════════════════
#  ADMIN KOMUTLARI
# ═══════════════════════════════════════════════════════════════

async def cmd_addbalance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin komutu - Kullanıcıya bakiye ekle
    
    Kullanım şekilleri:
    1. /addbalance 1000000  (kendine)
    2. /addbalance 123456789 1000000  (ID ile)
    3. Reply yaparak: /addbalance 1000000  (yanıtlanan kişiye)
    """
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Bu komutu kullanma yetkiniz yok!")
        return
    
    args = ctx.args
    target_id = None
    amount_str = None
    
    # Kullanım şeklini belirle
    if update.message.reply_to_message:
        # REPLY ile kullanım: /addbalance 1000000
        target_id = update.message.reply_to_message.from_user.id
        amount_str = args[0] if args else None
    elif len(args) == 1:
        # Sadece miktar yazıldı: /addbalance 1000000 (kendine)
        target_id = user.id
        amount_str = args[0]
    elif len(args) >= 2:
        # ID ve miktar: /addbalance 123456789 1000000
        try:
            target_id = int(args[0])
            amount_str = args[1]
        except:
            await update.message.reply_text("❌ Geçersiz kullanıcı ID'si!")
            return
    else:
        await update.message.reply_text(
            "💸 <b>KULLANIM ŞEKİLLERİ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"1️⃣ Kendine ekle: /addbalance 1000000\n"
            f"2️⃣ ID ile ekle: /addbalance 123456789 1000000\n"
            f"3️⃣ Reply ile ekle: (mesajı yanıtla) /addbalance 1000000",
            parse_mode="HTML"
        )
        return
    
    # Miktarı kontrol et
    if not amount_str:
        await update.message.reply_text("❌ Miktar belirtilmedi!")
        return
    
    # Miktarı parse et (admin olduğu için limitsiz)
    try:
        amount, err = parse_amount(amount_str, 10**18)
        if err:
            await update.message.reply_text(f"❌ {err}")
            return
    except:
        await update.message.reply_text("❌ Geçersiz miktar!")
        return
    
    # Kullanıcıyı kontrol et
    db = await get_db()
    target_user = await db.users.find_one({"telegram_id": target_id})
    if not target_user:
        await update.message.reply_text("❌ Kullanıcı bulunamadı!")
        return
    
    # Para ekle
    await add_balance(target_id, amount, "admin", f"Admin tarafından verildi: {amount_str}")
    
    # Kimin eklediğini belirt
    if target_id == user.id:
        kaynak = "Kendinize"
    else:
        kaynak = f"{target_user['display_name']} kullanıcısına"
    
    await update.message.reply_text(
        f"✅ <b>PARA EKLENDİ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {kaynak}\n"
        f"💰 Miktar: {format_amount(amount)}\n"
        f"💳 Yeni bakiye: {format_amount(await get_balance(target_id))}",
        parse_mode="HTML"
    )


async def cmd_setbalance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin komutu - Kullanıcının bakiyesini ayarlar"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Bu komutu kullanma yetkiniz yok!")
        return
    
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("💸 Kullanım: /setbalance <kullanıcı_id> <miktar>")
        return
    
    try:
        target_id = int(args[0])
        amount = int(args[1])
    except:
        await update.message.reply_text("❌ Geçersiz miktar veya ID!")
        return
    
    if amount < 0:
        await update.message.reply_text("❌ Miktar 0'dan küçük olamaz!")
        return
    
    db = await get_db()
    await db.users.update_one(
        {"telegram_id": target_id},
        {"$set": {"balance": amount, "updated_at": datetime.now()}}
    )
    
    target_user = await db.users.find_one({"telegram_id": target_id})
    
    await update.message.reply_text(
        f"✅ <b>BAKİYE AYARLANDI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Kullanıcı: {target_user['display_name']}\n"
        f"💰 Yeni bakiye: {format_amount(amount)}",
        parse_mode="HTML"
    )


async def cmd_cleanup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin komutu - Takılı kalmış oyunları temizle"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Bu komutu kullanma yetkiniz yok!")
        return
    
    global _active_games, _bj
    
    async with _state_lock:
        _active_games.clear()
    
    _bj.clear()
    
    # Veritabanında da temizlik
    db = await get_db()
    await db.games.update_many(
        {"state": {"$in": ["OPEN", "PLAYING", "CALCULATING"]}},
        {"$set": {"state": "FINISHED", "finished_at": datetime.now()}}
    )
    
    await update.message.reply_text(
        "✅ <b>OYUNLAR TEMİZLENDİ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🧹 Tüm takılı kalmış oyunlar sonlandırıldı.\n"
        f"🎮 Artık yeni oyun başlatabilirsiniz.",
        parse_mode="HTML"
    )


async def cmd_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """ID öğrenme komutu (herkes kullanabilir)"""
    user = update.effective_user
    await update.message.reply_text(
        f"🆔 <b>Telegram ID'niz:</b>\n"
        f"<code>{user.id}</code>\n\n"
        f"👤 Kullanıcı: {user.full_name}",
        parse_mode="HTML"
    )


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin komutu - Bot istatistikleri"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Bu komutu kullanma yetkiniz yok!")
        return
    
    db = await get_db()
    
    # İstatistikleri al
    total_users = await db.users.count_documents({})
    total_games = await db.games.count_documents({})
    total_transactions = await db.transactions.count_documents({})
    
    # Aktif oyunlar
    active_games_count = 0
    async with _state_lock:
        for chat_games in _active_games.values():
            active_games_count += len([g for g in chat_games.values() if g["state"] != "FINISHED"])
    
    await update.message.reply_text(
        f"📊 <b>BOT İSTATİSTİKLERİ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Toplam Kullanıcı: <b>{total_users}</b>\n"
        f"🎮 Toplam Oyun: <b>{total_games}</b>\n"
        f"💸 Toplam İşlem: <b>{total_transactions}</b>\n"
        f"🔄 Aktif Oyun: <b>{active_games_count}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Bot: @BettMasterrBot\n"
        f"🕒 Son güncelleme: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        parse_mode="HTML"
    )


async def cmd_reklam(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin komutu - Botun bulunduğu TÜM gruplara reklam gönder"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Bu komutu kullanma yetkiniz yok!")
        return
    
    if not ctx.args:
        await update.message.reply_text(
            "📢 <b>REKLAM KOMUTU</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"Kullanım: /reklam <mesaj>\n\n"
            f"Örnek: /reklam 🎰 Casino botumuzu deneyin!\n\n"
            f"⚠️ Botun üye olduğu TÜM gruplara gönderilir.",
            parse_mode="HTML"
        )
        return
    
    reklam_metni = " ".join(ctx.args)
    
    # Botun bulunduğu tüm sohbetleri bul
    db = await get_db()
    
    # Yöntem 1: Veritabanında kayıtlı gruplar varsa
    groups = await db.groups.find({"is_active": True}).to_list(length=1000)
    
    # Yöntem 2: Alternatif - get_updates ile son 100 sohbet
    if not groups:
        updates = await ctx.bot.get_updates(limit=100)
        chat_ids = set()
        for update_obj in updates:
            if update_obj.message and update_obj.message.chat:
                chat = update_obj.message.chat
                if chat.type in ["group", "supergroup"]:
                    chat_ids.add(chat.id)
            elif update_obj.callback_query and update_obj.callback_query.message:
                chat = update_obj.callback_query.message.chat
                if chat.type in ["group", "supergroup"]:
                    chat_ids.add(chat.id)
        
        groups = [{"chat_id": cid} for cid in chat_ids]
    
    # Her gruba reklam gönder
    gonderilen = 0
    hata = 0
    
    for group in groups:
        group_id = group.get("chat_id") or group.get("_id")
        try:
            await ctx.bot.send_message(
                group_id,
                f"📢 <b>REKLAM</b>\n━━━━━━━━━━━━━━━━━━━━━\n{reklam_metni}\n━━━━━━━━━━━━━━━━━━━━━\n💡 Bu mesaj bot sahibi tarafından gönderilmiştir.",
                parse_mode="HTML"
            )
            gonderilen += 1
            await asyncio.sleep(0.3)  # Rate limit koruması
        except Exception as e:
            hata += 1
            logger.error(f"Reklam gönderilemedi {group_id}: {e}")
    
    await update.message.reply_text(
        f"✅ <b>REKLAM GÖNDERİLDİ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📨 Başarılı: {gonderilen} grup\n"
        f"❌ Başarısız: {hata} grup\n"
        f"📝 Mesaj: {reklam_metni[:50]}...",
        parse_mode="HTML"
    )
    
    
# ═══════════════════════════════════════════════════════════════
#  MENÜ SİSTEMİ
# ═══════════════════════════════════════════════════════════════
async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Ana menüyü göster"""
    user = update.effective_user
    await get_or_create_user(user.id, user.username, user.full_name)
    bal = await get_balance(user.id)
    
    keyboard = [
        [
            InlineKeyboardButton("🎰 RULET", callback_data="menu_roulette"),
            InlineKeyboardButton("🃏 BLACKJACK", callback_data="menu_blackjack")
        ],
        [
            InlineKeyboardButton("🎲 ZAR (PvP)", callback_data="menu_dice"),
            InlineKeyboardButton("🎡 ÇARKIFELEK", callback_data="menu_wheel")
        ],
        [
            InlineKeyboardButton("🎟️ KAZI KAZAN", callback_data="menu_scratch"),
            InlineKeyboardButton("💰 BAKİYE", callback_data="menu_balance")
        ],
        [
            InlineKeyboardButton("🏆 LİDERLİK", callback_data="menu_leaderboard"),
            InlineKeyboardButton("🎁 GÜNLÜK BONUS", callback_data="menu_daily")
        ],
        [
            InlineKeyboardButton("🌟 VIP KASA", callback_data="menu_buy"),
            InlineKeyboardButton("❓ YARDIM", callback_data="menu_help")
        ]
    ]
    
    await update.message.reply_text(
        f"🎮 <b>CASİNİBOT ANA MENÜ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {user.full_name}\n"
        f"💰 Bakiyeniz: {format_amount(bal)}\n\n"
        f"Bir oyun seçin veya bilgi almak için butonlara tıklayın:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


async def menu_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Menü butonları için callback handler"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    data = query.data
    
    # Ana menü butonu her yerde aynı
    ana_menu_button = [[InlineKeyboardButton("🏠 ANA MENÜ", callback_data="menu_main")]]
    
    if data == "menu_roulette":
        await query.edit_message_text(
            "🎰 <b>RULET NASIL OYNANIR?</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ /rulet ile oyun başlatın\n"
            "2️⃣ 25 saniye içinde bahis yapın:\n"
            "   🔴 /red <miktar> - Kırmızıya bahis\n"
            "   ⚫ /black <miktar> - Siyaha bahis\n"
            "   🟢 /green <miktar> - Yeşile bahis (0)\n"
            "   🔢 /number <sayı> <miktar> - Tek sayı\n"
            "   🔢 /numbers <1,2,3> <miktar> - Çoklu sayı\n\n"
            "💰 Çarpanlar: Kırmızı/Siyah 2x, Yeşil 72x, Sayı 36x\n"
            "🎯 Bol şans!",
            reply_markup=InlineKeyboardMarkup(ana_menu_button),
            parse_mode="HTML"
        )
        
    elif data == "menu_blackjack":
        await query.edit_message_text(
            "🃏 <b>BLACKJACK NASIL OYNANIR?</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ /blackjack ile oyun başlatın\n"
            "2️⃣ 25 saniye içinde /bj <miktar> ile bahis yapın\n"
            "3️⃣ Kartlar dağıtılır, sırayla oynarsınız:\n"
            "   🃏 Hit - Yeni kart al\n"
            "   ✋ Stand - Kart dur\n\n"
            "📊 Kurallar:\n"
            "• 21'e en yakın olan kazanır\n"
            "• 21'i geçersen kaybedersin\n"
            "• Kurpiyer 17'de durur\n"
            "• Kazanırsan 2x alırsın\n\n"
            "🎯 Bol şans!",
            reply_markup=InlineKeyboardMarkup(ana_menu_button),
            parse_mode="HTML"
        )
        
    elif data == "menu_dice":
        await query.edit_message_text(
            "🎲 <b>ZAR OYUNU (PvP) NASIL OYNANIR?</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ /dicebet ile oyun başlatın\n"
            "2️⃣ 25 saniye içinde /dice <miktar> ile katılın\n"
            "3️⃣ En az 2 oyuncu gerekir\n"
            "4️⃣ Herkes zar atar, en yüksek toplam kazanır\n"
            "5️⃣ Beraberlikte havuz bölüşülür\n\n"
            "💰 Kazanan tüm havuzu alır!\n"
            "🎯 Bol şans!",
            reply_markup=InlineKeyboardMarkup(ana_menu_button),
            parse_mode="HTML"
        )
        
    elif data == "menu_wheel":
        await query.edit_message_text(
            "🎡 <b>ÇARKIFELEK NASIL OYNANIR?</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ /wheelbet ile oyun başlatın\n"
            "2️⃣ 25 saniye içinde /wheel <miktar> ile bahis yapın\n"
            "3️⃣ Çark döner ve sonuç belirlenir\n\n"
            "💰 Kazançlar:\n"
            "• 💀 PASS → Bahis kaybedilir\n"
            "• 🔄 İADE → Bahis iade\n"
            "• 2x, 3x, 5x, 10x, 15x, 25x, 50x, 100x → Bahis × çarpan\n\n"
            "🎯 Bol şans!",
            reply_markup=InlineKeyboardMarkup(ana_menu_button),
            parse_mode="HTML"
        )
        
    elif data == "menu_scratch":
        await query.edit_message_text(
            "🎟 <b>KAZI KAZAN NASIL OYNANIR?</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🎟️ <b>TEK KİŞİLİK</b>\n"
            "📌 /kazisolo <miktar> - Tek başına oyna\n\n"
            "🎟️ <b>TURNUVASI</b>\n"
            "1️⃣ /kazibet - Turnuva başlat\n"
            "2️⃣ /kazi <miktar> - Turnuvaya katıl (en az 2 kişi)\n\n"
            "🏆 Kazanma şartı:\n"
            "6 kutuda 3 aynı çarpan = KAZANÇ!\n\n"
            "💰 Çarpanlar: 2x, 3x, 5x, 10x, 15x, 25x, 50x, 100x, 250x\n"
            "🎯 Bol şans!",
            reply_markup=InlineKeyboardMarkup(ana_menu_button),
            parse_mode="HTML"
        )
        
    elif data == "menu_balance":
        u = await get_user(user.id)
        if u:
            lvl, emoji = get_level(u["balance"])
            await query.edit_message_text(
                f"💳 <b>{user.full_name}</b> [{lvl}] {emoji}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 Bakiye: <b>{format_amount(u['balance'])}</b>\n"
                f"🎮 Oynanan oyun: {u.get('games_played', 0)}\n"
                f"📊 Toplam bahis: {format_amount(u.get('total_wagered', 0))}\n"
                f"🏆 Toplam kazanç: {format_amount(u.get('total_won', 0))}",
                reply_markup=InlineKeyboardMarkup(ana_menu_button),
                parse_mode="HTML"
            )
        else:
            await query.edit_message_text("❌ Kullanıcı bulunamadı.")
            
    elif data == "menu_leaderboard":
        rows = await get_leaderboard(LEADERBOARD_SIZE)
        medals = ["🥇", "🥈", "🥉"]
        lines = ["🏆 <b>LİDERLİK TABLOSU</b>", "━━━━━━━━━━━━━━━━━━━━━"]
        for i, r in enumerate(rows):
            lvl, emoji = get_level(r["balance"])
            medal = medals[i] if i < 3 else f"{i+1}."
            name = r.get("display_name", "Bilinmeyen")[:15]
            lines.append(f"{medal} {name} [{lvl}]{emoji} — {format_amount(r['balance'])}")
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(ana_menu_button),
            parse_mode="HTML"
        )
        
    elif data == "menu_daily":
        await query.edit_message_text("🎁 Günlük bonus alınıyor...")
        fake_update = update
        fake_update.message = query.message
        await cmd_daily(fake_update, ctx)
        await query.delete_message()
        
    elif data == "menu_buy":
        await query.edit_message_text(
            "🌟 <b>VIP KASA</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "Telegram Stars ile oyun parası satın al:\n\n"
            "⭐ 10 Stars → 1.000.000🪙\n"
            "⭐ 25 Stars → 50.000.000🪙\n"
            "⭐ 50 Stars → 1.000.000.000🪙\n"
            "⭐ 100 Stars → 10.000.000.000🪙\n"
            "⭐ 250 Stars → 100.000.000.000🪙\n"
            "⭐ 500 Stars → 1.000.000.000.000🪙\n"
            "⭐ 1000 Stars → 10.000.000.000.000🪙\n\n"
            "💡 /buy yazarak satın alabilirsiniz!\n"
            "⚠️ Tamamen sanal oyun parasıdır, gerçek para değeri yoktur.",
            reply_markup=InlineKeyboardMarkup(ana_menu_button),
            parse_mode="HTML"
        )
        
    elif data == "menu_help":
        await query.edit_message_text(
            "🎰 <b>CASİNİBOT KOMUTLAR</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👤 <b>HESAP</b>\n"
            "/start — Kayıt / Hoş geldin\n"
            "/balance — Bakiyeni göster\n"
            "/changename — İsim değiştir\n"
            "/leaderboard — İlk 15 oyuncu\n"
            "/moneys — Para gönder\n"
            "/daily — Günlük bonus\n\n"
            "🎡 <b>RULET</b>\n"
            "/rulet — Rulet başlat\n"
            "/red /black /green /number /numbers\n\n"
            "🎲 <b>ZAR (PvP)</b>\n"
            "/dicebet — Başlat | /dice — Katıl\n\n"
            "🎡 <b>ÇARKIFELEK</b>\n"
            "/wheelbet — Başlat | /wheel — Bahis\n\n"
            "🎟 <b>KAZI KAZAN</b>\n"
            "/kazisolo — Solo oyna\n"
            "/kazibet — Turnuva başlat\n"
            "/kazi — Turnuvaya katıl\n\n"
            "🃏 <b>BLACKJACK</b>\n"
            "/blackjack — Başlat | /bj — Bahis\n\n"
            "🌟 <b>VIP KASA</b>\n"
            "/buy — Telegram Stars ile satın al\n\n"
            "💡 Miktar yerine <code>allin</code> yazarak tüm bakiyeni yatırabilirsin!",
            reply_markup=InlineKeyboardMarkup(ana_menu_button),
            parse_mode="HTML"
        )
        
    elif data == "menu_main":
        bal = await get_balance(user.id)
        main_keyboard = [
            [
                InlineKeyboardButton("🎰 RULET", callback_data="menu_roulette"),
                InlineKeyboardButton("🃏 BLACKJACK", callback_data="menu_blackjack")
            ],
            [
                InlineKeyboardButton("🎲 ZAR (PvP)", callback_data="menu_dice"),
                InlineKeyboardButton("🎡 ÇARKIFELEK", callback_data="menu_wheel")
            ],
            [
                InlineKeyboardButton("🎟️ KAZI KAZAN", callback_data="menu_scratch"),
                InlineKeyboardButton("💰 BAKİYE", callback_data="menu_balance")
            ],
            [
                InlineKeyboardButton("🏆 LİDERLİK", callback_data="menu_leaderboard"),
                InlineKeyboardButton("🎁 GÜNLÜK BONUS", callback_data="menu_daily")
            ],
            [
                InlineKeyboardButton("🌟 VIP KASA", callback_data="menu_buy"),
                InlineKeyboardButton("❓ YARDIM", callback_data="menu_help")
            ]
        ]
        await query.edit_message_text(
            f"🎮 <b>CASİNİBOT ANA MENÜ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {user.full_name}\n"
            f"💰 Bakiyeniz: {format_amount(bal)}\n\n"
            f"Bir oyun seçin veya bilgi almak için butonlara tıklayın:",
            reply_markup=InlineKeyboardMarkup(main_keyboard),
            parse_mode="HTML"
        )
        
        
        
# ═══════════════════════════════════════════════════════════════
#  YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════

async def cleanup_stuck_games():
    """Bot başlarken takılı kalmış oyunları temizle"""
    db = await get_db()
    await db.games.update_many(
        {"state": {"$in": ["OPEN", "PLAYING", "CALCULATING"]}},
        {"$set": {"state": "FINISHED", "finished_at": datetime.now()}}
    )
    logger.info("🧹 Takılı kalmış oyunlar temizlendi.")


async def backup_task():
    """Yedekleme görevi (MongoDB için farklı çalışır)"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    while True:
        await asyncio.sleep(24 * 3600)
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = os.path.join(BACKUP_DIR, f"casinobot_{ts}.json")
            
            # MongoDB'den verileri yedekle
            db = await get_db()
            users = await db.users.find().to_list(length=None)
            transactions = await db.transactions.find().to_list(length=None)
            games = await db.games.find().to_list(length=None)
            
            import json
            backup_data = {
                "users": users,
                "transactions": transactions,
                "games": games,
                "backup_date": datetime.now().isoformat()
            }
            
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, default=str, indent=2)
            
            logger.info(f"📦 Backup alındı: {dest}")
            
            # Eski backup'ları temizle (son 7'yi tut)
            backups = sorted(os.listdir(BACKUP_DIR))
            for old in backups[:-7]:
                os.remove(os.path.join(BACKUP_DIR, old))
        except Exception as e:
            logger.error(f"Backup hatası: {e}")
            
            
            
# ═══════════════════════════════════════════════════════════════
#  ANA FONKSİYON
# ═══════════════════════════════════════════════════════════════

async def post_init(app):
    await init_db()
    await cleanup_stuck_games()
    asyncio.create_task(backup_task())
    logger.info("🎰 CasiniBot başlatıldı!")


async def post_shutdown(app):
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()
    logger.info("CasiniBot kapatıldı.")


def main():
    if BOT_TOKEN == "8646115906:AAEn4Rydo0TjRBm_iiaZqSRJ-KcIqUmNyZQ":
        print("✅ Bot token ayarlanmış.")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    
    # Admin komutları
    app.add_handler(CommandHandler("addbalance", cmd_addbalance))
    app.add_handler(CommandHandler("setbalance", cmd_setbalance))
    app.add_handler(CommandHandler("cleanup", cmd_cleanup))
    app.add_handler(CommandHandler("reklam", cmd_reklam))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("stats", cmd_stats))
    
    # Genel komutlar
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("moneys", cmd_moneys))
    app.add_handler(CommandHandler("changename", cmd_changename))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("daily", cmd_daily))
    app.add_handler(CommandHandler("menu", cmd_menu))
    
    # VIP Kasa
    app.add_handler(CommandHandler("buy", cmd_buy))
    app.add_handler(CallbackQueryHandler(buy_callback, pattern=r"^buy_"))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    # Rulet
    app.add_handler(CommandHandler("rulet", cmd_rulet))
    app.add_handler(CommandHandler("green", cmd_green))
    app.add_handler(CommandHandler("red", cmd_red))
    app.add_handler(CommandHandler("black", cmd_black))
    app.add_handler(CommandHandler("number", cmd_number))
    app.add_handler(CommandHandler("numbers", cmd_numbers))
    
    # Zar
    app.add_handler(CommandHandler("dicebet", cmd_dicebet))
    app.add_handler(CommandHandler("dice", cmd_dice))
    
    
    # Çark
    app.add_handler(CommandHandler("wheelbet", cmd_wheelbet))
    app.add_handler(CommandHandler("wheel", cmd_wheel))
    
    # Kazı Kazan
    app.add_handler(CommandHandler("kazisolo", cmd_kazisolo))
    app.add_handler(CommandHandler("kazibet", cmd_kazibet))
    app.add_handler(CommandHandler("kazi", cmd_kazi))
    
    # Blackjack
    app.add_handler(CommandHandler("blackjack", cmd_blackjack))
    app.add_handler(CommandHandler("bj", cmd_bj))
    app.add_handler(CallbackQueryHandler(bj_callback, pattern=r"^bj_(hit|stand):"))
    
    # Menü
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu_"))
    
    logger.info("🚀 Handler'lar yüklendi. Polling başlıyor...")
    app.run_polling(drop_pending_updates=True, allowed_updates=["message", "callback_query", "pre_checkout_query"])


if __name__ == "__main__":
    main()
               

# ═══════════════════════════════════════════════════════════════
#  CASINOBOT - ANA DOSYA (ÇALIŞAN SÜRÜM)
# ═══════════════════════════════════════════════════════════════

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
import io
import re
import urllib.request
from typing import Dict, List, Tuple

# MongoDB imports
from motor.motor_asyncio import AsyncIOMotorClient

# Telegram imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, LabeledPrice, SuccessfulPayment
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
    PreCheckoutQueryHandler, MessageHandler, filters
)
from telegram.error import BadRequest

# PIL imports
from PIL import Image, ImageDraw, ImageFont


# ═══════════════════════════════════════════════════════════════
#  BASE_DIR VE FONT AYARLARI
# ═══════════════════════════════════════════════════════════════

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_font(font_size: int):
    """Sistemdeki fontları dene, hiçbiri yoksa default kullan"""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    ]
    for path in font_paths:
        try:
            font = ImageFont.truetype(path, font_size)
            print(f"✅ Font bulundu: {path}")
            return font
        except:
            continue
    print(f"⚠️ Font bulunamadı, default kullanılıyor")
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
CARD_WIDTH, CARD_HEIGHT = 60, 84

# Kazı Kazan
KAPALI_KART_PATH = os.path.join(BASE_DIR, "kapali.jpg")
ACIK_KART_PATH = os.path.join(BASE_DIR, "acik.jpg")

# Transfer
TRANSFER_TEMPLATE_PATH = os.path.join(BASE_DIR, "transfer.png")

# Çarkıfelek
WHEEL_SEGMENTS = [
    ("💀 PASS 💀", 0), ("💀 PASS 💀", 0), ("💀 PASS 💀", 0),
    ("💀 PASS 💀", 0), ("💀 PASS 💀", 0), ("💀 PASS 💀", 0),
    ("💀 PASS 💀", 0), ("💀 PASS 💀", 0), ("💀 PASS 💀", 0),
    ("💀 PASS 💀", 0),
    ("🟢 2x", 2), ("🟢 2x", 2), ("🟢 2x", 2), ("🟢 2x", 2),
    ("🟢 5x", 5), ("🟢 5x", 5), ("🟢 5x", 5),
    ("🔵 10x", 10), ("🔵 10x", 10), ("🔵 10x", 10),
    ("🔵 25x", 25), ("🔵 25x", 25),
    ("🟣 50x", 50), ("🟣 100x", 100), ("🟡 250x", 250),
]

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
    (0, "Çırak", "🪵"), (1_000, "Bahisçi", "🎯"),
    (100_000, "Gümüş", "🥈"), (1_000_000, "Altın", "🥇"),
    (100_000_000, "Elmas", "💠"), (1_000_000_000, "Milyarder", "💰"),
    (1_000_000_000_000, "Trilyoner", "💎💰"),
    (10**18, "Quintillioner", "🌌"), (10**21, "Sextillioner", "🌀"),
    (10**24, "Septillioner", "🛡️"), (10**27, "Octillioner", "⚔️"),
    (10**30, "Nonillioner", "🔱"), (10**60, "Kozmik Varlık", "🪐"),
    (10**100, "MUTLAK TANRI", "👑👑👑"),
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
        _db = _mongo_client['casinibot']
    return _db

async def init_db():
    db = await get_db()
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

async def get_leaderboard(limit=15) -> list[dict]:
    db = await get_db()
    cursor = db.users.find().sort("balance", -1).limit(limit)
    users = await cursor.to_list(length=limit)
    return users


# ═══════════════════════════════════════════════════════════════
#  STATE MANAGER & OYUN YÖNETİMİ (MONGODB)
# ═══════════════════════════════════════════════════════════════

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
#  GÖRSEL OLUŞTURMA FONKSİYONLARI
# ═══════════════════════════════════════════════════════════════

def clean_name(name: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9ğüşıöçĞÜŞİÖÇ\s]', '', name)
    return cleaned.strip()

def create_transfer_image(sender: str, receiver: str, amount: int) -> io.BytesIO:
    transfer_template = os.path.join(BASE_DIR, "transfer.png")
    if not os.path.exists(transfer_template):
        raise FileNotFoundError(f"Transfer şablonu bulunamadı: {transfer_template}")
    
    img = Image.open(transfer_template).convert('RGBA')
    img.thumbnail((800, 600), Image.Resampling.LANCZOS)
    
    width, height = img.size
    txt_layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)
    
    font_isim = get_font(int(height * 0.10))
    font_miktar = get_font(int(height * 0.13))
    font_token = get_font(int(height * 0.067))
    
    gold_color = "#B8860B"
    shadow_color = "#4a3a1a"
    
    draw.text((width * 0.57, height * 0.19), sender, fill="#F5F5F5", font=font_isim, anchor="mm")
    draw.text((width * 0.57, height * 0.53), receiver, fill="#F5F5F5", font=font_isim, anchor="mm")
    
    amount_text = format_amount(amount).replace(CURRENCY_SYMBOL, "").strip()
    draw.text((width * 0.47 + 3, height * 0.86 + 3), amount_text, fill=shadow_color, font=font_miktar, anchor="lm")
    draw.text((width * 0.47, height * 0.86), amount_text, fill=gold_color, font=font_miktar, anchor="lm")
    
    try:
        text_w = draw.textlength(amount_text, font=font_miktar)
        draw.text((width * 0.47 + text_w + 20 + 3, height * 0.87 + 3), "Token", fill=shadow_color, font=font_token, anchor="lm")
        draw.text((width * 0.47 + text_w + 20, height * 0.87), "Token", fill=gold_color, font=font_token, anchor="lm")
    except:
        pass
    
    img = Image.alpha_composite(img, txt_layer).convert('RGB')
    bio = io.BytesIO()
    img.save(bio, format='PNG', quality=95)
    bio.seek(0)
    return bio

def create_scratch_result_image(board: list, winner_mult: int) -> io.BytesIO:
    acik_kart = os.path.join(BASE_DIR, "acik.jpg")
    if not os.path.exists(acik_kart):
        raise Exception(f"Açık kart görseli bulunamadı: {acik_kart}")
    
    img = Image.open(acik_kart)
    img.thumbnail((800, 600), Image.Resampling.LANCZOS)
    
    draw = ImageDraw.Draw(img)
    font = get_font(120)
    
    width, height = img.size
    
    boxes = [
        {"center": (width * 0.16, height * 0.25), "index": 0},
        {"center": (width * 0.50, height * 0.25), "index": 1},
        {"center": (width * 0.84, height * 0.25), "index": 2},
        {"center": (width * 0.16, height * 0.69), "index": 3},
        {"center": (width * 0.50, height * 0.69), "index": 4},
        {"center": (width * 0.84, height * 0.69), "index": 5},
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
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((center_x - tw/2, center_y - th/2), text, fill=text_color, font=font, stroke_width=3, stroke_fill=(0, 0, 0))
    
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    return bio


# ═══════════════════════════════════════════════════════════════
#  GENEL KOMUTLAR
# ═══════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = await get_or_create_user(user.id, user.username, user.full_name)
    lvl, emoji = get_level(u["balance"])
    await update.message.reply_text(
        f"🎰 <b>CasiniBot'a Hoş Geldiniz!</b>\n━━━━━━━━━━━━━━━━━━━━━\n👤 <b>{user.full_name}</b> [{lvl}] {emoji}\n💳 Bakiyeniz: {format_amount(u['balance'])}\n\n🍀 Bol şans!\n📌 Komutlar için /help",
        parse_mode="HTML"
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🎰 <b>CASİNİBOT KOMUTLAR</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
        "👤 <b>HESAP</b>\n/start — Kayıt\n/balance — Bakiye\n/daily — Günlük bonus\n/moneys — Para gönder\n/leaderboard — Liderlik\n\n"
        "🎡 <b>RULET</b>\n/rulet — Başlat\n/red /black /green /number\n\n"
        "🃏 <b>BLACKJACK</b>\n/blackjack — Başlat\n/bj — Bahis\n\n"
        "🎲 <b>ZAR (PvP)</b>\n/dicebet — Başlat\n/dice — Katıl\n\n"
        "🎡 <b>ÇARKIFELEK</b>\n/wheelbet — Başlat\n/wheel — Bahis\n\n"
        "🎟 <b>KAZI KAZAN</b>\n/kazisolo — Tek kişilik\n/kazibet — Turnuva\n\n"
        "💰 <b>SATIN AL</b>\n/buy — Stars ile satın al"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")

async def cmd_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_rate_limited(user.id): return
    u = await get_user(user.id)
    if not u:
        await update.message.reply_text("❌ Önce /start yazın!")
        return
    
    username = user.username if user.username else str(user.id)
    def get_level_info(balance: int):
        if balance >= 10**60: return ("Kozmik Varlık", "🪐")
        elif balance >= 10**30: return ("Mutlak Tanrı", "👑")
        elif balance >= 10**24: return ("Septillioner", "🛡️")
        elif balance >= 10**21: return ("Sextillioner", "🌀")
        elif balance >= 10**18: return ("Mythic", "🌌")
        elif balance >= 10**15: return ("Grand", "🔱")
        elif balance >= 10**12: return ("Epic", "💎")
        elif balance >= 10**9: return ("Legend", "🥇")
        elif balance >= 10**6: return ("Expert", "🥈")
        else: return ("Çırak", "🪵")
    
    level_name, level_emoji = get_level_info(u["balance"])
    db = await get_db()
    all_users = await db.users.find().sort("balance", -1).to_list(length=None)
    rank = 1
    for i, doc in enumerate(all_users, 1):
        if doc["telegram_id"] == user.id:
            rank = i
            break
    
    balance_text = f"{u['balance']:,}".replace(",", ".")
    total_won_text = f"{u.get('total_won', 0):,}".replace(",", ".")
    total_wagered_text = f"{u.get('total_wagered', 0):,}".replace(",", ".")
    games_played = u.get('games_played', 0)
    win_rate = (u.get('total_won', 0) / u.get('total_wagered', 1) * 100) if u.get('total_wagered', 0) > 0 else 0
    
    info_text = (
        f"📌 <b>Verilerim</b>\n\n    👤 {username}\n\n    🤴 Seviye 🔘 {level_name} {level_emoji}\n\n"
        f"    🏧 Bakiye 🔘 {balance_text} 🪙\n\n    📊 Toplam Kazanç 🔘 {total_won_text} 🪙\n"
        f"    🎲 Toplam Bahis 🔘 {total_wagered_text} 🪙\n    🎮 Oynanan Oyun 🔘 {games_played}\n"
        f"    📈 Kazanma Oranı 🔘 %{win_rate:.1f}\n\n    🌍 Genel Sıralamanız 🔘 {rank}\n"
        f"    🔗 Referans Sayısı 🔘 0\n    🎯 Günlük Seri 🔘 {u.get('daily_streak', 0)} gün"
    )
    await update.message.reply_text(info_text, parse_mode="HTML")

async def cmd_changename(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_rate_limited(user.id): return
    if not ctx.args:
        await update.message.reply_text("✏️ Kullanım: /changename <yeni isim>", parse_mode="HTML")
        return
    new_name = " ".join(ctx.args)[:32]
    if len(new_name) < 2:
        await update.message.reply_text("❌ İsim en az 2 karakter olmalı!")
        return
    clean_name_str = re.sub(r'[^a-zA-Z0-9ğüşıöçĞÜŞİÖÇ\s]', '', new_name).strip()
    if not clean_name_str:
        await update.message.reply_text("❌ Geçersiz isim!")
        return
    db = await get_db()
    await db.users.update_one({"telegram_id": user.id}, {"$set": {"display_name": clean_name_str, "updated_at": datetime.now()}})
    await update.message.reply_text(f"✅ İsminiz <b>{clean_name_str}</b> olarak güncellendi!", parse_mode="HTML")

async def cmd_moneys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_rate_limited(user.id): return
    
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
    
    try:
        sender_name = clean_name(user.full_name)
        receiver_name = clean_name(target.full_name)
        transfer_img = create_transfer_image(sender_name, receiver_name, amount)
        await update.message.reply_photo(
            photo=transfer_img,
            caption=f"✅ <b>Transfer Başarılı!</b>\n━━━━━━━━━━━━━━━━━━━━━\n📤 {sender_name} → 📥 {receiver_name}\n💰 Miktar: {format_amount(amount)}\n💳 Yeni bakiyeniz: {format_amount(new_bal)}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Transfer görseli hatası: {e}")
        await update.message.reply_text(
            f"✅ <b>Transfer Başarılı!</b>\n━━━━━━━━━━━━━━━━━━━━━\n📤 {user.full_name} → 📥 {target.full_name}\n💰 Miktar: {format_amount(amount)}\n💳 Yeni bakiyeniz: {format_amount(new_bal)}",
            parse_mode="HTML"
        )

async def cmd_daily(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_rate_limited(user.id): return
    u = await get_or_create_user(user.id, user.username, user.full_name)
    db = await get_db()
    lock = await _get_lock(user.id)
    async with lock:
        user_data = await db.users.find_one({"telegram_id": user.id})
        last_daily = user_data.get("last_daily")
        current_streak = user_data.get("daily_streak", 0)
        
        def can_claim(last_daily):
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
        
        can_claim_daily, hours_left = can_claim(last_daily)
        if not can_claim_daily:
            await update.message.reply_text(f"⏰ Günlük bonusunuzu zaten aldınız! Sonraki bonus: {hours_left} saat sonra", parse_mode="HTML")
            return
        
        new_streak = current_streak + 1
        bonus_amount = 50000 * (2 ** min(new_streak, 10))
        await db.users.update_one(
            {"telegram_id": user.id},
            {"$inc": {"balance": bonus_amount}, "$set": {"last_daily": datetime.now().isoformat(), "daily_streak": new_streak}}
        )
        new_balance = await get_balance(user.id)
        await update.message.reply_text(f"🎁 GÜNLÜK BONUS! +{format_amount(bonus_amount)}\n💳 Yeni bakiye: {format_amount(new_balance)}", parse_mode="HTML")

async def cmd_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if is_rate_limited(update.effective_user.id): return
    rows = await get_leaderboard(LEADERBOARD_SIZE)
    chat = update.effective_chat
    group_name = chat.title if chat.title else "Casino"
    
    def get_rank_badge(balance: int) -> str:
        if balance >= 10**60: return "🪐 Kozmik Varlık"
        elif balance >= 10**30: return "👑 Mutlak Tanrı"
        elif balance >= 10**24: return "🛡️ Septillioner"
        elif balance >= 10**21: return "🌀 Sextillioner"
        elif balance >= 10**18: return "🌌 Mythic"
        elif balance >= 10**15: return "🔱 Grand"
        elif balance >= 10**12: return "💎 Diamond"
        elif balance >= 10**9: return "🥇 Gold"
        elif balance >= 10**6: return "🥈 Silver"
        else: return "🪵 Bronze"
    
    rank_emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    lines = [f"🏆 <b>{group_name} En Zengin {min(LEADERBOARD_SIZE, len(rows))} Kullanıcı</b> 🏆", ""]
    for i, r in enumerate(rows[:10]):
        rank_emoji = rank_emojis[i] if i < len(rank_emojis) else f"{i+1}️⃣"
        name = r.get("display_name", "Bilinmeyen")[:15]
        balance = r["balance"]
        badge = get_rank_badge(balance)
        balance_text = format_amount(balance).replace(CURRENCY_SYMBOL, "").strip()
        lines.append(f"{rank_emoji} {name} ❇️  {balance_text} 🪙 {badge}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# ═══════════════════════════════════════════════════════════════
#  RULET (GELİŞMİŞ)
# ═══════════════════════════════════════════════════════════════

def format_number_with_emoji(number: int) -> str:
    emoji_digits = {'0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
                    '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'}
    return ''.join(emoji_digits[d] for d in str(number))

def get_rank_emoji(rank: int) -> str:
    return ["🥇", "🥈", "🥉"][rank-1] if rank <= 3 else "📍"

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
    
    spin_img_path = os.path.join(ROULETTE_IMG_PATH, "spin.jpg")
    caption = f"🎰 <b>AVRUPA RULETİ BAŞLADI!</b>\n━━━━━━━━━━━━━━━━━━━━━\n⏱ <b>{BET_WINDOW} saniye</b> içinde bahis yapın!\n\n🔴 /red &lt;miktar&gt;\n⚫ /black &lt;miktar&gt;\n🟢 /green &lt;miktar&gt;\n🔢 /number &lt;sayı&gt; &lt;miktar&gt;"
    
    try:
        if os.path.exists(spin_img_path):
            with open(spin_img_path, "rb") as photo:
                msg = await update.message.reply_photo(photo=photo, caption=caption, parse_mode="HTML")
        else:
            msg = await update.message.reply_text(caption, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Spin görseli gönderilemedi: {e}")
        msg = await update.message.reply_text(caption, parse_mode="HTML")
    
    game = await create_game(chat_id, "roulette", msg.message_id)
    asyncio.create_task(_roulette_timer(ctx, chat_id, game["game_id"], msg))

async def _roulette_timer(ctx, chat_id, game_id, msg):
    await asyncio.sleep(BET_WINDOW)
    game = await get_active_game(chat_id, "roulette")
    if not game or game["game_id"] != game_id: return
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
    for uid, data in parts.items():
        bet = data["bet"]
        bd = data["bet_data"]
        payout = 0
        if bd.get("type") == "color":
            if bd.get("color") == color:
                multiplier = ROULETTE_MULTIPLIERS[color]
                payout = bet * multiplier
                await add_balance(uid, payout, "win", f"Rulet game:{game_id}")
                await update_stats(uid, payout)
                winner_list.append((bd['name'], bd['color'], payout))
            else:
                await update_stats(uid, 0)
        elif bd.get("type") == "number":
            if winning in bd.get("numbers", []):
                per_number_bet = bet // len(bd["numbers"])
                multiplier = ROULETTE_MULTIPLIERS["number"]
                payout = per_number_bet * multiplier
                await add_balance(uid, payout, "win", f"Rulet game:{game_id}")
                await update_stats(uid, payout)
                winner_list.append((bd['name'], None, payout))
            else:
                await update_stats(uid, 0)
    
    result_text = f"🆔 GAME ID: <code>{game_id}</code>\n\n🏆 Kazanan Sayı 🔘 {format_number_with_emoji(winning)} {color_emoji}!\n\n🏧 Kazanan Kişiler 🔘\n"
    if winner_list:
        for i, (name, win_color, payout) in enumerate(winner_list[:15], 1):
            rank_emoji = get_rank_emoji(i)
            if win_color:
                win_color_emoji = ROUL_EMOJI.get(win_color, "")
                result_text += f" {rank_emoji} {name} {win_color_emoji} {format_amount(payout)}🪙\n"
            else:
                result_text += f" {rank_emoji} {name} {color_emoji} {format_amount(payout)}🪙\n"
    else:
        result_text += " 💀 Kazanan olmadı!\n"
    
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
    if is_rate_limited(user.id): return
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
        bd = {"type": "color", "color": color, "numbers": [], "name": user.full_name}
        color_emoji = {"red": "🔴", "black": "⚫", "green": "🟢"}.get(color, "🔵")
    else:
        bd = {"type": "number", "color": None, "numbers": numbers or [], "name": user.full_name}
        color_emoji = "🔵"
    await add_participant(chat_id, game["game_id"], user.id, amount, bd)
    await update.message.reply_text(f"🕹 <b>{user.full_name}</b> {color_emoji} {format_amount(amount)}🪙 bahis yaptı", parse_mode="HTML")

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
        keyboard.append([InlineKeyboardButton(f"🌟 {stars} Stars → {config['label']} {format_amount(config['coin'])}🪙", callback_data=f"buy_{stars}")])
    await update.message.reply_text(
        "🌟 <b>VIP KASA - Telegram Stars ile Satın Al</b>\n━━━━━━━━━━━━━━━━━━━━━\nAşağıdaki paketlerden birini seçin:\n\n💡 Telegram Stars satın almak için: @PremiumBot\n⚠️ Bu sanal oyun parasıdır, gerçek para değeri yoktur.\n✅ Satın alınca coinler anında hesabınıza eklenir!",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
    )

async def buy_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    stars = int(query.data.split("_")[1])
    config = STARS_CONFIG[stars]
    coin_amount = config["coin"]
    user = query.from_user
    await ctx.bot.send_invoice(
        chat_id=user.id, title=f"{stars} Telegram Stars", description=f"{config['label']} - {format_amount(coin_amount)}🪙",
        payload=f"stars_{stars}", provider_token="", currency="XTR",
        prices=[LabeledPrice(label=f"{stars} Stars", amount=stars)], start_parameter="vip_kasa",
        need_name=False, need_phone_number=False, need_email=False
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
    await update.message.reply_text(f"✅ SATIN ALMA BAŞARILI!\n━━━━━━━━━━━━━━━━━━━━━\n🌟 {stars} Stars → {format_amount(coin_amount)}🪙\n💰 Yeni bakiyeniz: {format_amount(new_balance)}", parse_mode="HTML")


# ═══════════════════════════════════════════════════════════════
#  BLACKJACK
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
    back_path = os.path.join(BASE_DIR, "back.png")
    if os.path.exists(back_path):
        img = Image.open(back_path)
        img = img.resize((CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS)
        return img
    return Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), color='#2c2c2c')

def combine_cards(cards: list) -> io.BytesIO:
    if not cards: return None
    total_width = len(cards) * CARD_WIDTH
    combined = Image.new('RGB', (total_width, CARD_HEIGHT), color='#1a1a2e')
    for i, card in enumerate(cards):
        combined.paste(get_card_image(card), (i * CARD_WIDTH, 0))
    bio = io.BytesIO()
    combined.save(bio, format='PNG')
    bio.seek(0)
    return bio

def combine_cards_with_hidden(cards: list) -> io.BytesIO:
    if not cards: return None
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
    if rank in ("J", "Q", "K"): return 10
    if rank == "A": return 11
    return int(rank)

def _hand_val(hand: List[Tuple[str, str]]) -> int:
    total = sum(_card_val(r) for r, s in hand)
    aces = sum(1 for r, s in hand if r == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

def _bj_kb(game_id: str):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🃏 Hit", callback_data=f"bj_hit:{game_id}"), InlineKeyboardButton("✋ Stand", callback_data=f"bj_stand:{game_id}")]])

async def cmd_blackjack(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if is_rate_limited(user.id): return
    ok, err = await can_open_game(chat_id, "blackjack")
    if not ok:
        await update.message.reply_text(f"❌ {err}")
        return
    msg = await update.message.reply_text(f"🃏 <b>BLACKJACK BAŞLADI!</b>\n━━━━━━━━━━━━━━━━━━━━━\n⏱ <b>{BET_WINDOW} saniye</b> içinde bahis yapın!\n\n📌 /bj &lt;miktar&gt;", parse_mode="HTML")
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
        await update.message.reply_text(f"🕹 <b>{user.full_name}</b> 🃏 +{format_amount(amount)}🪙 (Toplam: {format_amount(bj['players'][user.id]['bet'])})\n━━━━━━━━━━━━━━━━━━━━━\n💰 Yeni bakiye: {format_amount(await get_balance(user.id))}", parse_mode="HTML")
    else:
        bj["players"][user.id] = {"bet": amount, "hand": [], "state": "WAITING", "name": user.full_name}
        bj["order"].append(user.id)
        await update.message.reply_text(f"🕹 <b>{user.full_name}</b> 🃏 {format_amount(amount)}🪙 bahis yaptı\n━━━━━━━━━━━━━━━━━━━━━\n💰 Yeni bakiye: {format_amount(await get_balance(user.id))}", parse_mode="HTML")

async def _bj_bet_timer(ctx, chat_id, game_id):
    await asyncio.sleep(BET_WINDOW)
    bj = _bj.get(chat_id)
    if not bj or bj["game_id"] != game_id: return
    if not bj["players"]:
        await ctx.bot.send_message(chat_id, "❌ Blackjack iptal — kimse katılmadı.")
        await finish_game(chat_id, game_id, "iptal")
        await cleanup(chat_id)
        return
    bj["state"] = "DEALING"
    deck = _new_deck()
    bj["deck"] = deck
    for uid in bj["order"]:
        bj["players"][uid]["hand"] = [deck.pop(), deck.pop()]
        bj["players"][uid]["state"] = "PLAYING"
        bj["players"][uid]["cards_sent"] = False
    bj["dealer"] = [deck.pop(), deck.pop()]
    bj["current"] = 0
    dealer_img = combine_cards_with_hidden(bj["dealer"])
    first_card_value = _card_val(bj["dealer"][0][0])
    await ctx.bot.send_photo(chat_id, photo=dealer_img, caption=f"🎩 <b>KURPİYER</b>\n━━━━━━━━━━━━━━━━━━━━━\nAçık kart: {first_card_value}\nKapalı kart: ?", parse_mode="HTML")
    for uid in bj["order"]:
        p = bj["players"][uid]
        hand_img = combine_cards(p["hand"])
        await ctx.bot.send_photo(chat_id, photo=hand_img, caption=f"🃏 <b>{p['name']}</b>\n━━━━━━━━━━━━━━━━━━━━━\n🃏 Eliniz: {_hand_val(p['hand'])}", parse_mode="HTML")
        p["cards_sent"] = True
    await _bj_next(ctx, chat_id, game_id)

async def _bj_next(ctx, chat_id, game_id):
    bj = _bj.get(chat_id)
    if not bj or bj["game_id"] != game_id: return
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
    if not p.get("cards_sent", False):
        hand_img = combine_cards(p["hand"])
        await ctx.bot.send_photo(chat_id, photo=hand_img, caption=f"🃏 <b>{p['name']}</b>\n━━━━━━━━━━━━━━━━━━━━━\n🃏 Eliniz: {val}", reply_markup=_bj_kb(game_id), parse_mode="HTML")
        p["cards_sent"] = True
    else:
        await ctx.bot.send_message(chat_id, f"🃏 <b>{p['name']}</b> sırası!\n━━━━━━━━━━━━━━━━━━━━━\n🃏 Eliniz: {val}\n\n⏱ {BLACKJACK_TURN} saniyen var!", reply_markup=_bj_kb(game_id), parse_mode="HTML")
    p["task"] = asyncio.create_task(_bj_timeout(ctx, chat_id, game_id, uid))

async def _bj_timeout(ctx, chat_id, game_id, uid):
    await asyncio.sleep(BLACKJACK_TURN)
    bj = _bj.get(chat_id)
    if not bj or bj["game_id"] != game_id: return
    p = bj["players"].get(uid)
    if not p or p["state"] != "PLAYING": return
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
    if p.get("task"):
        p["task"].cancel()
    if action == "bj_hit":
        card = bj["deck"].pop()
        p["hand"].append(card)
        val = _hand_val(p["hand"])
        hand_img = combine_cards(p["hand"])
        if val > 21:
            await query.edit_message_media(media=InputMediaPhoto(media=hand_img, caption=f"💥 <b>BUST!</b>\n━━━━━━━━━━━━━━━━━━━━━\n👤 {p['name']}\n🃏 Eliniz: {val}\n❌ Kaybettiniz!", parse_mode="HTML"))
            p["state"] = "BUST"
            bj["current"] += 1
            await _bj_next(ctx, chat_id, game_id)
        elif val == 21:
            await query.edit_message_media(media=InputMediaPhoto(media=hand_img, caption=f"🎉 <b>BLACKJACK! 21</b>\n━━━━━━━━━━━━━━━━━━━━━\n👤 {p['name']}\n✅ Otomatik Stand", parse_mode="HTML"))
            p["state"] = "STAND"
            bj["current"] += 1
            await _bj_next(ctx, chat_id, game_id)
        else:
            await query.edit_message_media(media=InputMediaPhoto(media=hand_img, caption=f"🃏 <b>SIRA SENDE</b>\n━━━━━━━━━━━━━━━━━━━━━\n👤 {p['name']}\n🃏 Eliniz: {val}\n⏳ {BLACKJACK_TURN} saniyen var!", parse_mode="HTML"), reply_markup=_bj_kb(game_id))
            p["task"] = asyncio.create_task(_bj_timeout(ctx, chat_id, game_id, user.id))
    elif action == "bj_stand":
        hand_val = _hand_val(p["hand"])
        p["state"] = "STAND"
        bj["current"] += 1
        hand_img = combine_cards(p["hand"])
        await query.edit_message_media(media=InputMediaPhoto(media=hand_img, caption=f"✋ <b>STAND</b>\n━━━━━━━━━━━━━━━━━━━━━\n👤 {p['name']}\n🃏 Eliniz: {hand_val} ile durdu.", parse_mode="HTML"))
        await _bj_next(ctx, chat_id, game_id)

async def _bj_dealer(ctx, chat_id, game_id):
    bj = _bj.get(chat_id)
    if not bj or bj["game_id"] != game_id: return
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
        elif dval > 21:
            payout = bet * 2
            await add_balance(uid, payout, "win", f"BJ game:{game_id}")
            await update_stats(uid, payout)
            total_payout += payout
            results.append(f"✅ {p['name']}: {pval} vs {dval} (BUST) → +{format_amount(payout)}")
        elif pval > dval:
            payout = bet * 2
            await add_balance(uid, payout, "win", f"BJ game:{game_id}")
            await update_stats(uid, payout)
            total_payout += payout
            results.append(f"✅ {p['name']}: {pval} vs {dval} → +{format_amount(payout)}")
        elif pval == dval:
            await add_balance(uid, bet, "refund", f"BJ game:{game_id}")
            results.append(f"🤝 {p['name']}: {pval} vs {dval} → İADE")
        else:
            results.append(f"❌ {p['name']}: {pval} vs {dval} → -{format_amount(bet)}")
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
    msg = await update.message.reply_text(f"🎲 <b>ZAR OYUNU BAŞLADI! (PvP)</b>\n━━━━━━━━━━━━━━━━━━━━━\n⏱ <b>{BET_WINDOW} saniye</b> içinde katılın!\n\n📌 /dice &lt;miktar&gt; veya /dice allin\n🎯 En yüksek zar toplamı kazanır!\n🤝 Beraberlikte havuz bölüşülür.", parse_mode="HTML")
    game = await create_game(chat_id, "dice", msg.message_id)
    async with _state_lock:
        if chat_id in _active_games and game["game_id"] in _active_games[chat_id]:
            _active_games[chat_id][game["game_id"]]["min_bet"] = 0
            _active_games[chat_id][game["game_id"]]["players_rolled"] = {}
            _active_games[chat_id][game["game_id"]]["current_player_index"] = 0
            _active_games[chat_id][game["game_id"]]["order"] = []
            _active_games[chat_id][game["game_id"]]["pool"] = 0
            _active_games[chat_id][game["game_id"]]["participants_data"] = {}
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
    ok = await remove_balance(user.id, amount, "bet", f"Zar game:{game['game_id']}")
    if not ok:
        await update.message.reply_text("❌ Yetersiz bakiye.")
        return
    await add_participant(chat_id, game["game_id"], user.id, amount, {"name": user.full_name})
    await update.message.reply_text(f"🎲 <b>{user.full_name}</b> — {format_amount(amount)} katıldı!", parse_mode="HTML")

async def _dice_bet_timer(ctx, chat_id, game_id):
    await asyncio.sleep(BET_WINDOW)
    game = await get_active_game(chat_id, "dice")
    if not game or game["game_id"] != game_id: return
    parts = await get_participants(chat_id, game_id)
    if len(parts) < 2:
        for uid, data in parts.items():
            await add_balance(uid, data["bet"], "refund", f"Zar iade game:{game_id}")
        await ctx.bot.send_message(chat_id, "❌ Zar oyunu iptal! En az 2 oyuncu gerekli. Bahisler iade edildi.", parse_mode="HTML")
        await finish_game(chat_id, game_id, "iptal")
        await cleanup(chat_id)
        return
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if game_data:
            game_data["state"] = "ROLLING"
            game_data["order"] = list(parts.keys())
            game_data["players_rolled"] = {}
            game_data["current_player_index"] = 0
            game_data["pool"] = sum(data["bet"] for data in parts.values())
            game_data["participants_data"] = parts
    await _dice_next_player(ctx, chat_id, game_id)

async def _dice_next_player(ctx, chat_id, game_id):
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data: return
        idx = game_data["current_player_index"]
        order = game_data["order"]
        if idx >= len(order):
            await _dice_calculate_results(ctx, chat_id, game_id)
            return
        uid = order[idx]
        parts = game_data["participants_data"]
        player_name = parts[uid]["bet_data"]["name"]
        bet = parts[uid]["bet"]
    keyboard = [[InlineKeyboardButton("🎲 ZAR AT 🎲", callback_data=f"dice_roll:{game_id}:{uid}")]]
    await ctx.bot.send_message(chat_id, f"🎲 <b>SIRA SENDE!</b>\n━━━━━━━━━━━━━━━━━━━━━\n👤 Oyuncu: <b>{player_name}</b>\n💰 Bahis: {format_amount(bet)}\n🎯 Toplam havuz: {format_amount(game_data['pool'])}\n\n⏱ <b>15 saniyen var!</b>\n⬇️ Zar atmak için butona tıkla ⬇️", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    async with _state_lock:
        if game_id in _active_games.get(chat_id, {}):
            _active_games[chat_id][game_id]["roll_task"] = asyncio.create_task(_dice_roll_timeout(ctx, chat_id, game_id, uid))

async def _dice_roll_timeout(ctx, chat_id, game_id, uid):
    await asyncio.sleep(15)
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data or uid in game_data["players_rolled"]: return
        game_data["players_rolled"][uid] = 2
        parts = game_data["participants_data"]
        player_name = parts[uid]["bet_data"]["name"]
    await ctx.bot.send_message(chat_id, f"⏰ <b>{player_name}</b> süresinde zar atmadı!\n❌ En düşük puan (2) olarak kaydedildi.", parse_mode="HTML")
    async with _state_lock:
        if game_data:
            game_data["current_player_index"] += 1
    await _dice_next_player(ctx, chat_id, game_id)

async def dice_roll_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        _, game_id, uid = query.data.split(":", 2)
        uid = int(uid)
    except:
        await query.answer("Hata!", show_alert=True)
        return
    user = query.from_user
    chat_id = query.message.chat_id
    if user.id != uid:
        await query.answer("Bu senin sıran değil!", show_alert=True)
        return
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data or uid in game_data["players_rolled"]:
            await query.answer("Oyun bitti veya zaten zar attın!", show_alert=True)
            return
        if game_data.get("roll_task"):
            game_data["roll_task"].cancel()
        dice1 = random.randint(1, 6)
        dice2 = random.randint(1, 6)
        total = dice1 + dice2
        game_data["players_rolled"][uid] = total
        parts = game_data["participants_data"]
        player_name = parts[uid]["bet_data"]["name"]
    await query.message.reply_text(f"🎲 <b>{player_name}</b> zarları attı!\n├─ 1. zar: {dice1}\n├─ 2. zar: {dice2}\n└─ Toplam: <b>{total}</b>", parse_mode="HTML")
    async with _state_lock:
        if game_data:
            game_data["current_player_index"] += 1
    await _dice_next_player(ctx, chat_id, game_id)
    try:
        await query.message.delete()
    except: pass

async def _dice_calculate_results(ctx, chat_id, game_id):
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data: return
        parts = game_data["participants_data"]
        rolled = game_data["players_rolled"]
        pool = game_data["pool"]
    max_score = max(rolled.values())
    winners = [uid for uid, score in rolled.items() if score == max_score]
    share = pool // len(winners)
    lines = ["🎲 <b>ZAR OYUNU SONUÇLARI</b>", "━━━━━━━━━━━━━━━━━━━━━", f"💰 Toplam havuz: {format_amount(pool)}", f"🏆 En yüksek skor: <b>{max_score}</b>", f"👥 Kazanan sayısı: {len(winners)}", "━━━━━━━━━━━━━━━━━━━━━", ""]
    for uid in winners:
        player_name = parts[uid]["bet_data"]["name"]
        bet = parts[uid]["bet"]
        await add_balance(uid, share, "win", f"Zar kazancı game:{game_id}")
        await update_stats(uid, share)
        lines.append(f"✅ {player_name} +{format_amount(share - bet)} (Toplam: {format_amount(share)})")
    for uid, data in parts.items():
        if uid not in winners:
            player_name = data["bet_data"]["name"]
            bet = data["bet"]
            await update_stats(uid, 0)
            lines.append(f"❌ {player_name} -{format_amount(bet)}")
    lines.append(f"\n🆔 <code>{game_id}</code>")
    await ctx.bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")
    await finish_game(chat_id, game_id, f"max:{max_score}")
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
    msg = await update.message.reply_text(f"🎡 <b>ÇARKIFELEK BAŞLADI!</b>\n━━━━━━━━━━━━━━━━━━━━━\n⏱ <b>{BET_WINDOW} saniye</b>\n\n📌 /wheel &lt;miktar&gt; veya /wheel allin\n\n💀 PASS | 2x | 3x | 5x | 10x | 25x | 50x | 100x | 250x", parse_mode="HTML")
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
    await update.message.reply_text(f"🕹 <b>{user.full_name}</b> 🎡 {format_amount(amount)}🪙 bahis yaptı", parse_mode="HTML")

async def _wheel_timer(ctx, chat_id, game_id):
    await asyncio.sleep(BET_WINDOW)
    game = await get_active_game(chat_id, "wheel")
    if not game or game["game_id"] != game_id: return
    async with _state_lock:
        if game_id in _active_games.get(chat_id, {}):
            _active_games[chat_id][game_id]["state"] = "CALCULATING"
    label, mult = secrets.choice(WHEEL_SEGMENTS)
    parts = await get_participants(chat_id, game_id)
    lines = [f"🎡 <b>ÇARK DÖNDÜ!</b>", "━━━━━━━━━━━━━━━━━━━━━", f"🎯 Sonuç: <b>{label}</b>", f"🆔 <code>{game_id}</code>", ""]
    total_payout = 0
    if not parts:
        lines.append("😴 Kimse bahis yapmadı.")
    elif mult == 0:
        lines.append("💀 <b>PASS!</b> Herkes kaybetti.")
        for uid, d in parts.items():
            await update_stats(uid, 0)
            lines.append(f"  ❌ {d['bet_data']['name']} -{format_amount(d['bet'])}")
    else:
        lines.append(f"🏆 <b>{label} ({mult}x)</b>")
        for uid, d in parts.items():
            payout = d["bet"] * mult
            await add_balance(uid, payout, "win", f"Çark game:{game_id}")
            await update_stats(uid, payout)
            total_payout += payout
            lines.append(f"  ✅ {d['bet_data']['name']} +{format_amount(payout - d['bet'])}")
    if mult > 0:
        lines.append(f"\n💰 Toplam dağıtılan: {format_amount(total_payout)}")
    await ctx.bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")
    await finish_game(chat_id, game_id, label)
    await cleanup(chat_id)


# ═══════════════════════════════════════════════════════════════
#  KAZI KAZAN - SOLO & TURNUV A
# ═══════════════════════════════════════════════════════════════

async def cmd_kazisolo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_rate_limited(user.id): return
    if not ctx.args:
        await update.message.reply_text("🎟 <b>KAZI KAZAN (SOLO)</b>\n━━━━━━━━━━━━━━━━━━━━━\n📌 Kullanım: <code>/kazisolo &lt;miktar&gt;</code>\nveya <code>/kazisolo allin</code>\n\n🏆 Çarpanlar: 2x, 3x, 5x, 10x, 25x, 50x, 100x, 250x\n🎯 6 kutuda 3 aynı çarpan = kazanç!", parse_mode="HTML")
        return
    await get_or_create_user(user.id, user.username, user.full_name)
    bal = await get_balance(user.id)
    amount, err = parse_amount(ctx.args[0], bal)
    if err:
        await update.message.reply_text(f"❌ {err}")
        return
    ok = await remove_balance(user.id, amount, "bet", "Kazı Kazan Solo")
    if not ok:
        await update.message.reply_text("❌ Yetersiz bakiye.")
        return
    if os.path.exists(KAPALI_KART_PATH):
        with open(KAPALI_KART_PATH, "rb") as photo:
            await update.message.reply_photo(photo=photo, caption=f"🎟 <b>KAZI KAZAN (SOLO)</b>\n━━━━━━━━━━━━━━━━━━━━━\n💰 Bahis: {format_amount(amount)}\n✨ KAZIYORSUN... ✨", parse_mode="HTML")
    else:
        await update.message.reply_text(f"🎟 <b>KAZI KAZAN (SOLO)</b>\n━━━━━━━━━━━━━━━━━━━━━\n💰 Bahis: {format_amount(amount)}\n✨ KAZIYORSUN... ✨", parse_mode="HTML")
    await asyncio.sleep(1.5)
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
        else:
            await update_stats(user.id, 0)
            msg = f"❌ Eşleşme yok!\n💀 KAYBETTİN! -{format_amount(amount)}"
        new_bal = await get_balance(user.id)
        await update.message.reply_photo(photo=result_img, caption=f"🎟 <b>KAZI KAZAN (SOLO)</b>\n━━━━━━━━━━━━━━━━━━━━━\n{msg}\n💳 Yeni bakiye: {format_amount(new_bal)}", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Kazı Kazan görsel hatası: {e}")
        if winner_mult > 0:
            await add_balance(user.id, payout, "win", f"Kazı Solo {winner_mult}x")
            await update_stats(user.id, payout)
            await update.message.reply_text(f"🎟 <b>KAZI KAZAN (SOLO)</b>\n━━━━━━━━━━━━━━━━━━━━━\n✅ {winner_mult}x bulundu!\n🎉 KAZANDIN! +{format_amount(payout - amount)}\n💳 Yeni bakiye: {format_amount(new_bal)}", parse_mode="HTML")
        else:
            await update_stats(user.id, 0)
            await update.message.reply_text(f"🎟 <b>KAZI KAZAN (SOLO)</b>\n━━━━━━━━━━━━━━━━━━━━━\n❌ Eşleşme yok!\n💀 KAYBETTİN! -{format_amount(amount)}", parse_mode="HTML")

async def cmd_kazibet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if is_rate_limited(user.id): return
    ok, err = await can_open_game(chat_id, "scratch_tournament")
    if not ok:
        await update.message.reply_text(f"❌ {err}")
        return
    caption = f"🎟 <b>KAZI KAZAN TURNUVASI!</b>\n━━━━━━━━━━━━━━━━━━━━━\n⏱ <b>{BET_WINDOW} saniye</b> içinde katıl!\n📌 /kazi &lt;miktar&gt;\n🎯 Herkes aynı kartı kazır!"
    if os.path.exists(KAPALI_KART_PATH):
        with open(KAPALI_KART_PATH, "rb") as photo:
            msg = await update.message.reply_photo(photo=photo, caption=caption, parse_mode="HTML")
    else:
        msg = await update.message.reply_text(caption, parse_mode="HTML")
    game = await create_game(chat_id, "scratch_tournament", msg.message_id)
    async with _state_lock:
        if chat_id in _active_games and game["game_id"] in _active_games[chat_id]:
            _active_games[chat_id][game["game_id"]]["min_bet"] = 0
            _active_games[chat_id][game["game_id"]]["pool"] = 0
            _active_games[chat_id][game["game_id"]]["players"] = {}
    asyncio.create_task(_scratch_countdown(ctx, chat_id, game["game_id"], msg.message_id))
    asyncio.create_task(_scratch_tournament_timer(ctx, chat_id, game["game_id"]))

async def cmd_kazi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    if is_rate_limited(user.id): return
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
    ok = await remove_balance(user.id, amount, "bet", f"Kazi Turnuva {game['game_id']}")
    if not ok:
        await update.message.reply_text("❌ Yetersiz bakiye.")
        return
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game["game_id"])
        if game_data:
            if user.id in game_data["players"]:
                game_data["players"][user.id]["bet"] += amount
            else:
                game_data["players"][user.id] = {"bet": amount, "name": user.full_name}
            game_data["pool"] = game_data.get("pool", 0) + amount
    await update.message.reply_text(f"🕹 <b>{user.full_name}</b> 🎟️ {format_amount(amount)} ile katıldı.", parse_mode="HTML")

async def _scratch_countdown(ctx, chat_id, game_id, message_id):
    for remaining in range(BET_WINDOW, 0, -5):
        await asyncio.sleep(5)
        game = await get_active_game(chat_id, "scratch_tournament")
        if not game or game["game_id"] != game_id or game["state"] != "OPEN": return
        async with _state_lock:
            game_data = _active_games.get(chat_id, {}).get(game_id)
            if not game_data: return
            players_count = len(game_data.get("players", {}))
            pool = game_data.get("pool", 0)
        try:
            await ctx.bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption=f"🎟 <b>KAZI KAZAN TURNUVASI</b>\n━━━━━━━━━━━━━━━━━━━━━\n⏱ Kalan: {remaining} sn\n👥 Katılımcı: {players_count}\n💰 Havuz: {format_amount(pool)}", parse_mode="HTML")
        except: pass

async def _scratch_tournament_timer(ctx, chat_id, game_id):
    await asyncio.sleep(BET_WINDOW)
    game = await get_active_game(chat_id, "scratch_tournament")
    if not game or game["game_id"] != game_id: return
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data: return
        players = game_data.get("players", {}).copy()
    if len(players) < 2:
        for uid, d in players.items():
            await add_balance(uid, d["bet"], "refund", "Kazi Turnuva İptal")
        await ctx.bot.send_message(chat_id, "❌ KAZI KAZAN TURNUVASI İPTAL!\nEn az 2 oyuncu gerekli. Bahisler iade edildi.", parse_mode="HTML")
        await finish_game(chat_id, game_id, "iptal")
        await cleanup(chat_id)
        return
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
            lines.append(f"\n💰 Toplam dağıtılan: {format_amount(total_payout)}")
        else:
            lines.append(f"❌ Eşleşme yok!\n😢 <b>HERKES KAYBETTİ!</b>\n")
            for uid, d in players.items():
                await update_stats(uid, 0)
                lines.append(f"❌ {d['name']}: -{format_amount(d['bet'])}")
        await ctx.bot.send_photo(chat_id, photo=result_img, caption="\n".join(lines), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Kazi turnuva görsel hatası: {e}")
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
#  MENU
# ═══════════════════════════════════════════════════════════════

async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await get_or_create_user(user.id, user.username, user.full_name)
    bal = await get_balance(user.id)
    lvl, emoji = get_level(bal)
    menu_text = f"🎰 <b>CASİNO MENÜ</b>\n━━━━━━━━━━━━━━━━━━━━━\n👤 {user.full_name} [{lvl}] {emoji}\n💰 Bakiye: {format_amount(bal)}\n━━━━━━━━━━━━━━━━━━━━━\n🎮 Aşağıdaki butonlardan bir oyun seçin:"
    keyboard = [
        [InlineKeyboardButton("🎰 RULET", callback_data="menu_roulette"), InlineKeyboardButton("🃏 BLACKJACK", callback_data="menu_blackjack")],
        [InlineKeyboardButton("🎲 ZAR (PvP)", callback_data="menu_dice"), InlineKeyboardButton("🎡 ÇARKIFELEK", callback_data="menu_wheel")],
        [InlineKeyboardButton("🎟 KAZI KAZAN", callback_data="menu_scratch"), InlineKeyboardButton("🏆 LİDERLİK", callback_data="menu_leaderboard")],
        [InlineKeyboardButton("💰 BAKİYE", callback_data="menu_balance"), InlineKeyboardButton("⭐ SATIN AL", callback_data="menu_buy")],
        [InlineKeyboardButton("❓ YARDIM", callback_data="menu_help")]
    ]
    await update.message.reply_text(menu_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def menu_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    chat_id = query.message.chat_id
    action = query.data
    if is_rate_limited(user.id):
        await query.edit_message_text("⏰ Lütfen biraz bekleyin!", parse_mode="HTML")
        return
    if action == "menu_roulette":
        await query.edit_message_text("🎰 Rulet başlatılıyor...", parse_mode="HTML")
        await cmd_rulet(update, ctx)
    elif action == "menu_blackjack":
        await query.edit_message_text("🃏 Blackjack başlatılıyor...", parse_mode="HTML")
        await cmd_blackjack(update, ctx)
    elif action == "menu_dice":
        await query.edit_message_text("🎲 Zar oyunu başlatılıyor...", parse_mode="HTML")
        await cmd_dicebet(update, ctx)
    elif action == "menu_wheel":
        await query.edit_message_text("🎡 Çarkıfelek başlatılıyor...", parse_mode="HTML")
        await cmd_wheelbet(update, ctx)
    elif action == "menu_scratch":
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🎟 SOLO OYNA", callback_data="scratch_solo"), InlineKeyboardButton("👥 TURNUVASI", callback_data="scratch_tournament")], [InlineKeyboardButton("🔙 GERİ", callback_data="menu_back")]])
        await query.edit_message_text("🎟 <b>KAZI KAZAN</b>\n━━━━━━━━━━━━━━━━━━━━━\n• <b>SOLO OYNA</b>: Tek başına, anında kazı\n• <b>TURNUVASI</b>: Diğer oyuncularla, herkes aynı kartı kazar", reply_markup=keyboard, parse_mode="HTML")
    elif action == "scratch_solo":
        await query.edit_message_text("🎟 Solo Kazı Kazan başlatılıyor...\nÖrnek: /kazisolo 1000", parse_mode="HTML")
    elif action == "scratch_tournament":
        await query.edit_message_text("👥 Kazı Kazan Turnuvası başlatılıyor...", parse_mode="HTML")
        await cmd_kazibet(update, ctx)
    elif action == "menu_leaderboard":
        await query.edit_message_text("🏆 Liderlik tablosu yükleniyor...", parse_mode="HTML")
        await cmd_leaderboard(update, ctx)
    elif action == "menu_balance":
        await query.edit_message_text("💰 Bakiye sorgulanıyor...", parse_mode="HTML")
        await cmd_balance(update, ctx)
    elif action == "menu_buy":
        await query.edit_message_text("⭐ Satın alma menüsü açılıyor...", parse_mode="HTML")
        await cmd_buy(update, ctx)
    elif action == "menu_help":
        await query.edit_message_text("❓ Yardım menüsü açılıyor...", parse_mode="HTML")
        await cmd_help(update, ctx)
    elif action == "menu_back":
        await cmd_menu(update, ctx)


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Genel komutlar
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("menu", cmd_menu))
    application.add_handler(CommandHandler("balance", cmd_balance))
    application.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    application.add_handler(CommandHandler("changename", cmd_changename))
    application.add_handler(CommandHandler("daily", cmd_daily))
    application.add_handler(CommandHandler("moneys", cmd_moneys))
    application.add_handler(CommandHandler("buy", cmd_buy))
    
    # Rulet
    application.add_handler(CommandHandler("rulet", cmd_rulet))
    application.add_handler(CommandHandler("red", cmd_red))
    application.add_handler(CommandHandler("black", cmd_black))
    application.add_handler(CommandHandler("green", cmd_green))
    application.add_handler(CommandHandler("number", cmd_number))
    application.add_handler(CommandHandler("numbers", cmd_numbers))
    
    # Blackjack
    application.add_handler(CommandHandler("blackjack", cmd_blackjack))
    application.add_handler(CommandHandler("bj", cmd_bj))
    
    # Zar
    application.add_handler(CommandHandler("dicebet", cmd_dicebet))
    application.add_handler(CommandHandler("dice", cmd_dice))
    
    # Çarkıfelek
    application.add_handler(CommandHandler("wheelbet", cmd_wheelbet))
    application.add_handler(CommandHandler("wheel", cmd_wheel))
    
    # Kazı Kazan
    application.add_handler(CommandHandler("kazisolo", cmd_kazisolo))
    application.add_handler(CommandHandler("kazibet", cmd_kazibet))
    application.add_handler(CommandHandler("kazi", cmd_kazi))
    
    # Callback handler'lar
    application.add_handler(CallbackQueryHandler(bj_callback, pattern="^bj_"))
    application.add_handler(CallbackQueryHandler(dice_roll_callback, pattern="^dice_roll:"))
    application.add_handler(CallbackQueryHandler(buy_callback, pattern="^buy_"))
    application.add_handler(CallbackQueryHandler(menu_callback, pattern="^(menu_|scratch_)"))
    
    # Ödeme handler'ları
    application.add_handler(PreCheckoutQueryHandler(pre_checkout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    asyncio.run(init_db())
    main()

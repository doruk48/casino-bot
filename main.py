import asyncio
import logging
import os
import secrets
import random
import time
import uuid
from collections import Counter
from datetime import datetime
from bson.decimal128 import Decimal128
from decimal import Decimal

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
#  FONT BULMA FONKSİYONU
# ═══════════════════════════════════════════════════════════════

def get_font(size: int):
    """Sistemdeki fontları dene, hiçbiri yoksa default kullan"""
    
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        "/system/fonts/Roboto-Bold.ttf",
    ]
    
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
    
    print(f"⚠️ Font bulunamadı, default kullanılıyor (boyut: {size})")
    return ImageFont.load_default()


# ═══════════════════════════════════════════════════════════════
#  AYARLAR
# ═══════════════════════════════════════════════════════════════

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

STARTING_BALANCE = 1000000
CURRENCY_SYMBOL = "🪙BTK"
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
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["♠️", "♥️", "♦️", "♣️"]

# Kazı Kazan
KAPALI_KART_PATH = os.path.join(BASE_DIR, "Kapali.jpg")
ACIK_KART_PATH = os.path.join(BASE_DIR, "acik.jpg")

# Transfer
TRANSFER_TEMPLATE_PATH = os.path.join(BASE_DIR, "transfer.png")

# Çarkıfelek - KASA LEHİNE DAĞILIM
WHEEL_SEGMENTS = [
    # 💀 PASS - 6 adet
    ("💀 PASS 💀", 0), ("💀 PASS 💀", 0), ("💀 PASS 💀", 0),
    ("💀 PASS 💀", 0), ("💀 PASS 💀", 0), ("💀 PASS 💀", 0),
    
    # 🎰 JACKPOT - 1 adet
    ("🎰 JACKPOT 🎰", -1),
    
    # 🔄 İADE - 5 adet
    ("🔄 İADE 🔄", 1), ("🔄 İADE 🔄", 1), ("🔄 İADE 🔄", 1),
    ("🔄 İADE 🔄", 1), ("🔄 İADE 🔄", 1),
    
    # Çarpanlar (toplam 8 adet)
    ("🟢 2x", 2), ("🟢 2x", 2), ("🟢 2x", 2),
    ("🟢 3x", 3), ("🟢 3x", 3),
    ("🔵 5x", 5),
    ("🔵 10x", 10),
    ("🟡 100x", 100),
]
random.shuffle(WHEEL_SEGMENTS)

# Kazı Kazan
SCRATCH_SYMBOLS = [
    (250, 1), (100, 2), (50, 3), (20, 5), (10, 10),
    (5, 15), (3, 20), (2, 29), (0, 15),
]
SCRATCH_POOL = []
for val, weight in SCRATCH_SYMBOLS:
    SCRATCH_POOL.extend([val] * weight)

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
    await db.users.create_index("telegram_id", unique=True)
    await db.transactions.create_index("from_id")
    await db.transactions.create_index("to_id")
    await db.games.create_index([("chat_id", 1), ("state", 1)])
    await db.game_participants.create_index("game_id")
    await db.user_stats.create_index("telegram_id", unique=True)
    await db.groups.create_index("chat_id", unique=True)  # <-- EKLENDİ
    logger.info("🚀 MongoDB bağlantısı kuruldu!")


# ═══════════════════════════════════════════════════════════════
#  EKONOMİ FONKSİYONLARI
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

def format_amount(amount) -> str:
    """Büyük sayıları formatla - Decimal128, Decimal veya int kabul eder"""
    if amount is None:
        amount = 0
    if isinstance(amount, Decimal128):
        amount = int(amount.to_decimal())
    elif isinstance(amount, Decimal):
        amount = int(amount)
    else:
        try:
            amount = int(amount)
        except:
            amount = 0
    
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
            # Yeni kullanıcı - Decimal128 ile oluştur
            user_data = {
                "telegram_id": uid,
                "username": username,
                "display_name": name,
                "balance": Decimal128(str(STARTING_BALANCE)),
                "total_wagered": Decimal128("0"),
                "total_won": Decimal128("0"),
                "games_played": 0,
                "last_daily": None,
                "daily_streak": 0,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            await db.users.insert_one(user_data)
            
            await db.transactions.insert_one({
                "to_id": uid,
                "amount": Decimal128(str(STARTING_BALANCE)),
                "type": "bonus",
                "description": "Başlangıç",
                "created_at": datetime.now()
            })
            
            user = await db.users.find_one({"telegram_id": uid})
            
        else:
            # Mevcut kullanıcı - balance eski tipteyse dönüştür
            balance = user.get("balance", 0)
            total_wagered = user.get("total_wagered", 0)
            total_won = user.get("total_won", 0)
            
            updates = {}
            
            # Balance dönüşümü
            if not isinstance(balance, Decimal128):
                old_balance = int(balance) if balance else 0
                updates["balance"] = Decimal128(str(old_balance))
            
            # Total wagered dönüşümü
            if not isinstance(total_wagered, Decimal128) and total_wagered:
                updates["total_wagered"] = Decimal128(str(int(total_wagered)))
            
            # Total won dönüşümü
            if not isinstance(total_won, Decimal128) and total_won:
                updates["total_won"] = Decimal128(str(int(total_won)))
            
            if updates:
                updates["updated_at"] = datetime.now()
                await db.users.update_one(
                    {"telegram_id": uid},
                    {"$set": updates}
                )
                logger.info(f"🔄 Kullanıcı {uid} bakiyesi Decimal128'e dönüştürüldü")
            
            # İsim güncelleme
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
    if not u:
        return 0
    balance = u.get("balance", 0)
    if isinstance(balance, Decimal128):
        return int(balance.to_decimal())
    elif isinstance(balance, Decimal):
        return int(balance)
    return int(balance) if balance else 0

async def add_balance(uid: int, amount: int, tx_type="win", desc="") -> bool:
    if amount <= 0:
        return False
    
    db = await get_db()
    lock = await _get_lock(uid)
    
    async with lock:
        try:
            # Decimal128 ile sınırsız büyük sayı desteği
            result = await db.users.update_one(
                {"telegram_id": uid},
                {"$inc": {"balance": Decimal128(str(amount))}, 
                 "$set": {"updated_at": datetime.now()}}
            )
            
            if result.modified_count > 0:
                await db.transactions.insert_one({
                    "to_id": uid,
                    "amount": Decimal128(str(amount)),
                    "type": tx_type,
                    "description": desc[:200],
                    "created_at": datetime.now()
                })
                return True
                
        except Exception as e:
            logger.error(f"Bakiye eklenirken hata: {e}")
            return False
    
    return False

async def remove_balance(uid: int, amount: int, tx_type="bet", desc="") -> bool:
    if amount <= 0:
        return False
    
    db = await get_db()
    lock = await _get_lock(uid)
    
    async with lock:
        user = await db.users.find_one({"telegram_id": uid})
        if not user:
            return False
        
        # Decimal128'i Python int'e çevir
        current_balance = user.get("balance", 0)
        if isinstance(current_balance, Decimal128):
            current_balance = int(current_balance.to_decimal())
        elif isinstance(current_balance, Decimal):
            current_balance = int(current_balance)
        else:
            current_balance = int(current_balance) if current_balance else 0
        
        if current_balance < amount:
            return False
        
        result = await db.users.update_one(
            {"telegram_id": uid},
            {"$inc": {
                "balance": Decimal128(str(-amount)), 
                "total_wagered": Decimal128(str(amount))
            },
             "$set": {"updated_at": datetime.now()}}
        )
        
        if result.modified_count > 0:
            await db.transactions.insert_one({
                "from_id": uid,
                "amount": Decimal128(str(amount)),
                "type": tx_type,
                "description": desc[:200],
                "created_at": datetime.now()
            })
            return True
    
    return False

async def update_stats(uid: int, won: int):
    db = await get_db()
    async with await _get_lock(uid):
        await db.users.update_one(
            {"telegram_id": uid},
            {"$inc": {
                "total_won": Decimal128(str(won)), 
                "games_played": 1
            }, "$set": {"updated_at": datetime.now()}}
        )

async def update_win_rate(uid: int, game_type: str, won: bool):
    """Win rate güncelle"""
    try:
        db = await get_db()
        
        # Önce mevcut istatistikleri al
        stats = await db.user_stats.find_one({"telegram_id": uid})
        
        if not stats:
            # Yeni istatistik oluştur
            stats = {
                "telegram_id": uid,
                "roulette_total": 0, "roulette_wins": 0, "roulette_win_rate": 0,
                "blackjack_total": 0, "blackjack_wins": 0, "blackjack_win_rate": 0,
                "dice_total": 0, "dice_wins": 0, "dice_win_rate": 0,
                "wheel_total": 0, "wheel_wins": 0, "wheel_win_rate": 0,
                "scratch_total": 0, "scratch_wins": 0, "scratch_win_rate": 0,
                "total_win_rate": 0
            }
        
        # İlgili oyunun sayılarını artır
        total_field = f"{game_type}_total"
        wins_field = f"{game_type}_wins"
        
        stats[total_field] = stats.get(total_field, 0) + 1
        if won:
            stats[wins_field] = stats.get(wins_field, 0) + 1
        
        # Win rate hesapla
        if stats[total_field] > 0:
            stats[f"{game_type}_win_rate"] = round((stats[wins_field] / stats[total_field]) * 100, 1)
        
        # Genel win rate hesapla
        all_total = stats.get("roulette_total", 0) + stats.get("blackjack_total", 0) + \
                    stats.get("dice_total", 0) + stats.get("wheel_total", 0) + stats.get("scratch_total", 0)
        all_wins = stats.get("roulette_wins", 0) + stats.get("blackjack_wins", 0) + \
                   stats.get("dice_wins", 0) + stats.get("wheel_wins", 0) + stats.get("scratch_wins", 0)
        
        if all_total > 0:
            stats["total_win_rate"] = round((all_wins / all_total) * 100, 1)
        
        # Veritabanına kaydet
        await db.user_stats.update_one(
            {"telegram_id": uid},
            {"$set": stats},
            upsert=True
        )
        
    except Exception as e:
        logger.error(f"Win rate güncellenemedi: {e}")

async def get_leaderboard(limit=15) -> list[dict]:
    db = await get_db()
    cursor = db.users.find().sort("balance", -1).limit(limit)
    users = await cursor.to_list(length=limit)
    
    # Tüm bakiyeleri int'e çevir
    for user in users:
        balance = user.get("balance", 0)
        if isinstance(balance, Decimal128):
            user["balance"] = int(balance.to_decimal())
        elif isinstance(balance, Decimal):
            user["balance"] = int(balance)
        else:
            try:
                user["balance"] = int(balance) if balance else 0
            except:
                user["balance"] = 0
    
    # Manuel sıralama
    users.sort(key=lambda x: x.get("balance", 0), reverse=True)
    
    return users[:limit]
    
    
    
# ═══════════════════════════════════════════════════════════════
#  STATE MANAGER & OYUN YÖNETİMİ
# ═══════════════════════════════════════════════════════════════

_active_games: dict[int, dict[str, dict]] = {}
_state_lock = asyncio.Lock()

async def can_open_game(chat_id: int, game_type: str) -> tuple[bool, str]:
    """Yeni oyun açılabilir mi kontrol et"""
    async with _state_lock:
        games = _active_games.get(chat_id, {})
        active = [g for g in games.values() if g["state"] != "FINISHED"]
        if len(active) >= MAX_OPEN_GAMES:
            return False, f"Bu grupta zaten {MAX_OPEN_GAMES} aktif oyun var."
        if any(g["game_type"] == game_type for g in active):
            return False, f"Bu grupta zaten açık bir {game_type} oyunu var."
        return True, ""

async def create_game(chat_id: int, game_type: str, message_id: int = 0) -> dict:
    """Yeni oyun oluştur"""
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
    """Aktif oyunu getir"""
    async with _state_lock:
        for g in _active_games.get(chat_id, {}).values():
            if g["game_type"] == game_type and g["state"] != "FINISHED":
                return g
    return None

async def add_participant(chat_id: int, game_id: str, uid: int, bet: int, bet_data: dict):
    """
    Oyuncunun bahsini ekler.
    - Aynı tür bahis varsa toplar
    - Farklı tür bahisleri ayrı tutar
    - bet_data içinde 'type' yoksa, otomatik olarak game_type'dan alır
    """
    async with _state_lock:
        game = _active_games.get(chat_id, {}).get(game_id)
        if not game:
            return

        if uid not in game["participants"]:
            game["participants"][uid] = {"bets": []}

        user_bets = game["participants"][uid]["bets"]
        merged = False
        
        # Bet type yoksa game_type'dan al
        bet_type = bet_data.get("type")
        if not bet_type:
            bet_type = game.get("game_type", "unknown")
            bet_data["type"] = bet_type

        # Aynı tür bahsi bul ve birleştir
        for existing_bet in user_bets:
            existing_bd = existing_bet["bet_data"]
            existing_type = existing_bd.get("type")
            
            # RENK bahisleri için (Rulet)
            if bet_type == "color" and existing_type == "color":
                if bet_data.get("color") == existing_bd.get("color"):
                    existing_bet["bet"] += bet
                    merged = True
                    break
            
            # SAYI bahisleri için (Rulet)
            elif bet_type == "number" and existing_type == "number":
                if set(bet_data.get("numbers", [])) == set(existing_bd.get("numbers", [])):
                    existing_bet["bet"] += bet
                    merged = True
                    break
            
            # DİĞER OYUNLAR için (Zar, Çarkıfelek, Kazı Kazan Turnuva)
            # Bu oyunlarda her oyuncunun tek bir bahsi olur, tekrar bahis yaparsa toplanır
            elif bet_type == existing_type and bet_type in ["dice", "wheel", "scratch_tournament"]:
                existing_bet["bet"] += bet
                merged = True
                break

        # Yeni bahis türü ise ekle
        if not merged:
            user_bets.append({
                "bet": bet,
                "bet_data": bet_data
            })

    # MongoDB'ye kaydet
    db = await get_db()
    
    # Oyuncunun bu oyundaki tüm bahislerini güncelle
    all_bets = []
    total_bet = 0
    for b in user_bets:
        all_bets.append({"bet": b["bet"], "bet_data": b["bet_data"]})
        total_bet += b["bet"]
    
    await db.game_participants.update_one(
        {"game_id": game_id, "telegram_id": uid},
        {"$set": {"bets": all_bets, "bet_amount": total_bet, "updated_at": datetime.now()}},
        upsert=True
    )

async def get_participants(chat_id: int, game_id: str) -> dict:
    """
    Katılımcıları ve bahislerini getir.
    Dönen format: {uid: {"bets": [{"bet": 1000, "bet_data": {...}}, ...]}}
    """
    async with _state_lock:
        game = _active_games.get(chat_id, {}).get(game_id)
        if not game:
            return {}
        
        participants = {}
        for uid, data in game.get("participants", {}).items():
            participants[uid] = {
                "bets": [{"bet": b["bet"], "bet_data": b["bet_data"].copy()} for b in data.get("bets", [])]
            }
        return participants




# ═══════════════════════════════════════════════════════════════
#  JACKPOT SİSTEMİ (TEK FONKSİYON - TÜM OYUNLAR İÇİN)
# ═══════════════════════════════════════════════════════════════

JACKPOT_MINIMUM = 1_000_000_000  # 1B


def create_jackpot_image(game_type: str, winner_name: str) -> io.BytesIO:
    """Jackpot görselinin üzerine kazanan adını yaz"""
    try:
        # Görsel seçimi
        if game_type == "wheel":
            img_path = os.path.join(BASE_DIR, "jackpot_wheel.jpg")
        elif game_type == "blackjack":
            img_path = os.path.join(BASE_DIR, "jackpot_blackjack.jpg")
        else:
            return None
        
        if not os.path.exists(img_path):
            logger.warning(f"⚠️ Jackpot görseli bulunamadı: {img_path}")
            return None
        
        img = Image.open(img_path).convert('RGBA')
        img.thumbnail((800, 600), Image.Resampling.LANCZOS)
        
        width, height = img.size
        txt_layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)
        
        # Font - Transfer ile aynı
        font_isim = get_font(int(height * 0.10))
        
        # Renkler - Parlak Beyaz ve koyu gölge
        gold_color = "#FFFFFF"      # Beyaz
        shadow_color = "#1a1a1a"    # Koyu gri/siyah gölge
        
        # Koordinatlar - "OYUNCU:" yazısının sağı
        name_x = int(width * 0.59)
        name_y = int(height * 0.29)
        
        # Temizlenmiş isim
        clean_name = re.sub(r'[^a-zA-Z0-9ğüşıöçĞÜŞİÖÇ\s]', '', winner_name)
        if not clean_name:
            clean_name = winner_name
        
        # İsmi kısalt (10 karakter sınır)
        if len(clean_name) > 10:
            clean_name = clean_name[:10] + "..."
        
        # Gölgeli isim
        draw.text((name_x + 3, name_y + 3), clean_name, fill=shadow_color, font=font_isim, anchor="lm")
        draw.text((name_x, name_y), clean_name, fill=gold_color, font=font_isim, anchor="lm")
        
        img = Image.alpha_composite(img, txt_layer).convert('RGB')
        bio = io.BytesIO()
        img.save(bio, format='PNG', quality=95)
        bio.seek(0)
        return bio
        
    except Exception as e:
        logger.error(f"❌ Jackpot görseli oluşturulamadı: {e}")
        return None


async def _get_jackpot_amount(game_type: str) -> int:
    """Jackpot miktarını getir"""
    try:
        db = await get_db()
        jackpot = await db.jackpot.find_one({"_id": f"{game_type}_jackpot"})
        
        if not jackpot:
            await db.jackpot.insert_one({
                "_id": f"{game_type}_jackpot",
                "amount": Decimal128(str(JACKPOT_MINIMUM)),
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            })
            return JACKPOT_MINIMUM
        
        amount = jackpot.get("amount", JACKPOT_MINIMUM)
        if isinstance(amount, Decimal128):
            return int(amount.to_decimal())
        return int(amount)
        
    except Exception as e:
        logger.error(f"❌ Jackpot miktarı alınamadı ({game_type}): {e}")
        return JACKPOT_MINIMUM


async def _add_to_jackpot(game_type: str, amount: int) -> int:
    """Jackpot'a para ekle"""
    if amount <= 0:
        return await _get_jackpot_amount(game_type)
    
    try:
        db = await get_db()
        result = await db.jackpot.find_one_and_update(
            {"_id": f"{game_type}_jackpot"},
            {
                "$inc": {"amount": Decimal128(str(amount))},
                "$set": {"updated_at": datetime.now()}
            },
            upsert=True,
            return_document=True
        )
        
        new_amount = result.get("amount", 0)
        if isinstance(new_amount, Decimal128):
            new_amount = int(new_amount.to_decimal())
        
        logger.info(f"🎰 Jackpot'a eklendi ({game_type}): +{format_amount(amount)} → {format_amount(new_amount)}")
        return new_amount
        
    except Exception as e:
        logger.error(f"❌ Jackpot'a eklenemedi ({game_type}, {amount}): {e}")
        return await _get_jackpot_amount(game_type)


async def _reset_jackpot(game_type: str) -> None:
    """Jackpot'u minimuma sıfırla"""
    try:
        db = await get_db()
        await db.jackpot.update_one(
            {"_id": f"{game_type}_jackpot"},
            {
                "$set": {
                    "amount": Decimal128(str(JACKPOT_MINIMUM)),
                    "updated_at": datetime.now()
                }
            },
            upsert=True
        )
        logger.info(f"🎰 Jackpot sıfırlandı ({game_type}): {format_amount(JACKPOT_MINIMUM)}")
        
    except Exception as e:
        logger.error(f"❌ Jackpot sıfırlanamadı ({game_type}): {e}")


async def process_jackpot_on_game_end(game_id: str, result: str, chat_id: int, ctx=None) -> None:
    """
    ANA JACKPOT FONKSİYONU - TÜM OYUNLAR İÇİN
    finish_game içinden çağrılır.
    """
    try:
        db = await get_db()
        game = await db.games.find_one({"game_id": game_id})
        
        if not game:
            logger.warning(f"⚠️ Jackpot: Oyun bulunamadı {game_id}")
            return
        
        game_type = game.get("game_type")
        
        # Sadece desteklenen oyunlar
        if game_type not in ["wheel", "blackjack"]:
            return
        
        # Katılımcıları al
        participants = await db.game_participants.find({"game_id": game_id}).to_list(None)
        if not participants:
            logger.info(f"ℹ️ Jackpot: Katılımcı yok {game_id}")
            return
        
        # =========================================================
        # ÇARKIFELEK JACKPOT
        # =========================================================
        if game_type == "wheel":
            
            if "PASS" in result:
                # PASS: Tüm bahisler havuza
                for p in participants:
                    bet = p.get("bet_amount", 0)
                    if isinstance(bet, Decimal128):
                        bet = int(bet.to_decimal())
                    else:
                        bet = int(bet) if bet else 0
                    if bet > 0:
                        await _add_to_jackpot("wheel", bet)
                logger.info(f"🎰 Çarkıfelek PASS: Bahisler havuza eklendi. Game: {game_id}")
                
            elif "İADE" in result:
                # İADE: %10 komisyon havuza
                for p in participants:
                    bet = p.get("bet_amount", 0)
                    if isinstance(bet, Decimal128):
                        bet = int(bet.to_decimal())
                    else:
                        bet = int(bet) if bet else 0
                    commission = int(bet * 0.1)
                    if commission > 0:
                        await _add_to_jackpot("wheel", commission)
                logger.info(f"🎰 Çarkıfelek İADE: %10 komisyon havuza eklendi. Game: {game_id}")
                
            elif "JACKPOT" in result:
                # JACKPOT: Havuz eşit pay + bahis iadesi
                jackpot_amount = await _get_jackpot_amount("wheel")
                total_players = len(participants)
                
                if total_players > 0 and jackpot_amount > JACKPOT_MINIMUM:
                    jackpot_per_player = jackpot_amount // total_players
                    
                    for p in participants:
                        uid = p["telegram_id"]
                        bet = p.get("bet_amount", 0)
                        if isinstance(bet, Decimal128):
                            bet = int(bet.to_decimal())
                        else:
                            bet = int(bet) if bet else 0
                        
                        # Oyuncu adını al
                        user = await db.users.find_one({"telegram_id": uid})
                        player_name = user.get("display_name", str(uid)) if user else str(uid)
                        
                        # Bahis iadesi + jackpot payı
                        total_win = bet + jackpot_per_player
                        
                        await add_balance(uid, total_win, "win", f"Çark JACKPOT! game:{game_id}")
                        await update_stats(uid, total_win)
                        await update_win_rate(uid, "wheel", True)
                        
                        # Görsel oluştur ve gönder
                        if ctx:
                            jackpot_img = create_jackpot_image("wheel", player_name)
                            caption = (
                                f"🎰 <b>JACKPOT KAZANDIN!</b> 🎰\n"
                                f"━━━━━━━━━━━━━━━━━━━━━\n"
                                f"🆔 GAME ID: {game_id}\n"
                                f"🎡 Oyun: Çarkıfelek\n"
                                f"💰 Havuz Payın: {format_amount(jackpot_per_player)}\n"
                                f"🎁 Bahis İaden: {format_amount(bet)}\n"
                                f"💳 Toplam: {format_amount(total_win)}\n\n"
                                f"🎉 <b>TEBRİKLER!</b> 🎉"
                            )
                            
                            if jackpot_img:
                                await ctx.bot.send_photo(chat_id, photo=jackpot_img, caption=caption, parse_mode="HTML")
                            else:
                                await ctx.bot.send_message(chat_id, caption, parse_mode="HTML")
                    
                    await _reset_jackpot("wheel")
                    logger.info(f"🎰 Çarkıfelek JACKPOT dağıtıldı: {format_amount(jackpot_amount)}. Game: {game_id}")
        
        # =========================================================
        # BLACKJACK JACKPOT
        # =========================================================
        elif game_type == "blackjack":
            
            # Önce kayıpları ve BUST'ları havuza ekle
            for p in participants:
                uid = p["telegram_id"]
                bet = p.get("bet_amount", 0)
                if isinstance(bet, Decimal128):
                    bet = int(bet.to_decimal())
                else:
                    bet = int(bet) if bet else 0
                
                # Oyuncunun durumunu bul
                player_state = None
                for bj_player in p.get("bets", []):
                    # Blackjack oyuncu durumu _bj içinden veya game_participants'tan alınabilir
                    pass
                
                # BUST: %100 havuza
                # KAYBETME: %25 havuza
                # BERABERLİK: %10 havuza
                # Bu kısım _bj_dealer'dan gelen sonuçlara göre işlenecek
                # Şimdilik result string'ine göre kontrol edelim
            
            # Eğer result içinde "BLACKJACK" veya "21" varsa havuzu dağıt
            if "BLACKJACK" in result.upper() or "21" in result:
                jackpot_amount = await _get_jackpot_amount("blackjack")
                
                # 21 yapanları bul
                winners_21 = []
                for p in participants:
                    # 21 yapanları tespit et
                    # Şimdilik basit: result'ta isim varsa
                    pass
                
                if winners_21 and jackpot_amount > JACKPOT_MINIMUM:
                    jackpot_per_winner = jackpot_amount // len(winners_21)
                    
                    for uid, bet, player_name in winners_21:
                        total_win = bet + jackpot_per_winner
                        
                        await add_balance(uid, total_win, "win", f"Blackjack JACKPOT! game:{game_id}")
                        await update_stats(uid, total_win)
                        await update_win_rate(uid, "blackjack", True)
                        
                        if ctx:
                            jackpot_img = create_jackpot_image("blackjack", player_name)
                            caption = (
                                f"🃏 <b>BLACKJACK JACKPOT KAZANDIN!</b> 🃏\n"
                                f"━━━━━━━━━━━━━━━━━━━━━\n"
                                f"🆔 GAME ID: {game_id}\n"
                                f"🃏 Oyun: Blackjack (21)\n"
                                f"💰 Havuz Payın: {format_amount(jackpot_per_winner)}\n"
                                f"🎁 Bahis İaden: {format_amount(bet)}\n"
                                f"💳 Toplam: {format_amount(total_win)}\n\n"
                                f"🎉 <b>TEBRİKLER!</b> 🎉"
                            )
                            
                            if jackpot_img:
                                await ctx.bot.send_photo(chat_id, photo=jackpot_img, caption=caption, parse_mode="HTML")
                            else:
                                await ctx.bot.send_message(chat_id, caption, parse_mode="HTML")
                    
                    await _reset_jackpot("blackjack")
                    logger.info(f"🃏 Blackjack JACKPOT dağıtıldı: {format_amount(jackpot_amount)}. Game: {game_id}")
            
    except Exception as e:
        logger.error(f"❌ process_jackpot_on_game_end kritik hata: {e}", exc_info=True)


# ═══════════════════════════════════════════════════════════════
#  /jackpot KOMUTU
# ═══════════════════════════════════════════════════════════════

async def cmd_jackpot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Tüm jackpot havuzlarını göster"""
    try:
        wheel_amount = await _get_jackpot_amount("wheel")
        blackjack_amount = await _get_jackpot_amount("blackjack")
        
        text = (
            f"🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥\n"
            f"      👑 <b>KRALLIK JACKPOT HAVUZLARI</b> 👑\n"
            f"🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥\n\n"
            f"✅ <b>🎡 ÇARKIFELEK KRALLIĞI</b> ✅\n"
            f"═══════════════════════════════════\n"
            f"🔘 <b>HAVUZ:</b> <code>{format_amount(wheel_amount)}</code> 🪙BTK 💵💵\n"
            f"🔘 <b>JACKPOT ŞANSI:</b> %5\n"
            f"🔘 PASS → HAVUZA EKLENİR\n\n"
            f"✅ <b>🃏 BLACKJACK KRALLIĞI</b> ✅\n"
            f"═══════════════════════════════════\n"
            f"🔘 <b>HAVUZ:</b> <code>{format_amount(blackjack_amount)}</code> 🪙BTK 💵💵\n"
            f"🔘 21 YAPANA → JACKPOT\n"
            f"🔘 BUST → HAVUZA EKLENİR\n\n"
            f"      👑💰 <b>TAHT SENİ BEKLİYOR!</b> 💰👑"
        )
        
        await update.message.reply_text(text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"❌ cmd_jackpot hatası: {e}")
        await update.message.reply_text("❌ Jackpot bilgileri alınırken hata oluştu.")

async def finish_game(chat_id: int, game_id: str, result: str = ""):
    """Oyunu bitir"""
    async with _state_lock:
        if game_id in _active_games.get(chat_id, {}):
            _active_games[chat_id][game_id]["state"] = "FINISHED"
    
    db = await get_db()
    await db.games.update_one(
        {"game_id": game_id},
        {"$set": {"state": "FINISHED", "result": result, "finished_at": datetime.now()}}
    )
    
    # 🎰 JACKPOT DİNLEYİCİ - SADECE BU SATIRI EKLE
    asyncio.create_task(process_jackpot_on_game_end(game_id, result, chat_id))

async def cleanup(chat_id: int):
    """Bitmiş oyunları temizle"""
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
    """Rate limit kontrolü"""
    now = time.monotonic()
    if now - _last_cmd.get(uid, 0) < RATE_LIMIT_SECONDS:
        return True
    _last_cmd[uid] = now
    return False
    
    
# ═══════════════════════════════════════════════════════════════
#  GENEL KOMUTLAR
# ═══════════════════════════════════════════════════════════════

def clean_name(name: str) -> str:
    """Sadece harf, rakam ve boşluk bırakır (Görselde hata vermemesi için)"""
    cleaned = re.sub(r'[^a-zA-Z0-9ğüşıöçĞÜŞİÖÇ\s]', '', name)
    return cleaned.strip()

def create_transfer_image(sender: str, receiver: str, amount: int) -> io.BytesIO:
    """Transfer görseli oluştur"""
    transfer_template = os.path.join(BASE_DIR, "transfer.png")
    
    if not os.path.exists(transfer_template):
        img = Image.new('RGB', (800, 600), color='#1a1a2e')
    else:
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
    
    # İsimler
    draw.text((width * 0.57, height * 0.19), sender, fill="#F5F5F5", font=font_isim, anchor="mm")
    draw.text((width * 0.57, height * 0.53), receiver, fill="#F5F5F5", font=font_isim, anchor="mm")
    
    # Miktar (sembolsüz)
    amount_text = format_amount(amount).replace(CURRENCY_SYMBOL, "").strip()
    
    # Gölgeli yazı
    draw.text((width * 0.47 + 3, height * 0.86 + 3), amount_text, fill=shadow_color, font=font_miktar, anchor="lm")
    draw.text((width * 0.47, height * 0.86), amount_text, fill=gold_color, font=font_miktar, anchor="lm")
    
    # Token yazısı
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


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Başlangıç komutu - Kullanıcıyı kaydeder"""
    user = update.effective_user
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
    """Bakiye sorgula - Oyun istatistikleri ve sıralama ile"""
    user = update.effective_user
    if is_rate_limited(user.id): 
        return
    
    u = await get_user(user.id)
    if not u:
        await update.message.reply_text("❌ Kullanıcı bulunamadı. /start yazın.")
        return
    
    # Kullanıcının sıralamasını bul
    db = await get_db()
    
    # Mevcut bakiyeyi int'e çevir
    current_balance = u.get("balance", 0)
    if isinstance(current_balance, Decimal128):
        current_balance = int(current_balance.to_decimal())
    elif isinstance(current_balance, Decimal):
        current_balance = int(current_balance)
    else:
        try:
            current_balance = int(current_balance) if current_balance else 0
        except:
            current_balance = 0
    
    # Sıralama için sorgula
    try:
        higher_count = await db.users.count_documents({
            "$or": [
                {"balance": {"$gt": Decimal128(str(current_balance))}},
                {"balance": {"$gt": current_balance}}
            ]
        })
    except:
        higher_count = await db.users.count_documents({})
    rank = higher_count + 1
    
    # Seviye
    lvl, emoji = get_level(current_balance)
    
    # Bakiye formatı
    balance = format_amount(u['balance'])
    
    # Oyun istatistiklerini al
    stats = await db.user_stats.find_one({"telegram_id": user.id})
    
    if not stats:
        rulet_win_rate = blackjack_win_rate = dice_win_rate = wheel_win_rate = scratch_win_rate = total_win_rate = 0
    else:
        rulet_win_rate = stats.get("roulette_win_rate", 0)
        blackjack_win_rate = stats.get("blackjack_win_rate", 0)
        dice_win_rate = stats.get("dice_win_rate", 0)
        wheel_win_rate = stats.get("wheel_win_rate", 0)
        scratch_win_rate = stats.get("scratch_win_rate", 0)
        total_win_rate = stats.get("total_win_rate", 0)
    
    # Mesajı oluştur
    message = (
        f"📌 <b>Verilerim</b>\n\n"
        f"👤 <b>{user.full_name}</b>\n\n"
        f"🤴 Seviye 🔘 {lvl} {emoji}\n\n"
        f"🏧 Bakiye 🔘 {balance}\n\n"
        f"🌍 Genel Sıralamanız 🔘 {rank}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Oyun İstatistikleri</b>\n"
        f"🎡 Rulet: %{rulet_win_rate}\n"
        f"🃏 Blackjack: %{blackjack_win_rate}\n"
        f"🎲 Zar: %{dice_win_rate}\n"
        f"🎡 Çarkıfelek: %{wheel_win_rate}\n"
        f"🎟 Kazı Kazan: %{scratch_win_rate}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 <b>Toplam Kazanma Oranı: %{total_win_rate}</b>"
    )
    
    await update.message.reply_text(message, parse_mode="HTML")

async def cmd_changename(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """İsim değiştir"""
    user = update.effective_user
    if is_rate_limited(user.id): 
        return
    
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
    
    try:
        sender_name = clean_name(user.full_name)
        receiver_name = clean_name(target.full_name)
        transfer_img = create_transfer_image(sender_name, receiver_name, amount)
        
        await update.message.reply_photo(
            photo=transfer_img,
            caption=f"✅ <b>Transfer Başarılı!</b>\n💰 {format_amount(amount)}\n💳 Yeni bakiyeniz: {format_amount(new_bal)}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Transfer görsel hatası: {e}")
        await update.message.reply_text(
            f"✅ <b>Transfer Başarılı!</b>\n"
            f"📤 {user.full_name} → 📥 {target.full_name}\n"
            f"💰 {format_amount(amount)}\n"
            f"💳 Yeni bakiyeniz: {format_amount(new_bal)}",
            parse_mode="HTML"
        )


async def cmd_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Liderlik tablosu - Grup adı ile"""
    if is_rate_limited(update.effective_user.id): 
        return
    
    rows = await get_leaderboard(LEADERBOARD_SIZE)
    
    # Grubun adını al
    chat = update.effective_chat
    if chat.type in ["group", "supergroup"]:
        group_name = chat.title
    else:
        group_name = "Casino Bot"
    
    # Başlık
    lines = [f"🏆 <b>{group_name}</b> En Zengin {LEADERBOARD_SIZE} Kullanıcı 🏆", ""]
    
    # Madalya emojileri
    medals = ["🥇", "🥈", "🥉"]
    
    for i, r in enumerate(rows):
        if i < 3:
            rank_emoji = medals[i]
        else:
            rank_emoji = f"{i+1}️⃣"
        
        name = r.get("display_name", "Bilinmeyen")[:20]
        balance = format_amount(r['balance'])
        lvl, emoji = get_level(r['balance'])
        
        lines.append(f"{rank_emoji} <b>{name}</b> ❇️  {balance} {emoji}{lvl}")
    
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
#  ADMIN KOMUTLARI
# ═══════════════════════════════════════════════════════════════

async def cmd_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """ID öğrenme komutu (herkes kullanabilir)"""
    user = update.effective_user
    chat = update.effective_chat
    
    message = f"🆔 <b>Kullanıcı ID:</b> <code>{user.id}</code>\n"
    message += f"👤 İsim: {user.full_name}\n"
    
    if chat.type in ["group", "supergroup"]:
        message += f"\n💬 <b>Grup ID:</b> <code>{chat.id}</code>\n"
        message += f"📌 Grup Adı: {chat.title}"
    
    await update.message.reply_text(message, parse_mode="HTML")


async def cmd_addbalance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin komutu - Kullanıcıya bakiye ekle"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Bu komutu kullanma yetkiniz yok!")
        return
    
    args = ctx.args
    target_id = None
    amount_str = None
    
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        amount_str = args[0] if args else None
    elif len(args) == 1:
        target_id = user.id
        amount_str = args[0]
    elif len(args) >= 2:
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
    
    if not amount_str:
        await update.message.reply_text("❌ Miktar belirtilmedi!")
        return
    
    try:
        amount, err = parse_amount(amount_str, 10**18)
        if err:
            await update.message.reply_text(f"❌ {err}")
            return
    except:
        await update.message.reply_text("❌ Geçersiz miktar!")
        return
    
    db = await get_db()
    target_user = await db.users.find_one({"telegram_id": target_id})
    if not target_user:
        await update.message.reply_text("❌ Kullanıcı bulunamadı!")
        return
    
    await add_balance(target_id, amount, "admin", f"Admin tarafından verildi")
    
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
    """Admin komutu - Kullanıcının bakiyesini ayarla"""
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
    
    db = await get_db()
    await db.games.update_many(
        {"state": {"$in": ["OPEN", "PLAYING", "CALCULATING", "BETTING", "DEALING", "ROLLING"]}},
        {"$set": {"state": "FINISHED", "finished_at": datetime.now()}}
    )
    
    await update.message.reply_text(
        "✅ <b>OYUNLAR TEMİZLENDİ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🧹 Tüm takılı kalmış oyunlar sonlandırıldı.\n"
        f"🎮 Artık yeni oyun başlatabilirsiniz.",
        parse_mode="HTML"
    )


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin komutu - Bot istatistikleri"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Bu komutu kullanma yetkiniz yok!")
        return
    
    db = await get_db()
    
    total_users = await db.users.count_documents({})
    total_games = await db.games.count_documents({})
    total_transactions = await db.transactions.count_documents({})
    
    pipeline = [{"$group": {"_id": None, "total": {"$sum": "$balance"}}}]
    result = await db.users.aggregate(pipeline).to_list(length=1)
    total_balance = result[0]["total"] if result else 0
    
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
        f"💰 Toplam Bakiye: <b>{format_amount(total_balance)}</b>\n"
        f"🔄 Aktif Oyun: <b>{active_games_count}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        parse_mode="HTML"
        )



async def cmd_testjackpot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Jackpot görselini test et (Sadece Admin)"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Bu komutu kullanma yetkiniz yok!")
        return
    
    test_name = user.full_name if user.full_name else "Test Oyuncu"
    
    for game_type in ["wheel", "blackjack"]:
        img = create_jackpot_image(game_type, test_name)
        
        if img:
            caption = f"🧪 <b>TEST GÖRSELİ</b>\n🎮 Oyun: {game_type}\n👤 İsim: {test_name}\n\n✅ Görsel başarıyla oluşturuldu."
            await update.message.reply_photo(photo=img, caption=caption, parse_mode="HTML")
        else:
            await update.message.reply_text(f"❌ {game_type} görseli oluşturulamadı.")


# ═══════════════════════════════════════════════════════════════
#  RULET
# ═══════════════════════════════════════════════════════════════

def format_number_with_emoji(number: int) -> str:
    """Sayıyı emoji rakamlarla göster"""
    emoji_digits = {
        '0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
        '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'
    }
    return ''.join(emoji_digits[d] for d in str(number))

def get_rank_emoji(rank: int) -> str:
    """Sıralama için madalya emojisi"""
    if rank == 1:
        return "🥇"
    elif rank == 2:
        return "🥈"
    elif rank == 3:
        return "🥉"
    else:
        return "📍"

def get_roulette_image(number: int) -> str:
    """Kazanan sayının görselini bul"""
    if number == 0:
        img_path = os.path.join(BASE_DIR, "0.jpg")
    else:
        img_path = os.path.join(BASE_DIR, f"{number}.jpg")
    
    if not os.path.exists(img_path):
        spin_path = os.path.join(BASE_DIR, "spin.jpg")
        if os.path.exists(spin_path):
            img_path = spin_path
    return img_path


async def cmd_rulet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Rulet oyunu başlat"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    if is_rate_limited(user.id): 
        return
    
    ok, err = await can_open_game(chat_id, "roulette")
    if not ok:
        await update.message.reply_text(f"❌ {err}")
        return
    
    # Önce oyunu oluştur ki game_id alalım
    game = await create_game(chat_id, "roulette", 0)
    game_id = game["game_id"]
    
    spin_img_path = os.path.join(ROULETTE_IMG_PATH, "spin.jpg")
    caption = (
        f"🎰 <b>AVRUPA RULETİ BAŞLADI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 GAME ID: {game_id}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>{BET_WINDOW} saniye</b> içinde bahis yapın!\n\n"
        f"🔴 /red &lt;miktar&gt;\n"
        f"⚫ /black &lt;miktar&gt;\n"
        f"🟢 /green &lt;miktar&gt;\n"
        f"🔢 /number &lt;sayı 0-36&gt; &lt;miktar&gt;\n"
        f"🔢 /numbers &lt;1,2,3,...&gt; &lt;miktar&gt;"
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
        if chat_id in _active_games and game_id in _active_games[chat_id]:
            _active_games[chat_id][game_id]["message_id"] = msg.message_id
    
    asyncio.create_task(_roulette_timer(ctx, chat_id, game_id, msg))


async def _roulette_timer(ctx, chat_id, game_id, msg):
    """Rulet süre dolunca sonuçları hesapla"""
    await asyncio.sleep(BET_WINDOW)
    
    game = await get_active_game(chat_id, "roulette")
    if not game or game["game_id"] != game_id: 
        return
    
    game["state"] = "CALCULATING"
    
    # Kazanan sayıyı belirle
    winning = random.randint(0, 36)
    color = ROUL_COLORS[winning]
    color_emoji = ROUL_EMOJI[color]
    
    # Eski mesajı silmeyi dene
    try:
        await ctx.bot.delete_message(chat_id, msg.message_id)
    except:
        pass
    
    # Katılımcıları al
    parts = await get_participants(chat_id, game_id)
    winners = []
    
    for uid, data in parts.items():
        user_total_won = 0
        user_total_bet = 0
        
        for bet_wrapper in data.get("bets", []):
            bet = bet_wrapper["bet"]
            bd = bet_wrapper["bet_data"]
            user_total_bet += bet
            won = False
            payout = 0
            
            if bd.get("type") == "color":
                if bd.get("color") == color:
                    multiplier = ROULETTE_MULTIPLIERS[color]
                    payout = bet * multiplier
                    won = True
                    
            elif bd.get("type") == "number":
                if winning in bd.get("numbers", []):
                    per_number_bet = bet // len(bd["numbers"])
                    multiplier = ROULETTE_MULTIPLIERS["number"]
                    payout = per_number_bet * multiplier
                    won = True
            
            if won:
                await add_balance(uid, payout, "win", f"Rulet game:{game_id}")
                await update_stats(uid, payout)
                user_total_won += payout
            
            await update_win_rate(uid, "roulette", won)
        
        if user_total_won > 0:
            winners.append({
                "uid": uid,
                "name": bd.get("name", "Bilinmeyen"),
                "payout": user_total_won,
                "bet": user_total_bet
            })
        else:
            await update_stats(uid, 0)
            await update_win_rate(uid, "roulette", False)
    
    # Sonuç mesajını oluştur - YENİ FORMAT
    result_text = f"🆔 GAME ID: {game_id}\n\n"
    result_text += f"🏆 Kazanan Sayı 🔘 {format_number_with_emoji(winning)} {color_emoji}!\n\n"
    result_text += f"🏧 Kazanan Kişiler 🔘\n"
    
    if winners:
        # Toplam kazanca göre sırala
        winners.sort(key=lambda x: x["payout"], reverse=True)
        
        for i, w in enumerate(winners[:15], 1):
            rank_emoji = get_rank_emoji(i)
            result_text += f" {rank_emoji} {w['name']} {color_emoji} {format_amount(w['payout'])}\n"
    else:
        result_text += " 💀 Kazanan olmadı!\n"
    
    # Kazanan sayı görselini gönder
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
    """Rulet bahis işleme (ortak fonksiyon)"""
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
    
    # Bahsi düş
    ok = await remove_balance(user.id, amount, "bet", f"Rulet game:{game['game_id']}")
    if not ok:
        await update.message.reply_text("❌ Yetersiz bakiye.")
        return
    
    # Bahis verisini hazırla
    if bet_type == "color":
        bd = {"type": "color", "color": color, "name": user.full_name}
        color_emoji = {"red": "🔴", "black": "⚫", "green": "🟢"}.get(color, "🔵")
        bet_desc = f"{color_emoji} {color.upper()}"
    else:
        bd = {"type": "number", "numbers": numbers or [], "name": user.full_name}
        if len(numbers) == 1:
            bet_desc = f"🔢 Sayı {numbers[0]}"
        else:
            bet_desc = f"🔢 Sayılar {','.join(map(str, numbers))}"
        color_emoji = "🔵"
    
    # Bahsi ekle
    await add_participant(chat_id, game["game_id"], user.id, amount, bd)
    
    # Oyuncunun bu oyundaki toplam bahsini hesapla
    parts = await get_participants(chat_id, game["game_id"])
    user_bets = parts.get(user.id, {}).get("bets", [])
    total_bet = sum(b["bet"] for b in user_bets)
    
    # Bu spesifik bahis türü için toplamı bul
    specific_total = 0
    for b in user_bets:
        bd_check = b["bet_data"]
        if bet_type == "color" and bd_check.get("type") == "color":
            if bd_check.get("color") == color:
                specific_total = b["bet"]
                break
        elif bet_type == "number" and bd_check.get("type") == "number":
            if set(bd_check.get("numbers", [])) == set(numbers or []):
                specific_total = b["bet"]
                break
    
    await update.message.reply_text(
        f"🕹 <b>{user.full_name}</b>\n"
        f"📌 {bet_desc}: {format_amount(specific_total)}\n"
        f"💰 Bu oyunda toplam bahsiniz: {format_amount(total_bet)}",
        parse_mode="HTML"
    )


async def cmd_green(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Yeşile bahis"""
    if not ctx.args:
        await update.message.reply_text("❌ Kullanım: /green <miktar>")
        return
    await _rulet_bet(update, "color", color="green", amount_str=ctx.args[0])


async def cmd_red(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Kırmızıya bahis"""
    if not ctx.args:
        await update.message.reply_text("❌ Kullanım: /red <miktar>")
        return
    await _rulet_bet(update, "color", color="red", amount_str=ctx.args[0])


async def cmd_black(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Siyaha bahis"""
    if not ctx.args:
        await update.message.reply_text("❌ Kullanım: /black <miktar>")
        return
    await _rulet_bet(update, "color", color="black", amount_str=ctx.args[0])


async def cmd_number(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Tek sayıya bahis"""
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
    """Çoklu sayıya bahis"""
    if len(ctx.args) < 2:
        await update.message.reply_text("❌ Kullanım: /numbers <1,2,3> <miktar>")
        return
    try:
        nums = [int(x.strip()) for x in ctx.args[0].split(",")]
        if not all(0 <= n <= 36 for n in nums):
            await update.message.reply_text("❌ Sayılar 0-36 arasında olmalı.")
            return
        if len(nums) < 1:
            await update.message.reply_text("❌ En az 1 sayı belirtmelisiniz.")
            return
        await _rulet_bet(update, "number", numbers=nums, amount_str=ctx.args[1])
    except:
        await update.message.reply_text("❌ Geçersiz sayı listesi.")
        
        
        
        
# ═══════════════════════════════════════════════════════════════
#  BLACKJACK
# ═══════════════════════════════════════════════════════════════

_bj: Dict[int, dict] = {}

def get_card_image(card: tuple) -> Image.Image:
    """Kart görselini yükle"""
    rank, suit = card
    rank_map = {"A": "ace", "2": "2", "3": "3", "4": "4", "5": "5", "6": "6", 
                "7": "7", "8": "8", "9": "9", "10": "10", "J": "jack", "Q": "queen", "K": "king"}
    suit_map = {"♠️": "spades", "♥️": "hearts", "♦️": "diamonds", "♣️": "clubs"}
    filename = f"{rank_map.get(rank, rank)}_of_{suit_map.get(suit, 'spades')}.png"
    img_path = os.path.join(BASE_DIR, filename)
    
    if os.path.exists(img_path):
        img = Image.open(img_path)
        img = img.resize((CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS)
        return img
    return Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), color='#2c2c2c')

def get_face_down_card() -> Image.Image:
    """Kapalı kart görseli"""
    back_path = os.path.join(BLACKJACK_IMG_PATH, "back.png")
    if os.path.exists(back_path):
        img = Image.open(back_path)
        img = img.resize((CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS)
        return img
    return Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), color='#2c2c2c')

def combine_cards(cards: list) -> io.BytesIO:
    """Kartları yan yana birleştir"""
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
    """İlk kart kapalı, diğerleri açık birleştir"""
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
    """Yeni deste oluştur ve karıştır"""
    deck = [(r, s) for r in RANKS for s in SUITS]
    random.shuffle(deck)
    return deck

def _card_val(rank: str) -> int:
    """Kartın değerini hesapla"""
    if rank in ("J", "Q", "K"):
        return 10
    if rank == "A":
        return 11
    return int(rank)

def _hand_val(hand: List[Tuple[str, str]]) -> int:
    """Eldeki kartların toplam değerini hesapla (As 1 veya 11)"""
    total = sum(_card_val(r) for r, s in hand)
    aces = sum(1 for r, s in hand if r == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

def _bj_kb(game_id: str):
    """Blackjack butonları"""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🃏 Hit", callback_data=f"bj_hit:{game_id}"),
        InlineKeyboardButton("✋ Stand", callback_data=f"bj_stand:{game_id}"),
    ]])


async def cmd_blackjack(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Blackjack oyunu başlat"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    if is_rate_limited(user.id): 
        return
    
    ok, err = await can_open_game(chat_id, "blackjack")
    if not ok:
        await update.message.reply_text(f"❌ {err}")
        return
    
    # Önce oyunu oluştur
    game = await create_game(chat_id, "blackjack", 0)
    gid = game["game_id"]
    
    msg = await update.message.reply_text(
        f"🃏 <b>BLACKJACK BAŞLADI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 GAME ID: {gid}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>{BET_WINDOW} saniye</b> içinde bahis yapın!\n\n"
        f"📌 /bj &lt;miktar&gt;\n"
        f"• 21'i geç → kaybedersin\n"
        f"• Kurpiyer 17'de durur\n"
        f"• Kazanırsan 2x alırsın",
        parse_mode="HTML"
    )
    
    # Mesaj ID'sini güncelle
    async with _state_lock:
        if chat_id in _active_games and gid in _active_games[chat_id]:
            _active_games[chat_id][gid]["message_id"] = msg.message_id
    
    _bj[chat_id] = {
        "game_id": gid, 
        "state": "BETTING", 
        "players": {}, 
        "order": [], 
        "dealer": [], 
        "deck": [], 
        "current": 0
    }
    asyncio.create_task(_bj_bet_timer(ctx, chat_id, gid))


async def cmd_bj(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Blackjack bahis yap"""
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
        await update.message.reply_text(
            f"🕹 <b>{user.full_name}</b> 🃏 +{format_amount(amount)} "
            f"(Toplam: {format_amount(bj['players'][user.id]['bet'])})",
            parse_mode="HTML"
        )
    else:
        bj["players"][user.id] = {
            "bet": amount, 
            "hand": [], 
            "state": "WAITING", 
            "name": user.full_name
        }
        bj["order"].append(user.id)
        await update.message.reply_text(
            f"🕹 <b>{user.full_name}</b> 🃏 {format_amount(amount)} bahis yaptı",
            parse_mode="HTML"
        )


async def _bj_bet_timer(ctx, chat_id, game_id):
    """Bahis süresi dolunca kartları dağıt"""
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
    
    # Oyunculara 2'şer kart dağıt
    for uid in bj["order"]:
        bj["players"][uid]["hand"] = [deck.pop(), deck.pop()]
        bj["players"][uid]["state"] = "PLAYING"
        bj["players"][uid]["cards_sent"] = False
    
    # Kurpiyere 2 kart
    bj["dealer"] = [deck.pop(), deck.pop()]
    bj["current"] = 0
    
    # Kurpiyerin kartlarını göster (biri kapalı)
    dealer_img = combine_cards_with_hidden(bj["dealer"])
    first_card_val = _card_val(bj["dealer"][0][0])
    await ctx.bot.send_photo(
        chat_id, 
        photo=dealer_img, 
        caption=f"🎩 <b>KURPİYER</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
                f"Açık kart: {first_card_val}\nKapalı kart: ?",
        parse_mode="HTML"
    )
    
    # Oyuncuların kartlarını göster
    for uid in bj["order"]:
        p = bj["players"][uid]
        hand_img = combine_cards(p["hand"])
        await ctx.bot.send_photo(
            chat_id, 
            photo=hand_img, 
            caption=f"🃏 <b>{p['name']}</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🃏 Eliniz: {_hand_val(p['hand'])}",
            parse_mode="HTML"
        )
        p["cards_sent"] = True
    
    await _bj_next(ctx, chat_id, game_id)


async def _bj_next(ctx, chat_id, game_id):
    """Sıradaki oyuncuya geç"""
    bj = _bj.get(chat_id)
    if not bj or bj["game_id"] != game_id:
        return
    
    # Tüm oyuncular oynadıysa kurpiyere geç
    if bj["current"] >= len(bj["order"]):
        await _bj_dealer(ctx, chat_id, game_id)
        return
    
    uid = bj["order"][bj["current"]]
    p = bj["players"][uid]
    
    # Oyuncu zaten BUST veya STAND ise sonrakine geç
    if p["state"] != "PLAYING":
        bj["current"] += 1
        await _bj_next(ctx, chat_id, game_id)
        return
    
    val = _hand_val(p["hand"])
    
    # İlk turda kartlar zaten gösterildi, sadece mesaj gönder
    await ctx.bot.send_message(
        chat_id,
        f"🃏 <b>SIRA SENDE</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {p['name']}\n🃏 Eliniz: {val}\n⏳ {BLACKJACK_TURN} saniyen var!",
        reply_markup=_bj_kb(game_id),
        parse_mode="HTML"
    )
    
    # Timeout timer'ı başlat
    p["task"] = asyncio.create_task(_bj_timeout(ctx, chat_id, game_id, uid))


async def _bj_timeout(ctx, chat_id, game_id, uid):
    """Süre dolunca otomatik STAND"""
    await asyncio.sleep(BLACKJACK_TURN)
    bj = _bj.get(chat_id)
    if not bj or bj["game_id"] != game_id:
        return
    p = bj["players"].get(uid)
    if not p or p["state"] != "PLAYING":
        return
    p["state"] = "STAND"
    bj["current"] += 1
    await ctx.bot.send_message(
        chat_id, 
        f"⏰ <b>{p['name']}</b> süre doldu, otomatik STAND!",
        parse_mode="HTML"
    )
    await _bj_next(ctx, chat_id, game_id)


async def bj_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Blackjack buton callback'leri"""
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
    
    # Timeout timer'ını iptal et
    if p.get("task"):
        p["task"].cancel()
    
    if action == "bj_hit":
        # Yeni kart çek
        card = bj["deck"].pop()
        p["hand"].append(card)
        val = _hand_val(p["hand"])
        hand_img = combine_cards(p["hand"])
        
        if val > 21:
            # BUST
            await query.edit_message_media(
                media=InputMediaPhoto(
                    media=hand_img,
                    caption=f"💥 <b>BUST!</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
                            f"👤 {p['name']}\n🃏 Eliniz: {val}\n❌ Kaybettiniz!",
                    parse_mode="HTML"
                )
            )
            p["state"] = "BUST"
            bj["current"] += 1
            await _bj_next(ctx, chat_id, game_id)
            
        elif val == 21:
            # BLACKJACK - Otomatik STAND
            await query.edit_message_media(
                media=InputMediaPhoto(
                    media=hand_img,
                    caption=f"🎉 <b>BLACKJACK! 21</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
                            f"👤 {p['name']}\n✅ Otomatik Stand",
                    parse_mode="HTML"
                )
            )
            p["state"] = "STAND"
            bj["current"] += 1
            await _bj_next(ctx, chat_id, game_id)
            
        else:
            # Devam
            await query.edit_message_media(
                media=InputMediaPhoto(
                    media=hand_img,
                    caption=f"🃏 <b>SIRA SENDE</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
                            f"👤 {p['name']}\n🃏 Eliniz: {val}\n⏳ {BLACKJACK_TURN} saniyen var!",
                    parse_mode="HTML"
                ),
                reply_markup=_bj_kb(game_id)
            )
            p["task"] = asyncio.create_task(_bj_timeout(ctx, chat_id, game_id, user.id))
    
    elif action == "bj_stand":
        hand_val = _hand_val(p["hand"])
        p["state"] = "STAND"
        bj["current"] += 1
        
        hand_img = combine_cards(p["hand"])
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=hand_img,
                caption=f"✋ <b>STAND</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 {p['name']}\n🃏 Eliniz: {hand_val} ile durdu.",
                parse_mode="HTML"
            )
        )
        await _bj_next(ctx, chat_id, game_id)


async def _bj_dealer(ctx, chat_id, game_id):
    """Kurpiyerin sırası ve final sonuçları"""
    bj = _bj.get(chat_id)
    if not bj or bj["game_id"] != game_id:
        return
    
    # Kurpiyer 17'ye kadar kart çeker
    hand = bj["dealer"]
    while _hand_val(hand) < 17:
        hand.append(bj["deck"].pop())
    
    dval = _hand_val(hand)
    dealer_img = combine_cards(hand)
    
    await ctx.bot.send_photo(
        chat_id, 
        photo=dealer_img, 
        caption=f"🎩 <b>KURPİYER</b>\n━━━━━━━━━━━━━━━━━━━━━\n📊 Toplam: {dval}",
        parse_mode="HTML"
    )
    
    # Final tablosu
    results = [
        f"🏁 <b>BLACKJACK - FİNAL TABLOSU</b>",
        f"━━━━━━━━━━━━━━━━━━━━━"
    ]
    total_payout = 0
    
    # 🎰 JACKPOT RESULT STRING'İ
    jackpot_result = f"dealer:{dval}"
    
    for uid in bj["order"]:
        p = bj["players"][uid]
        pval = _hand_val(p["hand"])
        bet = p["bet"]
        
        # ═══════════════════════════════════════════════════════
        # 🎰 JACKPOT İŞLEMLERİ (ÖNCE HAVUZA EKLEME)
        # ═══════════════════════════════════════════════════════
        if p["state"] == "BUST":
            # BUST: Bahsin %100'ü havuza
            await _add_to_jackpot("blackjack", bet)
            jackpot_result += "|BUST"
            
        elif pval < dval and dval <= 21:
            # Kaybetme: Bahsin %25'i havuza
            commission = int(bet * 0.25)
            if commission > 0:
                await _add_to_jackpot("blackjack", commission)
            jackpot_result += "|LOSE"
            
        elif pval == dval:
            # Beraberlik: Bahsin %10'u havuza
            commission = int(bet * 0.10)
            if commission > 0:
                await _add_to_jackpot("blackjack", commission)
            jackpot_result += "|PUSH"
            
        elif pval == 21:
            # 21 yapan - JACKPOT DAĞIT
            jackpot_amount = await _get_jackpot_amount("blackjack")
            if jackpot_amount > JACKPOT_MINIMUM:
                total_win = bet + jackpot_amount
                await add_balance(uid, total_win, "win", f"Blackjack JACKPOT! game:{game_id}")
                await update_stats(uid, total_win)
                await update_win_rate(uid, "blackjack", True)
                
                # Görsel gönder
                user = await get_user(uid)
                player_name = user.get("display_name", str(uid)) if user else str(uid)
                jackpot_img = create_jackpot_image("blackjack", player_name)
                caption = (
                    f"🃏 <b>BLACKJACK JACKPOT KAZANDIN!</b> 🃏\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🆔 GAME ID: {game_id}\n"
                    f"🃏 Oyun: Blackjack (21)\n"
                    f"💰 Havuz Payın: {format_amount(jackpot_amount)}\n"
                    f"🎁 Bahis İaden: {format_amount(bet)}\n"
                    f"💳 Toplam: {format_amount(total_win)}\n\n"
                    f"🎉 <b>TEBRİKLER!</b> 🎉"
                )
                
                try:
                    if jackpot_img:
                        await ctx.bot.send_photo(chat_id, photo=jackpot_img, caption=caption, parse_mode="HTML")
                    else:
                        await ctx.bot.send_message(chat_id, caption, parse_mode="HTML")
                except Exception as e:
                    logger.error(f"Jackpot görseli gönderilemedi: {e}")
                    await ctx.bot.send_message(chat_id, caption, parse_mode="HTML")
                
                await _reset_jackpot("blackjack")
                logger.info(f"🃏 Blackjack JACKPOT dağıtıldı: {format_amount(jackpot_amount)}. Kazanan: {player_name}")
            
            jackpot_result += "|BLACKJACK"
        
        # ═══════════════════════════════════════════════════════
        # NORMAL KAZANÇ/KAYIP İŞLEMLERİ (MEVCUT KOD)
        # ═══════════════════════════════════════════════════════
        if p["state"] == "BUST":
            results.append(f"❌ {p['name']}: {pval} (BUST) → -{format_amount(bet)}")
            await update_win_rate(uid, "blackjack", False)
            
        elif dval > 21:
            payout = bet * 2
            await add_balance(uid, payout, "win", f"BJ game:{game_id}")
            await update_stats(uid, payout)
            total_payout += payout
            results.append(f"✅ {p['name']}: {pval} vs {dval} (BUST) → +{format_amount(payout)}")
            await update_win_rate(uid, "blackjack", True)
            
        elif pval > dval:
            payout = bet * 2
            await add_balance(uid, payout, "win", f"BJ game:{game_id}")
            await update_stats(uid, payout)
            total_payout += payout
            results.append(f"✅ {p['name']}: {pval} vs {dval} → +{format_amount(payout)}")
            await update_win_rate(uid, "blackjack", True)
            
        elif pval == dval:
            await add_balance(uid, bet, "refund", f"BJ game:{game_id}")
            results.append(f"🤝 {p['name']}: {pval} vs {dval} → İADE")
            
        else:
            results.append(f"❌ {p['name']}: {pval} vs {dval} → -{format_amount(bet)}")
            await update_win_rate(uid, "blackjack", False)
    
    results.append("━━━━━━━━━━━━━━━━━━━━━")
    results.append(f"🏧 DAĞITILAN TOPLAM: {format_amount(total_payout)}")
    results.append("✨ Yeni oyun için /blackjack yazın!")
    
    await ctx.bot.send_message(chat_id, "\n".join(results), parse_mode="HTML")
    
    # Oyunu temizle
    del _bj[chat_id]
    await finish_game(chat_id, game_id, jackpot_result)
    await cleanup(chat_id) 
    
    
    
# ═══════════════════════════════════════════════════════════════
#  ZAR OYUNU GÖRSEL FONKSİYONLARI
# ═══════════════════════════════════════════════════════════════

def create_dice_image(number: int) -> io.BytesIO:
    """Klasik noktalı zar - Kahverengi zemin, parlak siyah noktalar"""
    size = 80
    
    img = Image.new('RGB', (size, size), color='#5C2E0B')
    draw = ImageDraw.Draw(img)
    
    # Altın çerçeve
    draw.rounded_rectangle([3, 3, size-4, size-4], radius=10, outline='#FFD700', width=3)
    draw.rounded_rectangle([7, 7, size-8, size-8], radius=7, outline='#DAA520', width=1)
    
    # Nokta pozisyonları
    margin = size // 5
    center = size // 2
    
    dot_positions = {
        1: [(center, center)],
        2: [(margin, margin), (size-margin, size-margin)],
        3: [(margin, margin), (center, center), (size-margin, size-margin)],
        4: [(margin, margin), (size-margin, margin), 
            (margin, size-margin), (size-margin, size-margin)],
        5: [(margin, margin), (size-margin, margin), (center, center),
            (margin, size-margin), (size-margin, size-margin)],
        6: [(margin, margin), (size-margin, margin),
            (margin, center), (size-margin, center),
            (margin, size-margin), (size-margin, size-margin)]
    }
    
    dot_radius = size // 11
    
    for x, y in dot_positions.get(number, []):
        # Gölge
        draw.ellipse([x-dot_radius+1, y-dot_radius+1, x+dot_radius+1, y+dot_radius+1], 
                     fill='#000000')
        # Parlak siyah nokta
        draw.ellipse([x-dot_radius, y-dot_radius, x+dot_radius, y+dot_radius], 
                     fill='#1a1a1a')
        # Işık vurgusu
        highlight_radius = dot_radius // 2
        draw.ellipse([x-highlight_radius, y-highlight_radius, x, y], 
                     fill='#555555')
    
    bio = io.BytesIO()
    img.save(bio, format='PNG', quality=95)
    bio.seek(0)
    return bio


def create_total_card(total: int) -> io.BytesIO:
    """Toplam kartı - Yeşil zemin, altın sayı"""
    size = 80
    
    img = Image.new('RGB', (size, size), color='#1B5E20')
    draw = ImageDraw.Draw(img)
    
    draw.rounded_rectangle([3, 3, size-4, size-4], radius=10, outline='#FFD700', width=3)
    draw.rounded_rectangle([7, 7, size-8, size-8], radius=7, outline='#DAA520', width=1)
    
    try:
        font = get_font(42)
        bbox = draw.textbbox((0, 0), str(total), font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        
        draw.text((size//2 - tw//2 + 2, size//2 - th//2 + 2), 
                  str(total), fill='#0D3B0F', font=font)
        draw.text((size//2 - tw//2, size//2 - th//2), 
                  str(total), fill='#FFD700', font=font)
    except:
        draw.text((size//2, size//2), str(total), fill='#FFD700', anchor="mm")
    
    bio = io.BytesIO()
    img.save(bio, format='PNG', quality=95)
    bio.seek(0)
    return bio


def combine_dice_with_total(dice1: int, dice2: int) -> io.BytesIO:
    """Zar1 + Zar2 + Toplam = 3 kart yan yana"""
    size = 80
    spacing = 8
    
    total_width = size * 3 + spacing * 2
    total_height = size
    
    combined = Image.new('RGB', (total_width, total_height), color='#1a1a2e')
    
    img1 = Image.open(create_dice_image(dice1))
    img2 = Image.open(create_dice_image(dice2))
    img_total = Image.open(create_total_card(dice1 + dice2))
    
    combined.paste(img1, (0, 0))
    combined.paste(img2, (size + spacing, 0))
    combined.paste(img_total, (size * 2 + spacing * 2, 0))
    
    bio = io.BytesIO()
    combined.save(bio, format='PNG', quality=95)
    bio.seek(0)
    return bio


def _dice_kb(game_id: str, roll_num: int):
    """Zar atma butonu"""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"🎲 {roll_num}. Zarı At", callback_data=f"dice_roll:{game_id}")
    ]])


# ═══════════════════════════════════════════════════════════════
#  ZAR OYUNU KOMUTLARI
# ═══════════════════════════════════════════════════════════════

async def cmd_dicebet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Zar oyunu başlat"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    if is_rate_limited(user.id): 
        return
    
    ok, err = await can_open_game(chat_id, "dice")
    if not ok:
        await update.message.reply_text(f"❌ {err}")
        return
    
    game = await create_game(chat_id, "dice", 0)
    gid = game["game_id"]
    
    msg = await update.message.reply_text(
        f"🎲 <b>ZAR OYUNU BAŞLADI! (PvP)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 GAME ID: {gid}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>{BET_WINDOW} saniye</b> içinde katılın!\n\n"
        f"📌 /dice &lt;miktar&gt; veya /dice allin\n"
        f"🎯 En yüksek zar toplamı kazanır!\n"
        f"🤝 Beraberlikte havuz bölüşülür.",
        parse_mode="HTML"
    )
    
    async with _state_lock:
        if chat_id in _active_games and gid in _active_games[chat_id]:
            _active_games[chat_id][gid]["message_id"] = msg.message_id
            _active_games[chat_id][gid]["min_bet"] = 0
            _active_games[chat_id][gid]["pool"] = 0
            _active_games[chat_id][gid]["players_data"] = {}
            _active_games[chat_id][gid]["dice_state"] = {
                "current_player": None,
                "roll_count": 0,
                "dice1": None,
                "dice2": None,
                "current_msg_id": None
            }
    
    asyncio.create_task(_dice_bet_timer(ctx, chat_id, gid))


async def cmd_dice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Zar oyununa katıl"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    if is_rate_limited(user.id): 
        return
    
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
        await update.message.reply_text("❌ Açık zar oyunu yok veya süre doldu.")
        return
    
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game["game_id"])
        if not game_data:
            await update.message.reply_text("❌ Oyun bulunamadı.")
            return
        
        players = game_data.get("players_data", {})
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
    
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game["game_id"])
        if game_data:
            if user.id in game_data["players_data"]:
                game_data["players_data"][user.id]["bet"] += amount
                total_bet = game_data["players_data"][user.id]["bet"]
                await update.message.reply_text(
                    f"🕹 <b>{user.full_name}</b> 🎲 +{format_amount(amount)} "
                    f"(Toplam: {format_amount(total_bet)})",
                    parse_mode="HTML"
                )
            else:
                game_data["players_data"][user.id] = {"bet": amount, "name": user.full_name}
                await update.message.reply_text(
                    f"🕹 <b>{user.full_name}</b> 🎲 {format_amount(amount)} katıldı!",
                    parse_mode="HTML"
                )
            game_data["pool"] = game_data.get("pool", 0) + amount


async def _dice_bet_timer(ctx, chat_id, game_id):
    """Bahis süresi dolunca oyunu başlat"""
    await asyncio.sleep(BET_WINDOW)
    
    game = await get_active_game(chat_id, "dice")
    if not game or game["game_id"] != game_id:
        return
    
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data:
            return
        players = game_data.get("players_data", {}).copy()
        pool = game_data.get("pool", 0)
    
    if len(players) < 2:
        for uid, data in players.items():
            await add_balance(uid, data["bet"], "refund", f"Zar iade game:{game_id}")
        await ctx.bot.send_message(
            chat_id,
            f"❌ <b>Zar oyunu iptal!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"En az 2 oyuncu gerekli. Bahisler iade edildi.",
            parse_mode="HTML"
        )
        await finish_game(chat_id, game_id, "iptal")
        await cleanup(chat_id)
        return
    
    game["state"] = "ROLLING"
    
    async with _state_lock:
        if chat_id in _active_games and game_id in _active_games[chat_id]:
            _active_games[chat_id][game_id]["order"] = list(players.keys())
            _active_games[chat_id][game_id]["players_rolled"] = {}
            _active_games[chat_id][game_id]["pool"] = pool
            _active_games[chat_id][game_id]["dice_state"]["current_index"] = 0
    
    await ctx.bot.send_message(
        chat_id,
        f"🎲 <b>BAHİS SÜRESİ DOLDU!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Oyuncu sayısı: {len(players)}\n"
        f"💰 Havuz: {format_amount(pool)}\n\n"
        f"🎯 Sırayla zar atılacak...",
        parse_mode="HTML"
    )
    
    await _dice_start_next_player(ctx, chat_id, game_id)


async def _dice_start_next_player(ctx, chat_id, game_id):
    """Sıradaki oyuncu için zar atma ekranını hazırla"""
    game = await get_active_game(chat_id, "dice")
    if not game or game["game_id"] != game_id:
        return
    
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data:
            return
        
        idx = game_data["dice_state"]["current_index"]
        order = game_data["order"]
        players_data = game_data["players_data"]
    
    if idx >= len(order):
        await _dice_calculate_results(ctx, chat_id, game_id)
        return
    
    uid = order[idx]
    player_name = players_data[uid]["name"]
    player_bet = players_data[uid]["bet"]
    
    # State'i sıfırla
    async with _state_lock:
        if chat_id in _active_games and game_id in _active_games[chat_id]:
            _active_games[chat_id][game_id]["dice_state"]["current_player"] = uid
            _active_games[chat_id][game_id]["dice_state"]["roll_count"] = 0
            _active_games[chat_id][game_id]["dice_state"]["dice1"] = None
            _active_games[chat_id][game_id]["dice_state"]["dice2"] = None
            _active_games[chat_id][game_id]["dice_state"]["task"] = None
    
    msg = await ctx.bot.send_message(
        chat_id,
        f"🎲 <b>SIRA SENDE - {player_name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Bahsin: {format_amount(player_bet)}\n"
        f"🎯 1. zarı at!\n\n"
        f"⏳ {BLACKJACK_TURN} saniye içinde butona tıkla!",
        reply_markup=_dice_kb(game_id, 1),
        parse_mode="HTML"
    )
    
    async with _state_lock:
        if chat_id in _active_games and game_id in _active_games[chat_id]:
            _active_games[chat_id][game_id]["dice_state"]["current_msg_id"] = msg.message_id
    
    # Timeout timer'ı başlat
    task = asyncio.create_task(_dice_timeout(ctx, chat_id, game_id, uid))
    async with _state_lock:
        if chat_id in _active_games and game_id in _active_games[chat_id]:
            _active_games[chat_id][game_id]["dice_state"]["task"] = task


async def _dice_timeout(ctx, chat_id, game_id, uid):
    """Süre dolunca otomatik zar at"""
    await asyncio.sleep(BLACKJACK_TURN)
    
    game = await get_active_game(chat_id, "dice")
    if not game or game["game_id"] != game_id:
        return
    
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data:
            return
        current_player = game_data["dice_state"]["current_player"]
    
    if current_player != uid:
        return
    
    # Otomatik zar at
    await _dice_auto_roll(ctx, chat_id, game_id, uid)


async def _dice_auto_roll(ctx, chat_id, game_id, uid):
    """Otomatik zar atma işlemi"""
    game = await get_active_game(chat_id, "dice")
    if not game:
        return
    
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data:
            return
        
        dice_state = game_data["dice_state"]
        roll_count = dice_state["roll_count"]
        dice1 = dice_state["dice1"]
        dice2 = dice_state["dice2"]
        msg_id = dice_state["current_msg_id"]
        players_data = game_data["players_data"]
        player_name = players_data[uid]["name"]
        player_bet = players_data[uid]["bet"]
    
    if roll_count == 0:
        # 1. zarı otomatik at
        dice1 = random.randint(1, 6)
        dice_img = create_dice_image(dice1)
        
        try:
            await ctx.bot.delete_message(chat_id, msg_id)
        except:
            pass
        
        msg = await ctx.bot.send_photo(
            chat_id,
            photo=dice_img,
            caption=f"🎲 <b>SIRA SENDE - {player_name}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 Bahsin: {format_amount(player_bet)}\n"
                    f"🎲 1. Zar: {dice1} (otomatik)\n"
                    f"🎯 2. zarı at!\n\n"
                    f"⏳ {BLACKJACK_TURN} saniye içinde butona tıkla!",
            reply_markup=_dice_kb(game_id, 2),
            parse_mode="HTML"
        )
        
        async with _state_lock:
            if chat_id in _active_games and game_id in _active_games[chat_id]:
                _active_games[chat_id][game_id]["dice_state"]["roll_count"] = 1
                _active_games[chat_id][game_id]["dice_state"]["dice1"] = dice1
                _active_games[chat_id][game_id]["dice_state"]["current_msg_id"] = msg.message_id
                if dice_state.get("task"):
                    dice_state["task"].cancel()
                new_task = asyncio.create_task(_dice_timeout(ctx, chat_id, game_id, uid))
                _active_games[chat_id][game_id]["dice_state"]["task"] = new_task
        
    else:
        # 2. zarı otomatik at
        dice2 = random.randint(1, 6)
        combined_img = combine_dice_with_total(dice1, dice2)
        total = dice1 + dice2
        
        try:
            await ctx.bot.delete_message(chat_id, msg_id)
        except:
            pass
        
        await ctx.bot.send_photo(
            chat_id,
            photo=combined_img,
            caption=f"🎲 <b>{player_name} - SONUÇ</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🎲 Zarlar: {dice1} + {dice2} = {total} (otomatik)\n"
                    f"✅ Tamamlandı!\n\n"
                    f"⏳ Sıradaki oyuncuya geçiliyor...",
            parse_mode="HTML"
        )
        
        async with _state_lock:
            if chat_id in _active_games and game_id in _active_games[chat_id]:
                _active_games[chat_id][game_id]["players_rolled"][uid] = {
                    "total": total,
                    "dice1": dice1,
                    "dice2": dice2,
                    "name": player_name,
                    "bet": player_bet
                }
                _active_games[chat_id][game_id]["dice_state"]["current_index"] += 1
                _active_games[chat_id][game_id]["dice_state"]["current_player"] = None
                _active_games[chat_id][game_id]["dice_state"]["roll_count"] = 0
                _active_games[chat_id][game_id]["dice_state"]["dice1"] = None
                _active_games[chat_id][game_id]["dice_state"]["dice2"] = None
                if dice_state.get("task"):
                    dice_state["task"].cancel()
        
        await asyncio.sleep(2)
        await _dice_start_next_player(ctx, chat_id, game_id)


async def dice_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Zar atma butonu callback'i"""
    query = update.callback_query
    await query.answer()
    
    try:
        action, game_id = query.data.split(":", 1)
    except:
        await query.answer("Hata!", show_alert=True)
        return
    
    user = query.from_user
    chat_id = query.message.chat_id
    
    game = await get_active_game(chat_id, "dice")
    if not game or game["game_id"] != game_id:
        await query.answer("Oyun bitti.", show_alert=True)
        return
    
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data:
            await query.answer("Oyun bulunamadı.", show_alert=True)
            return
        
        current_player = game_data["dice_state"]["current_player"]
    
    if current_player != user.id:
        await query.answer("Şu an sıra sende değil!", show_alert=True)
        return
    
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data:
            return
        
        dice_state = game_data["dice_state"]
        roll_count = dice_state["roll_count"]
        dice1 = dice_state["dice1"]
        players_data = game_data["players_data"]
        player_name = players_data[user.id]["name"]
        player_bet = players_data[user.id]["bet"]
        
        # Önceki timeout'u iptal et
        if dice_state.get("task"):
            dice_state["task"].cancel()
    
    if roll_count == 0:
        # 1. zar
        dice1 = random.randint(1, 6)
        dice_img = create_dice_image(dice1)
        
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=dice_img,
                caption=f"🎲 <b>SIRA SENDE - {player_name}</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"💰 Bahsin: {format_amount(player_bet)}\n"
                        f"🎲 1. Zar: {dice1}\n"
                        f"🎯 2. zarı at!\n\n"
                        f"⏳ {BLACKJACK_TURN} saniye içinde butona tıkla!",
                parse_mode="HTML"
            ),
            reply_markup=_dice_kb(game_id, 2)
        )
        
        async with _state_lock:
            if chat_id in _active_games and game_id in _active_games[chat_id]:
                _active_games[chat_id][game_id]["dice_state"]["roll_count"] = 1
                _active_games[chat_id][game_id]["dice_state"]["dice1"] = dice1
                new_task = asyncio.create_task(_dice_timeout(ctx, chat_id, game_id, user.id))
                _active_games[chat_id][game_id]["dice_state"]["task"] = new_task
        
    else:
        # 2. zar
        dice2 = random.randint(1, 6)
        combined_img = combine_dice_with_total(dice1, dice2)
        total = dice1 + dice2
        
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=combined_img,
                caption=f"🎲 <b>{player_name} - SONUÇ</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🎲 Zarlar: {dice1} + {dice2} = {total}\n"
                        f"✅ Tamamlandı!\n\n"
                        f"⏳ Sıradaki oyuncuya geçiliyor...",
                parse_mode="HTML"
            )
        )
        
        async with _state_lock:
            if chat_id in _active_games and game_id in _active_games[chat_id]:
                _active_games[chat_id][game_id]["players_rolled"][user.id] = {
                    "total": total,
                    "dice1": dice1,
                    "dice2": dice2,
                    "name": player_name,
                    "bet": player_bet
                }
                _active_games[chat_id][game_id]["dice_state"]["current_index"] += 1
                _active_games[chat_id][game_id]["dice_state"]["current_player"] = None
                _active_games[chat_id][game_id]["dice_state"]["roll_count"] = 0
                _active_games[chat_id][game_id]["dice_state"]["dice1"] = None
                _active_games[chat_id][game_id]["dice_state"]["dice2"] = None
        
        await asyncio.sleep(2)
        await _dice_start_next_player(ctx, chat_id, game_id)


async def _dice_calculate_results(ctx, chat_id, game_id):
    """Sonuçları hesapla ve kazananları belirle"""
    game = await get_active_game(chat_id, "dice")
    if not game or game["game_id"] != game_id:
        return
    
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data:
            return
        players = game_data["players_rolled"]
        pool = game_data["pool"]
    
    max_score = max(p["total"] for p in players.values())
    winners = [(uid, data) for uid, data in players.items() if data["total"] == max_score]
    
    prize_per_winner = pool // len(winners)
    remaining = pool - (prize_per_winner * len(winners))
    
    results = [
        f"🆔 GAME ID: {game_id}\n",
        f"🎲 <b>ZAR OYUNU SONUÇLARI</b>",
        f"━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    for uid, data in players.items():
        results.append(f"🎲 {data['name']}: {data['dice1']} + {data['dice2']} = {data['total']}")
    
    results.append("━━━━━━━━━━━━━━━━━━━━━")
    
    if len(winners) == 1:
        uid, data = winners[0]
        payout = prize_per_winner + remaining
        await add_balance(uid, payout, "win", f"Zar game:{game_id}")
        await update_stats(uid, payout)
        await update_win_rate(uid, "dice", True)
        
        results.append(f"🏆 <b>KAZANAN: {data['name']}</b>")
        results.append(f"💰 Kazanç: {format_amount(payout)}")
        
        for uid2 in players.keys():
            if uid2 != uid:
                await update_win_rate(uid2, "dice", False)
    else:
        results.append(f"🤝 <b>BERABERLİK! {len(winners)} kazanan</b>")
        for uid, data in winners:
            await add_balance(uid, prize_per_winner, "win", f"Zar game:{game_id}")
            await update_stats(uid, prize_per_winner)
            await update_win_rate(uid, "dice", True)
            results.append(f"💰 {data['name']}: +{format_amount(prize_per_winner)}")
        
        for uid2 in players.keys():
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
#  ÇARKIFELEK
# ═══════════════════════════════════════════════════════════════

async def cmd_wheelbet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Çarkıfelek oyunu başlat"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    if is_rate_limited(user.id): 
        return
    
    ok, err = await can_open_game(chat_id, "wheel")
    if not ok:
        await update.message.reply_text(f"❌ {err}")
        return
    
    # Önce oyunu oluştur
    game = await create_game(chat_id, "wheel", 0)
    gid = game["game_id"]
    
    msg = await update.message.reply_text(
        f"🎡 <b>ÇARKIFELEK BAŞLADI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 GAME ID: {gid}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>{BET_WINDOW} saniye</b> içinde bahis yapın!\n\n"
        f"📌 /wheel &lt;miktar&gt; veya /wheel allin\n\n"
        f"💀 PASS | 🔄 İADE | 2x | 3x | 5x | 10x | 15x | 25x | 50x | 100x",
        parse_mode="HTML"
    )
    
    # Mesaj ID'sini güncelle
    async with _state_lock:
        if chat_id in _active_games and gid in _active_games[chat_id]:
            _active_games[chat_id][gid]["message_id"] = msg.message_id
    
    asyncio.create_task(_wheel_timer(ctx, chat_id, gid))


async def cmd_wheel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Çarkıfelek oyununa bahis yap"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    if is_rate_limited(user.id): 
        return
    
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
        await update.message.reply_text("❌ Açık çarkıfelek yok veya süre doldu.")
        return
    
    # Bahsi düş
    ok = await remove_balance(user.id, amount, "bet", f"Çark game:{game['game_id']}")
    if not ok:
        await update.message.reply_text("❌ Yetersiz bakiye.")
        return
    
    # Bahis verisini hazırla
    bd = {"type": "wheel", "name": user.full_name}
    
    # Bahsi ekle
    await add_participant(chat_id, game["game_id"], user.id, amount, bd)
    
    # Toplam bahsi hesapla
    parts = await get_participants(chat_id, game["game_id"])
    user_bets = parts.get(user.id, {}).get("bets", [])
    total_bet = sum(b["bet"] for b in user_bets)
    
    await update.message.reply_text(
        f"🕹 <b>{user.full_name}</b> 🎡 {format_amount(amount)} bahis yaptı\n"
        f"💰 Bu oyunda toplam bahsiniz: {format_amount(total_bet)}",
        parse_mode="HTML"
    )


async def _wheel_timer(ctx, chat_id, game_id):
    """Süre dolunca çarkı döndür ve sonuçları hesapla"""
    await asyncio.sleep(BET_WINDOW)
    
    game = await get_active_game(chat_id, "wheel")
    if not game or game["game_id"] != game_id:
        return
    
    game["state"] = "CALCULATING"
    
    # Segmentleri karıştır ve rastgele seç
    shuffled_segments = random.sample(WHEEL_SEGMENTS, len(WHEEL_SEGMENTS))
    label, mult = secrets.choice(shuffled_segments)
    
    # Katılımcıları al
    parts = await get_participants(chat_id, game_id)
    
    lines = [
        f"🆔 GAME ID: {game_id}\n",
        f"🎡 <b>ÇARK DÖNDÜ!</b>",
        f"━━━━━━━━━━━━━━━━━━━━━",
        f"🎯 Sonuç: <b>{label}</b>",
        ""
    ]
    
    total_payout = 0
    
    if not parts:
        lines.append("😴 Kimse bahis yapmadı.")
    elif mult == 0:
        # PASS - tam kayıp
        lines.append("💀 <b>PASS!</b> Herkes kaybetti.")
        for uid, data in parts.items():
            for bet_wrapper in data.get("bets", []):
                await update_stats(uid, 0)
                await update_win_rate(uid, "wheel", False)
                lines.append(f"  ❌ {bet_wrapper['bet_data']['name']}: -{format_amount(bet_wrapper['bet'])}")
    elif mult == 1:
        # İADE
        lines.append("🔄 <b>İADE!</b> Bahisler geri ödendi.")
        for uid, data in parts.items():
            for bet_wrapper in data.get("bets", []):
                await add_balance(uid, bet_wrapper["bet"], "refund", f"Çark iade game:{game_id}")
                await update_stats(uid, 0)
                await update_win_rate(uid, "wheel", True)
                lines.append(f"  🔄 {bet_wrapper['bet_data']['name']}: +0 (iade)")
    else:
        # Kazanç var
        lines.append(f"🏆 <b>{label} ({mult}x)</b>")
        for uid, data in parts.items():
            for bet_wrapper in data.get("bets", []):
                payout = bet_wrapper["bet"] * mult
                await add_balance(uid, payout, "win", f"Çark game:{game_id}")
                await update_stats(uid, payout)
                await update_win_rate(uid, "wheel", True)
                total_payout += payout
                net = payout - bet_wrapper["bet"]
                lines.append(f"  ✅ {bet_wrapper['bet_data']['name']}: +{format_amount(net)}")
    
    if mult > 0 and mult != 1:
        lines.append("")
        lines.append(f"💰 Toplam dağıtılan: {format_amount(total_payout)}")
    
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append("✨ Yeni oyun için /wheelbet")
    
    await ctx.bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")
    await finish_game(chat_id, game_id, label)
    await cleanup(chat_id)
    
    
    
    
# ═══════════════════════════════════════════════════════════════
#  KAZI KAZAN GÖRSEL FONKSİYONLARI
# ═══════════════════════════════════════════════════════════════

def create_scratch_result_image(board: list, winner_mult: int) -> io.BytesIO:
    """Açık kart görseline sonuçları yaz"""
    acik_kart = os.path.join(BASE_DIR, "acik.jpg")
    
    if not os.path.exists(acik_kart):
        img = Image.new('RGB', (800, 600), color='#1a1a2e')
    else:
        img = Image.open(acik_kart)
    
    img.thumbnail((800, 600), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(img)
    font = get_font(100)
    
    width, height = img.size
    
    # 6 kutunun merkez koordinatları
    boxes = [
        {"center": (width * 0.16, height * 0.25), "index": 0},
        {"center": (width * 0.51, height * 0.25), "index": 1},
        {"center": (width * 0.83, height * 0.25), "index": 2},
        {"center": (width * 0.16, height * 0.69), "index": 3},
        {"center": (width * 0.51, height * 0.69), "index": 4},
        {"center": (width * 0.83, height * 0.69), "index": 5},
    ]
    
    for box in boxes:
        center_x = int(box["center"][0])
        center_y = int(box["center"][1])
        value = board[box["index"]]
        
        # Renk belirle
        if value == winner_mult and winner_mult > 0:
            text_color = (0, 255, 0)  # Yeşil - kazanan
        elif value == 0:
            text_color = (255, 0, 0)  # Kırmızı - kayıp
        else:
            text_color = (255, 255, 255)  # Beyaz - normal
        
        text = f"{value}x"
        
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        
        # Gölgeli yazı
        draw.text((center_x - tw/2 + 3, center_y - th/2 + 3), text, 
                  fill=(0, 0, 0), font=font, stroke_width=3, stroke_fill=(0, 0, 0))
        draw.text((center_x - tw/2, center_y - th/2), text, 
                  fill=text_color, font=font)
    
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    return bio


# ═══════════════════════════════════════════════════════════════
#  KAZI KAZAN SOLO
# ═══════════════════════════════════════════════════════════════

async def cmd_kazisolo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Tek kişilik Kazı Kazan"""
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
    
    ok = await remove_balance(user.id, amount, "bet", "Kazı Kazan Solo")
    if not ok:
        await update.message.reply_text("❌ Yetersiz bakiye.")
        return
    
    # Kapalı kartı göster
    kapali_kart = os.path.join(BASE_DIR, "Kapali.jpg")
    if os.path.exists(kapali_kart):
        with open(kapali_kart, "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=f"🎟 <b>KAZI KAZAN (SOLO)</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"💰 Bahis: {format_amount(amount)}\n"
                        f"✨ KAZIYORSUN... ✨",
                parse_mode="HTML"
            )
    else:
        await update.message.reply_text(
            f"🎟 <b>KAZI KAZAN (SOLO)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Bahis: {format_amount(amount)}\n"
            f"✨ KAZIYORSUN... ✨",
            parse_mode="HTML"
        )
    
    await asyncio.sleep(1.5)
    
    # Kazı kazı tahtası oluştur
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
            caption=f"🎟 <b>KAZI KAZAN (SOLO)</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{msg}\n"
                    f"💳 Yeni bakiye: {format_amount(new_bal)}",
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
                f"🎟 <b>KAZI KAZAN (SOLO)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ {winner_mult}x bulundu!\n"
                f"🎉 KAZANDIN! +{format_amount(payout - amount)}\n"
                f"💳 Yeni bakiye: {format_amount(new_bal)}",
                parse_mode="HTML"
            )
        else:
            await update_stats(user.id, 0)
            await update_win_rate(user.id, "scratch", False)
            await update.message.reply_text(
                f"🎟 <b>KAZI KAZAN (SOLO)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"❌ Eşleşme yok!\n"
                f"💀 KAYBETTİN! -{format_amount(amount)}",
                parse_mode="HTML"
            )


# ═══════════════════════════════════════════════════════════════
#  KAZI KAZAN TURNUVA
# ═══════════════════════════════════════════════════════════════

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
    
    game = await create_game(chat_id, "scratch_tournament", 0)
    gid = game["game_id"]
    
    caption = (
        f"🎟 <b>KAZI KAZAN TURNUVASI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 GAME ID: {gid}\n"
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
    
    async with _state_lock:
        if chat_id in _active_games and gid in _active_games[chat_id]:
            _active_games[chat_id][gid]["message_id"] = msg.message_id
            _active_games[chat_id][gid]["min_bet"] = 0
            _active_games[chat_id][gid]["pool"] = 0
            _active_games[chat_id][gid]["players_data"] = {}
    
    asyncio.create_task(_scratch_countdown(ctx, chat_id, gid, msg.message_id))
    asyncio.create_task(_scratch_tournament_timer(ctx, chat_id, gid))


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
        await update.message.reply_text("❌ Açık turnuva yok veya süre doldu.")
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
        
        players = game_data.get("players_data", {})
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
            if user.id in game_data["players_data"]:
                game_data["players_data"][user.id]["bet"] += amount
                total_bet = game_data["players_data"][user.id]["bet"]
                await update.message.reply_text(
                    f"🕹 <b>{user.full_name}</b> 🎟️ +{format_amount(amount)} "
                    f"(Toplam: {format_amount(total_bet)})",
                    parse_mode="HTML"
                )
            else:
                game_data["players_data"][user.id] = {"bet": amount, "name": user.full_name}
                await update.message.reply_text(
                    f"🕹 <b>{user.full_name}</b> 🎟️ {format_amount(amount)} ile katıldı!",
                    parse_mode="HTML"
                )
            game_data["pool"] = game_data.get("pool", 0) + amount


async def _scratch_countdown(ctx, chat_id, game_id, message_id):
    """Geri sayım - mesajı güncelle"""
    for remaining in range(BET_WINDOW, 0, -5):
        await asyncio.sleep(5)
        game = await get_active_game(chat_id, "scratch_tournament")
        if not game or game["game_id"] != game_id or game["state"] != "OPEN":
            return
        
        async with _state_lock:
            game_data = _active_games.get(chat_id, {}).get(game_id)
            if not game_data:
                return
            players_count = len(game_data.get("players_data", {}))
            pool = game_data.get("pool", 0)
        
        try:
            await ctx.bot.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=f"🎟 <b>KAZI KAZAN TURNUVASI</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🆔 GAME ID: {game_id}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"⏱ Kalan: {remaining} sn\n"
                        f"👥 Katılımcı: {players_count}\n"
                        f"💰 Havuz: {format_amount(pool)}",
                parse_mode="HTML"
            )
        except:
            pass


async def _scratch_tournament_timer(ctx, chat_id, game_id):
    """Süre dolunca sonuçları hesapla"""
    await asyncio.sleep(BET_WINDOW)
    
    game = await get_active_game(chat_id, "scratch_tournament")
    if not game or game["game_id"] != game_id:
        return
    
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data:
            return
        players = game_data.get("players_data", {}).copy()
    
    if len(players) < 2:
        for uid, d in players.items():
            await add_balance(uid, d["bet"], "refund", "Kazi Turnuva İptal")
        await ctx.bot.send_message(
            chat_id,
            f"❌ <b>KAZI KAZAN TURNUVASI İPTAL!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"En az 2 oyuncu gerekli. Bahisler iade edildi.",
            parse_mode="HTML"
        )
        await finish_game(chat_id, game_id, "iptal")
        await cleanup(chat_id)
        return
    
    # Kazı kazı tahtası oluştur
    board = [secrets.choice(SCRATCH_POOL) for _ in range(6)]
    counts = Counter(board)
    winner_mult = 0
    for mult, count in counts.most_common():
        if count >= 3 and mult > 0:
            winner_mult = mult
            break
    
    try:
        result_img = create_scratch_result_image(board, winner_mult)
        lines = [
            f"🆔 GAME ID: {game_id}\n",
            f"🎟 <b>KAZI KAZAN SONUCU</b>",
            f"━━━━━━━━━━━━━━━━━━━━━"
        ]
        
        if winner_mult > 0:
            lines.append(f"✅ <b>{winner_mult}x</b> eşleşmesi bulundu!")
            lines.append(f"🎉 <b>HERKES KAZANDI!</b>\n")
            total_payout = 0
            for uid, d in players.items():
                payout = d["bet"] * winner_mult
                await add_balance(uid, payout, "win", f"Kazi Turnuva {winner_mult}x")
                await update_stats(uid, payout)
                net = payout - d["bet"]
                lines.append(f"✅ {d['name']}: +{format_amount(net)}")
                total_payout += payout
                await update_win_rate(uid, "scratch", True)
            lines.append(f"\n💰 Toplam dağıtılan: {format_amount(total_payout)}")
        else:
            lines.append(f"❌ Eşleşme yok!")
            lines.append(f"😢 <b>HERKES KAYBETTİ!</b>\n")
            for uid, d in players.items():
                await update_stats(uid, 0)
                lines.append(f"❌ {d['name']}: -{format_amount(d['bet'])}")
                await update_win_rate(uid, "scratch", False)
        
        lines.append("━━━━━━━━━━━━━━━━━━━━━")
        lines.append("✨ Yeni turnuva için /kazibet")
        
        await ctx.bot.send_photo(
            chat_id,
            photo=result_img,
            caption="\n".join(lines),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Kazi turnuva görsel hatası: {e}")
        msg = f"🆔 GAME ID: {game_id}\n\n🎟 <b>KAZI KAZAN SONUCU</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
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
#  VIP KASA (STARS SATIN ALMA)
# ═══════════════════════════════════════════════════════════════

async def cmd_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """VIP Kasa - Telegram Stars ile satın alma menüsü"""
    keyboard = []
    for stars, config in STARS_CONFIG.items():
        keyboard.append([
            InlineKeyboardButton(
                f"🌟 {stars} Stars → {config['label']} {format_amount(config['coin'])}",
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
    """Paket seçildiğinde fatura oluştur"""
    query = update.callback_query
    await query.answer()
    
    stars = int(query.data.split("_")[1])
    config = STARS_CONFIG[stars]
    coin_amount = config["coin"]
    user = query.from_user
    
    await ctx.bot.send_invoice(
        chat_id=user.id,
        title=f"{stars} Telegram Stars",
        description=f"{config['label']} - {format_amount(coin_amount)}",
        payload=f"stars_{stars}",
        provider_token="",  # Stars için boş
        currency="XTR",
        prices=[LabeledPrice(label=f"{stars} Stars", amount=stars)],
        start_parameter="vip_kasa",
        need_name=False,
        need_phone_number=False,
        need_email=False
    )


async def pre_checkout_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Ödeme öncesi onay"""
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def successful_payment_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Başarılı ödeme - Coinleri ekle"""
    user = update.effective_user
    payload = update.message.successful_payment.invoice_payload
    stars = int(payload.split("_")[1])
    
    coin_amount = STARS_CONFIG[stars]["coin"]
    label = STARS_CONFIG[stars]["label"]
    
    await add_balance(user.id, coin_amount, "stars_purchase", f"{stars} Stars ile {label}")
    new_balance = await get_balance(user.id)
    
    await update.message.reply_text(
        f"✅ <b>SATIN ALMA BAŞARILI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌟 {stars} Stars → {label}\n"
        f"💰 Hesabınıza eklenen: {format_amount(coin_amount)}\n"
        f"💳 Yeni bakiyeniz: {format_amount(new_balance)}\n\n"
        f"🎉 İyi eğlenceler!",
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
    
    ana_menu_button = [[InlineKeyboardButton("🏠 ANA MENÜ", callback_data="menu_main")]]
    
    if data == "menu_roulette":
        await query.edit_message_text(
            "🎰 <b>RULET NASIL OYNANIR?</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ /rulet ile oyun başlatın\n"
            "2️⃣ 25 saniye içinde bahis yapın:\n"
            "   🔴 /red &lt;miktar&gt; - Kırmızıya bahis\n"
            "   ⚫ /black &lt;miktar&gt; - Siyaha bahis\n"
            "   🟢 /green &lt;miktar&gt; - Yeşile bahis (0)\n"
            "   🔢 /number &lt;sayı&gt; &lt;miktar&gt; - Tek sayı\n"
            "   🔢 /numbers &lt;1,2,3&gt; &lt;miktar&gt; - Çoklu sayı\n\n"
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
            "2️⃣ 25 saniye içinde /bj &lt;miktar&gt; ile bahis yapın\n"
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
            "2️⃣ 25 saniye içinde /dice &lt;miktar&gt; ile katılın\n"
            "3️⃣ En az 2 oyuncu gerekir\n"
            "4️⃣ Sırayla butona tıklayarak zar atın\n"
            "5️⃣ En yüksek zar toplamı kazanır\n"
            "6️⃣ Beraberlikte havuz bölüşülür\n\n"
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
            "2️⃣ 25 saniye içinde /wheel &lt;miktar&gt; ile bahis yapın\n"
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
            "📌 /kazisolo &lt;miktar&gt; - Tek başına oyna\n\n"
            "🎟️ <b>TURNUVASI</b>\n"
            "1️⃣ /kazibet - Turnuva başlat\n"
            "2️⃣ /kazi &lt;miktar&gt; - Turnuvaya katıl (en az 2 kişi)\n\n"
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
            db = await get_db()
            higher_count = await db.users.count_documents({"balance": {"$gt": u["balance"]}})
            rank = higher_count + 1
            
            lvl, emoji = get_level(u["balance"])
            
            await query.edit_message_text(
                f"📌 <b>Verilerim</b>\n\n"
                f"👤 <b>{user.full_name}</b>\n\n"
                f"🤴 Seviye 🔘 {lvl} {emoji}\n\n"
                f"🏧 Bakiye 🔘 {format_amount(u['balance'])}\n\n"
                f"🌍 Genel Sıralamanız 🔘 {rank}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
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
        # Direkt daily bonusu ver, fake update'e gerek yok
        u = await get_or_create_user(user.id, user.username, user.full_name)
        db = await get_db()
        lock = await _get_lock(user.id)
        
        async with lock:
            user_data = await db.users.find_one({"telegram_id": user.id})
            last_daily = user_data.get("last_daily")
            current_streak = user_data.get("daily_streak", 0)
            
            can_claim, hours_left = can_claim_daily(last_daily)
            
            if not can_claim:
                await query.edit_message_text(
                    f"⏰ <b>Günlük bonusunuzu zaten aldınız!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🎁 Sonraki bonus: <b>{hours_left} saat</b> sonra\n"
                    f"📈 Mevcut seri: <b>{current_streak} gün</b>",
                    reply_markup=InlineKeyboardMarkup(ana_menu_button),
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
            
            await query.edit_message_text(
                f"🎁 <b>GÜNLÜK BONUS!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>{user.full_name}</b>\n"
                f"📅 Seri: <b>{new_streak}</b> gün\n"
                f"💰 Kazanılan: <b>+{format_amount(bonus_amount)}</b>\n"
                f"💳 Yeni bakiye: <b>{format_amount(new_balance)}</b>\n\n"
                f"🎯 Yarınki bonus: <b>{format_amount(next_bonus)}</b>",
                reply_markup=InlineKeyboardMarkup(ana_menu_button),
                parse_mode="HTML"
            )
        
    elif data == "menu_buy":
        await query.edit_message_text(
            "🌟 <b>VIP KASA</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "Telegram Stars ile oyun parası satın al:\n\n"
            "⭐ 10 Stars → 1.0M🪙BKT\n"
            "⭐ 25 Stars → 50.0M🪙BKT\n"
            "⭐ 50 Stars → 1.0B🪙BKT\n"
            "⭐ 100 Stars → 10.0B🪙BKT\n"
            "⭐ 250 Stars → 100.0B🪙BKT\n"
            "⭐ 500 Stars → 1.0T🪙BKT\n"
            "⭐ 1000 Stars → 10.0T🪙BKT\n\n"
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
        {"state": {"$in": ["OPEN", "PLAYING", "CALCULATING", "BETTING", "DEALING", "ROLLING"]}},
        {"$set": {"state": "FINISHED", "finished_at": datetime.now()}}
    )
    logger.info("🧹 Takılı kalmış oyunlar temizlendi.")


async def backup_task():
    """24 saatte bir yedekleme yap"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    while True:
        await asyncio.sleep(24 * 3600)
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = os.path.join(BACKUP_DIR, f"casinobot_{ts}.json")
            
            db = await get_db()
            users = await db.users.find().to_list(length=None)
            transactions = await db.transactions.find().to_list(length=None)
            games = await db.games.find().to_list(length=None)
            user_stats = await db.user_stats.find().to_list(length=None)
            
            import json
            backup_data = {
                "users": users,
                "transactions": transactions,
                "games": games,
                "user_stats": user_stats,
                "backup_date": datetime.now().isoformat()
            }
            
            # datetime objelerini string'e çevir
            def json_serial(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")
            
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, default=json_serial, indent=2)
            
            logger.info(f"📦 Backup alındı: {dest}")
            
            # Son 7 backup'ı tut, eskileri sil
            backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith('.json')])
            for old in backups[:-7]:
                os.remove(os.path.join(BACKUP_DIR, old))
                logger.info(f"🗑️ Eski backup silindi: {old}")
                
        except Exception as e:
            logger.error(f"Backup hatası: {e}")


async def save_group_to_db(chat_id: int, title: str):
    """Grubu veritabanına kaydet (reklam için)"""
    try:
        db = await get_db()
        await db.groups.update_one(
            {"chat_id": chat_id},
            {"$set": {
                "chat_id": chat_id,
                "title": title,
                "is_active": True,
                "last_seen": datetime.now()
            }},
            upsert=True
        )
    except Exception as e:
        logger.error(f"Grup kaydedilemedi: {e}")


async def on_chat_member_update(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Bot gruba eklendiğinde veya çıkarıldığında"""
    chat = update.effective_chat
    my_chat_member = update.my_chat_member
    
    if my_chat_member.new_chat_member.status == "member":
        await save_group_to_db(chat.id, chat.title)
        logger.info(f"✅ Bot gruba eklendi: {chat.title} ({chat.id})")
    
    elif my_chat_member.new_chat_member.status in ["left", "kicked"]:
        db = await get_db()
        await db.groups.update_one(
            {"chat_id": chat.id},
            {"$set": {"is_active": False, "removed_at": datetime.now()}}
        )
        logger.info(f"❌ Bot gruptan çıkarıldı: {chat.title} ({chat.id})")


async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Her mesajda grubu veritabanına kaydet (yedek yöntem)"""
    chat = update.effective_chat
    if chat.type in ["group", "supergroup"]:
        await save_group_to_db(chat.id, chat.title)
        
        
        
        
# ═══════════════════════════════════════════════════════════════
#  POST INIT / SHUTDOWN
# ═══════════════════════════════════════════════════════════════

async def post_init(app):
    """Bot başlatıldığında çalışır"""
    await init_db()
    await cleanup_stuck_games()
    asyncio.create_task(backup_task())
    logger.info("🎰 CasiniBot başlatıldı!")
    logger.info(f"📁 BASE_DIR: {BASE_DIR}")
    logger.info(f"💾 MongoDB: {'Bağlı' if _db is not None else 'Bağlantı yok'}")

async def post_shutdown(app):
    """Bot kapatıldığında çalışır"""
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()
        logger.info("🔌 MongoDB bağlantısı kapatıldı.")
    logger.info("👋 CasiniBot kapatıldı.")


# ═══════════════════════════════════════════════════════════════
#  MAIN FONKSİYON
# ═══════════════════════════════════════════════════════════════

def main():
    """Ana fonksiyon - Botu başlatır"""
    
    # Bot token kontrolü
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ BOT_TOKEN ayarlanmamış!")
        return
    
    logger.info(f"🤖 Bot token: {BOT_TOKEN[:10]}...")
    
    # Application oluştur
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    
    # ═══════════════════════════════════════════════════════════
    #  GENEL KOMUTLAR
    # ═══════════════════════════════════════════════════════════
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("jackpot", cmd_jackpot))
    app.add_handler(CommandHandler("changename", cmd_changename))
    app.add_handler(CommandHandler("moneys", cmd_moneys))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("daily", cmd_daily))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("id", cmd_id))
    
    # ═══════════════════════════════════════════════════════════
    #  RULET
    # ═══════════════════════════════════════════════════════════
    app.add_handler(CommandHandler("rulet", cmd_rulet))
    app.add_handler(CommandHandler("red", cmd_red))
    app.add_handler(CommandHandler("black", cmd_black))
    app.add_handler(CommandHandler("green", cmd_green))
    app.add_handler(CommandHandler("number", cmd_number))
    app.add_handler(CommandHandler("numbers", cmd_numbers))
    
    # ═══════════════════════════════════════════════════════════
    #  BLACKJACK
    # ═══════════════════════════════════════════════════════════
    app.add_handler(CommandHandler("blackjack", cmd_blackjack))
    app.add_handler(CommandHandler("bj", cmd_bj))
    app.add_handler(CallbackQueryHandler(bj_callback, pattern=r"^bj_(hit|stand):"))
    
    # ═══════════════════════════════════════════════════════════
    #  ZAR OYUNU
    # ═══════════════════════════════════════════════════════════
    app.add_handler(CommandHandler("dicebet", cmd_dicebet))
    app.add_handler(CommandHandler("dice", cmd_dice))
    app.add_handler(CallbackQueryHandler(dice_callback, pattern=r"^dice_roll:"))
    
    # ═══════════════════════════════════════════════════════════
    #  ÇARKIFELEK
    # ═══════════════════════════════════════════════════════════
    app.add_handler(CommandHandler("wheelbet", cmd_wheelbet))
    app.add_handler(CommandHandler("wheel", cmd_wheel))
    
    # ═══════════════════════════════════════════════════════════
    #  KAZI KAZAN
    # ═══════════════════════════════════════════════════════════
    app.add_handler(CommandHandler("kazisolo", cmd_kazisolo))
    app.add_handler(CommandHandler("kazibet", cmd_kazibet))
    app.add_handler(CommandHandler("kazi", cmd_kazi))
    
    # ═══════════════════════════════════════════════════════════
    #  VIP KASA (STARS)
    # ═══════════════════════════════════════════════════════════
    app.add_handler(CommandHandler("buy", cmd_buy))
    app.add_handler(CallbackQueryHandler(buy_callback, pattern=r"^buy_"))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    # ═══════════════════════════════════════════════════════════
    #  ADMIN KOMUTLARI
    # ═══════════════════════════════════════════════════════════
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("addbalance", cmd_addbalance))
    app.add_handler(CommandHandler("setbalance", cmd_setbalance))
    app.add_handler(CommandHandler("cleanup", cmd_cleanup))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("testjackpot", cmd_testjackpot))
    
    # ═══════════════════════════════════════════════════════════
    #  MENÜ CALLBACK
    # ═══════════════════════════════════════════════════════════
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu_"))
    
    # ═══════════════════════════════════════════════════════════
    #  GRUP TAKİP (ChatMemberHandler)
    # ═══════════════════════════════════════════════════════════
    from telegram.ext import ChatMemberHandler
    app.add_handler(ChatMemberHandler(on_chat_member_update, ChatMemberHandler.MY_CHAT_MEMBER))
    
    # ═══════════════════════════════════════════════════════════
    #  MESAJ HANDLER (Grup kaydetme için)
    # ═══════════════════════════════════════════════════════════
    app.add_handler(MessageHandler(filters.ChatType.GROUPS, on_message))
    
    # ═══════════════════════════════════════════════════════════
    #  HATA YAKALAMA
    # ═══════════════════════════════════════════════════════════
    async def error_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Hata yakalayıcı"""
        logger.error(f"❌ Hata: {ctx.error}", exc_info=ctx.error)
        
        try:
            if update and update.effective_chat:
                await ctx.bot.send_message(
                    update.effective_chat.id,
                    "❌ Bir hata oluştu. Lütfen tekrar deneyin."
                )
        except:
            pass
    
    app.add_error_handler(error_handler)
    
    # ═══════════════════════════════════════════════════════════
    #  BOTU BAŞLAT
    # ═══════════════════════════════════════════════════════════
    logger.info("🚀 Handler'lar yüklendi. Polling başlıyor...")
    logger.info(f"📋 Toplam handler: {len(app.handlers)}")
    
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=[
            Update.MESSAGE,
            Update.CALLBACK_QUERY,
            Update.PRE_CHECKOUT_QUERY,
            Update.CHAT_MEMBER,
            Update.MY_CHAT_MEMBER
        ]
    )


# ═══════════════════════════════════════════════════════════════
#  PROGRAM GİRİŞİ
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
                
                
                
                

        
        
        
        
        

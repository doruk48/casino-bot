
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

import aiosqlite
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import BadRequest

from PIL import Image, ImageDraw, ImageFont
import io

# ═══════════════════════════════════════════════════════════════
#  MERKEZİ OYUN KORUYUCU (Hata Yönetimi, İade, Limit Kontrolü)
# ═══════════════════════════════════════════════════════════════

import asyncio
import traceback
from functools import wraps

# Maksimum bakiye limiti (SQLite güvenli sınır)
MAX_SAFE_BALANCE = 8_000_000_000_000_000_000  # 8 Katrilyon (8Q)
WARNING_LIMIT = 7_000_000_000_000_000_000     # 7Q (uyarı limiti)

def safe_game(game_name: str):
    """Dekoratör: Oyunları hatalara karşı korur, bahisleri iade eder"""
    def decorator(func):
        @wraps(func)
        async def wrapper(ctx, chat_id, game_id, *args, **kwargs):
            try:
                # Oyunu çalıştır
                result = await func(ctx, chat_id, game_id, *args, **kwargs)
                return result
                
            except OverflowError as e:
                # Büyük sayı hatası (SQLite sınırı)
                logger.error(f"🔥 {game_name} OverflowError: {e}")
                await _handle_game_error(ctx, chat_id, game_id, game_name, "BÜYÜK SAYI HATASI", e)
                
            except Exception as e:
                # Diğer hatalar
                logger.error(f"🔥 {game_name} Hatası: {e}")
                logger.error(traceback.format_exc())
                await _handle_game_error(ctx, chat_id, game_id, game_name, "BEKLENMEDİK HATA", e)
        
        return wrapper
    return decorator


async def _handle_game_error(ctx, chat_id, game_id, game_name, error_type, error):
    """Hata yönetimi ve bahis iadesi"""
    
    # 1. Bahisleri iade et
    parts = await get_participants(chat_id, game_id)
    iade_edilen = 0
    total_refund = 0
    
    for uid, data in parts.items():
        bet = data["bet"]
        success = await add_balance(uid, bet, "refund", f"{game_name} iade (hata)")
        if success:
            iade_edilen += 1
            total_refund += bet
    
    # 2. Oyunu sonlandır
    await finish_game(chat_id, game_id, f"hata_{error_type}")
    await cleanup(chat_id)
    
    # 3. Kullanıcıya bilgi ver
    await ctx.bot.send_message(
        chat_id,
        f"❌ <b>{game_name} - HATA!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔍 Hata: {error_type}\n"
        f"💰 {iade_edilen} oyuncuya {format_amount(total_refund)} iade edildi.\n\n"
        f"⚠️ Bot sahibine bildirildi. Özür dileriz!",
        parse_mode="HTML"
    )


async def check_balance_limit(uid: int, amount: int, bet: int = 0) -> tuple:
    """
    Bakiye limitini kontrol et
    Returns: (uyarı_var_mı, mesaj)
    """
    db = await get_db()
    async with db.execute("SELECT balance FROM users WHERE telegram_id=?", (uid,)) as c:
        row = await c.fetchone()
    
    current = row["balance"] if row else 0
    new_balance = current + amount
    
    if new_balance >= MAX_SAFE_BALANCE:
        return True, f"🏆 <b>SINIRA ULAŞTIN!</b> Maksimum bakiye: {format_amount(MAX_SAFE_BALANCE)}"
    
    if new_balance >= WARNING_LIMIT:
        remaining = MAX_SAFE_BALANCE - new_balance
        return True, f"⚠️ <b>BAKİYE UYARISI!</b> Maksimum sınıra {format_amount(remaining)} kaldı."
    
    return False, ""


async def safe_add_balance(uid: int, amount: int, tx_type="win", desc="") -> tuple:
    """
    Güvenli bakiye ekleme (limit kontrolü ile)
    Returns: (başarılı_mı, mesaj)
    """
    if amount <= 0:
        return False, "Miktar sıfırdan büyük olmalı."
    
    # Limit kontrolü
    uyari, mesaj = await check_balance_limit(uid, amount)
    if uyari and "SINIRA ULAŞTIN" in mesaj:
        return False, mesaj
    
    # Normal ekleme
    success = await add_balance(uid, amount, tx_type, desc)
    
    if success and uyari:
        return True, mesaj
    
    return success, ""


# KULLANIM ÖRNEKLERİ:

# ═══════════════════════════════════════════════════════════════
#  AYARLAR
# ═══════════════════════════════════════════════════════════════

BOT_TOKEN = "7640572418:AAHhT1uzlpeNlTr7_sP2yJ3_6GNJ6Ph6JDs"
DATABASE_PATH = "casinibot.db"
STARTING_BALANCE = 1000000
CURRENCY_SYMBOL = "🪙"
BET_WINDOW = 25
BLACKJACK_TURN = 15
MAX_OPEN_GAMES = 5
LEADERBOARD_SIZE = 15
LEADERBOARD_CACHE_TTL = 60
RATE_LIMIT_SECONDS = 1
BACKUP_DIR = "casinibot_backups"
LOG_FILE = "casinibot.log"

# Rulet multiplier'ları
ROULETTE_MULTIPLIERS = {"red": 2, "black": 2, "green": 72, "number": 36}  


# Rulet görsel klasörü
ROULETTE_IMG_PATH = ""

# Blackjack görsel klasörü
BLACKJACK_IMG_PATH = ""

WHEEL_SEGMENTS = [
    # PASS - 10 dilim (%40)
    ("💀 PASS 💀", 0), ("💀 PASS 💀", 0), ("💀 PASS 💀", 0),
    ("💀 PASS 💀", 0), ("💀 PASS 💀", 0), ("💀 PASS 💀", 0),
    ("💀 PASS 💀", 0), ("💀 PASS 💀", 0), ("💀 PASS 💀", 0),
    ("💀 PASS 💀", 0),
    
    # 2x - 4 dilim (%16)
    ("🟢 2x", 2), ("🟢 2x", 2), ("🟢 2x", 2), ("🟢 2x", 2),
    
    # 5x - 3 dilim (%12)
    ("🟢 5x", 5), ("🟢 5x", 5), ("🟢 5x", 5),
    
    # 10x - 3 dilim (%12)
    ("🔵 10x", 10), ("🔵 10x", 10), ("🔵 10x", 10),
    
    # 25x - 2 dilim (%8)
    ("🔵 25x", 25), ("🔵 25x", 25),
    
    # 50x - 1 dilim (%4)
    ("🟣 50x", 50),
    
    # 100x - 1 dilim (%4)
    ("🟣 100x", 100),
    
    # 250x - 1 dilim (%4)
    ("🟡 250x", 250),
]

# Kazı Kazan sembolleri
SCRATCH_SYMBOLS = [
    (250, 1),   # 250x
    (100, 2),   # 100x
    (50, 3),    # 50x
    (20, 5),    # 20x
    (10, 10),   # 10x
    (5, 15),    # 5x
    (3, 20),    # 3x
    (2, 29),    # 2x
    (0, 15),    # Kaybet
]

# Kazı Kazan havuzu (önemli!)
SCRATCH_POOL = []
for val, weight in SCRATCH_SYMBOLS:
    SCRATCH_POOL.extend([val] * weight)

# Kazı Kazan emojileri
SCRATCH_EMOJI = {
    250: "🔥👑💎🔥",
    100: "💎💎💎✨",
    50: "💎💎🌟",
    20: "⭐🌟⭐",
    10: "🏆🥇🏆",
    5: "🔹🔹🔹",
    3: "🟤🟤🟤",
    2: "💰💰",
    0: "💀🌑💀"
}

# Level sistemi
LEVELS = [
    (0, "Çırak", "🪵"),
    (500, "Bahisçi", "🎯"),
    (5_000, "Kumarbaz", "🎲"),
    (25_000, "Bronz", "🥉"),
    (100_000, "Gümüş", "🥈"),
    (500_000, "Altın", "🥇"),
    (2_000_000, "Platin", "💎"),
    (10_000_000, "Elmas", "💠"),
    (50_000_000, "Efsane", "👑"),
    (250_000_000, "Efsanevi", "🌟"),
    (1_000_000_000, "Milyarder", "💰"),
    (5_000_000_000, "Mega Milyarder", "💰💰"),
    (25_000_000_000, "Trilyoner", "💎💰"),
    (100_000_000_000, "Mega Trilyoner", "💎💰💰"),
    (500_000_000_000, "Katrilyoner", "✨💰"),
    (1_000_000_000_000, "Mega Katrilyoner", "✨💰💰"),
    (5_000_000_000_000, "Kozmik", "🌌"),
    (25_000_000_000_000, "Sonsuzluk", "♾️"),
    (100_000_000_000_000, "Mutlak", "💫"),
    (500_000_000_000_000, "Yüce", "👁️"),
    (1_000_000_000_000_000, "Casino Tanrısı", "🏆🌌"),
    (5_000_000_000_000_000, "Kozmik Tanrı", "🌠🏆"),
    (10_000_000_000_000_000, "Evrensel", "🌌✨"),
    (25_000_000_000_000_000, "Sonsuz Güç", "⚡♾️"),
    (50_000_000_000_000_000, "Mutlak Güç", "💫👑"),
    (100_000_000_000_000_000, "Efsanevi Tanrı", "🏆🌌✨"),
]

# Rulet renkleri
RED_NUMS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
ROUL_COLORS = {0: "green"}
for n in range(1, 37):
    ROUL_COLORS[n] = "red" if n in RED_NUMS else "black"
ROUL_EMOJI = {"red": "🔴", "black": "⚫", "green": "🟢"}

# Blackjack
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["♠️", "♥️", "♦️", "♣️"]

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

# Görsel klasör kontrolü
if os.path.exists(ROULETTE_IMG_PATH):
    logger.info(f"✅ Rulet görsel klasörü bulundu: {ROULETTE_IMG_PATH}")
else:
    logger.warning(f"⚠️ Rulet görsel klasörü bulunamadı: {ROULETTE_IMG_PATH}")

# ═══════════════════════════════════════════════════════════════
#  VERİTABANI (Aynı kalacak)
# ═══════════════════════════════════════════════════════════════

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DATABASE_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
        await _db.execute("PRAGMA synchronous=NORMAL")
    return _db


async def init_db():
    db = await get_db()
    
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id   INTEGER PRIMARY KEY,
            username      TEXT,
            display_name  TEXT NOT NULL,
            balance       INTEGER NOT NULL DEFAULT 1000,
            total_wagered INTEGER NOT NULL DEFAULT 0,
            total_won     INTEGER NOT NULL DEFAULT 0,
            games_played  INTEGER NOT NULL DEFAULT 0,
            last_daily    TEXT,
            daily_streak  INTEGER DEFAULT 0,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id     INTEGER,
            to_id       INTEGER,
            amount      INTEGER NOT NULL,
            type        TEXT NOT NULL,
            description TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        CREATE TABLE IF NOT EXISTS games (
            game_id     TEXT PRIMARY KEY,
            chat_id     INTEGER NOT NULL,
            game_type   TEXT NOT NULL,
            state       TEXT NOT NULL DEFAULT 'OPEN',
            result      TEXT,
            message_id  INTEGER,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            finished_at TEXT
        );
        
        CREATE TABLE IF NOT EXISTS game_participants (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id     TEXT NOT NULL,
            telegram_id INTEGER NOT NULL,
            bet_amount  INTEGER NOT NULL,
            bet_data    TEXT,
            payout      INTEGER DEFAULT 0,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        CREATE INDEX IF NOT EXISTS idx_users_balance ON users(balance DESC);
        CREATE INDEX IF NOT EXISTS idx_games_chat ON games(chat_id, state);
        CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(from_id, to_id);
        CREATE INDEX IF NOT EXISTS idx_game_participants_game ON game_participants(game_id);
    """)
    
    # Eski veritabanı için kolon ekleme
    try:
        await db.execute("ALTER TABLE users ADD COLUMN last_daily TEXT")
    except:
        pass
    try:
        await db.execute("ALTER TABLE users ADD COLUMN daily_streak INTEGER DEFAULT 0")
    except:
        pass
    
    await db.commit()
    logger.info("Veritabanı hazır.")


# ═══════════════════════════════════════════════════════════════
#  EKONOMİ (Aynı kalacak)
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
    """Büyük sayıları formatla (K, M, B, T, Q, Qt, Sx, Sp, Ot)"""
    if amount < 1000:
        return f"{amount}{CURRENCY_SYMBOL}"
    
    # Büyük birimler
    units = [
        (10**15, "Q"),    # Katrilyon
        (10**18, "Qt"),   # Kuintilyon
        (10**21, "Sx"),   # Sekstilyon
        (10**24, "Sp"),   # Septilyon
        (10**27, "Ot"),   # Oktilyon
    ]
    
    for unit, suffix in units:
        if amount >= unit:
            value = amount / unit
            if value >= 1000:
                continue
            if value >= 100:
                formatted = f"{value:.0f}"
            elif value >= 10:
                formatted = f"{value:.1f}"
            else:
                formatted = f"{value:.2f}".rstrip('0').rstrip('.')
            return f"{formatted}{suffix}{CURRENCY_SYMBOL}"
    
    # Trilyon ve altı
    for div, suf in [(10**12, "T"), (10**9, "B"), (10**6, "M"), (10**3, "K")]:
        if amount >= div:
            v = amount / div
            formatted = f"{v:.2f}".rstrip('0').rstrip('.')
            return f"{formatted}{suf}{CURRENCY_SYMBOL}"
    
    return f"{amount}{CURRENCY_SYMBOL}"

def parse_amount(text: str, balance: int) -> tuple[int | None, str]:
    if text.lower() == "allin":
        return (balance, "") if balance > 0 else (None, "Bakiyeniz yetersiz.")
    text = text.lower().replace(",", "").replace(".", "")
    muls = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000, "t": 1_000_000_000_000}
    try:
        val = int(text[:-1]) * muls[text[-1]] if text and text[-1] in muls else int(text)
    except (ValueError, IndexError):
        return None, "Geçersiz miktar."
    if val <= 0:
        return None, "Miktar 0'dan büyük olmalı."
    if val > balance:
        return None, f"Yetersiz bakiye. Bakiyeniz: {format_amount(balance)}"
    return val, ""


async def get_or_create_user(uid: int, username, name: str) -> dict:
    db = await get_db()
    async with await _get_lock(uid):
        async with db.execute("SELECT * FROM users WHERE telegram_id=?", (uid,)) as c:
            row = await c.fetchone()
        if row is None:
            await db.execute(
                "INSERT INTO users (telegram_id,username,display_name,balance) VALUES (?,?,?,?)",
                (uid, username, name, STARTING_BALANCE))
            await db.execute(
                "INSERT INTO transactions (to_id,amount,type,description) VALUES (?,?,'bonus','Başlangıç')",
                (uid, STARTING_BALANCE))
            await db.commit()
            async with db.execute("SELECT * FROM users WHERE telegram_id=?", (uid,)) as c:
                row = await c.fetchone()
        else:
            if username != row["username"] or name != row["display_name"]:
                await db.execute(
                    "UPDATE users SET username=?,display_name=?,updated_at=datetime('now') WHERE telegram_id=?",
                    (username, name, uid))
                await db.commit()
    return dict(row)


async def get_user(uid: int) -> dict | None:
    db = await get_db()
    async with db.execute("SELECT * FROM users WHERE telegram_id=?", (uid,)) as c:
        row = await c.fetchone()
    return dict(row) if row else None


async def get_balance(uid: int) -> int:
    u = await get_user(uid)
    return u["balance"] if u else 0


async def add_balance(uid: int, amount: int, tx_type="win", desc="") -> bool:
    if amount <= 0:
        return False
    
    # 🔧 MAX BAKİYE: 10^30 (Sekstilyon)
    MAX_BALANCE = 9_000_000_000_000_000_000
    
    db = await get_db()
    lock = await _get_lock(uid)
    
    async with lock:
        async with db.execute("SELECT balance FROM users WHERE telegram_id=?", (uid,)) as c:
            row = await c.fetchone()
        
        new_balance = row["balance"] + amount
        if new_balance > MAX_BALANCE:
            # Sınıra ulaştı, daha fazla ekleme
            return False
        
        await db.execute("UPDATE users SET balance=balance+?,updated_at=datetime('now') WHERE telegram_id=?", (amount, uid))
        await db.execute("INSERT INTO transactions (to_id,amount,type,description) VALUES (?,?,?,?)", (uid, amount, tx_type, desc))
        await db.commit()
        return True


async def remove_balance(uid: int, amount: int, tx_type="bet", desc="") -> bool:
    if amount <= 0:
        return False
    db = await get_db()
    lock = await _get_lock(uid)
    async with lock:
        async with db.execute("SELECT balance FROM users WHERE telegram_id=?", (uid,)) as c:
            row = await c.fetchone()
        if not row or row["balance"] < amount:
            return False
        await db.execute(
            "UPDATE users SET balance=balance-?,total_wagered=total_wagered+?,updated_at=datetime('now') WHERE telegram_id=?",
            (amount, amount, uid))
        await db.execute(
            "INSERT INTO transactions (from_id,amount,type,description) VALUES (?,?,?,?)",
            (uid, amount, tx_type, desc))
        await db.commit()
        return True


async def update_stats(uid: int, won: int):
    db = await get_db()
    await db.execute(
        "UPDATE users SET total_won=total_won+?,games_played=games_played+1,updated_at=datetime('now') WHERE telegram_id=?",
        (won, uid))
    await db.commit()


async def get_leaderboard(limit=15) -> list[dict]:
    db = await get_db()
    async with db.execute(
        "SELECT telegram_id,display_name,balance FROM users ORDER BY balance DESC LIMIT ?", (limit,)
    ) as c:
        return [dict(r) for r in await c.fetchall()]


# ═══════════════════════════════════════════════════════════════
#  STATE MANAGER (Aynı kalacak)
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
        "game_id": game_id, "chat_id": chat_id, "game_type": game_type,
        "state": "OPEN", "message_id": message_id, "participants": {},
        "result": None, "task": None,
    }
    async with _state_lock:
        _active_games.setdefault(chat_id, {})[game_id] = game
    db = await get_db()
    await db.execute(
        "INSERT INTO games (game_id,chat_id,game_type,state,message_id) VALUES (?,?,?,?,?)",
        (game_id, chat_id, game_type, "OPEN", message_id))
    await db.commit()
    return game


async def get_active_game(chat_id: int, game_type: str) -> dict | None:
    async with _state_lock:
        for g in _active_games.get(chat_id, {}).values():
            if g["game_type"] == game_type and g["state"] != "FINISHED":
                return g
    return None


async def add_participant(chat_id: int, game_id: str, uid: int, bet: int, bet_data: dict):
    """Oyuncu bahislerini EKLE - ÜZERİNE YAZMA!"""
    async with _state_lock:
        game = _active_games.get(chat_id, {}).get(game_id)
        if not game:
            return
        
        if uid in game["participants"]:
            # Mevcut bahis miktarını ARTIR
            game["participants"][uid]["bet"] += bet
            
            # 🔧 DÜZELTME: Bet_data'yı BİRLEŞTİR (üzerine yazma!)
            existing_data = game["participants"][uid]["bet_data"]
            
            # 🔧 YENİ: 'type' anahtarının varlığını kontrol et
            existing_type = existing_data.get("type")
            new_type = bet_data.get("type")
            
            # Sadece her iki tipte de 'type' varsa ve aynıysa birleştir
            if existing_type and new_type and existing_type == new_type:
                if new_type == "color":
                    # Renk bahisleri için tüm renkleri kaydet
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
                    # Sayı bahisleri için tüm sayıları birleştir
                    if "numbers" not in existing_data:
                        existing_data["numbers"] = []
                    existing_data["numbers"].extend(bet_data["numbers"])
                    existing_data["numbers"] = list(set(existing_data["numbers"]))
                    existing_data["name"] = bet_data["name"]
                    existing_data["type"] = "number"
            else:
                # Farklı tip bahisler veya type yoksa - mevcut veriyi koru
                # Çarkıfelek gibi oyunlar için (type yok)
                pass
            
            game["participants"][uid]["bet_data"] = existing_data
        else:
            # Yeni oyuncu
            game["participants"][uid] = {"bet": bet, "bet_data": bet_data}
    
    import json
    db = await get_db()
    async with db.execute(
        "SELECT id FROM game_participants WHERE game_id=? AND telegram_id=?", (game_id, uid)
    ) as c:
        row = await c.fetchone()
    if row:
        await db.execute(
            "UPDATE game_participants SET bet_amount=bet_amount+? WHERE id=?",
            (bet, row["id"]))
    else:
        await db.execute(
            "INSERT INTO game_participants (game_id,telegram_id,bet_amount,bet_data) VALUES (?,?,?,?)",
            (game_id, uid, bet, json.dumps(bet_data)))
    await db.commit()

async def get_participants(chat_id: int, game_id: str) -> dict:
    async with _state_lock:
        game = _active_games.get(chat_id, {}).get(game_id)
        return dict(game["participants"]) if game else {}


async def finish_game(chat_id: int, game_id: str, result: str = ""):
    async with _state_lock:
        if game_id in _active_games.get(chat_id, {}):
            _active_games[chat_id][game_id]["state"] = "FINISHED"
    db = await get_db()
    await db.execute(
        "UPDATE games SET state='FINISHED',result=?,finished_at=datetime('now') WHERE game_id=?",
        (result, game_id))
    await db.commit()


async def cleanup(chat_id: int):
    async with _state_lock:
        if chat_id in _active_games:
            _active_games[chat_id] = {
                gid: g for gid, g in _active_games[chat_id].items()
                if g["state"] != "FINISHED"
            }


# ═══════════════════════════════════════════════════════════════
#  RATE LIMITER (Aynı kalacak)
# ═══════════════════════════════════════════════════════════════

_last_cmd: dict[int, float] = {}


def is_rate_limited(uid: int) -> bool:
    now = time.monotonic()
    if now - _last_cmd.get(uid, 0) < RATE_LIMIT_SECONDS:
        return True
    _last_cmd[uid] = now
    return False


# ═══════════════════════════════════════════════════════════════
#  GENEL KOMUTLAR (Aynı kalacak)
# ═══════════════════════════════════════════════════════════════

_lb_cache: dict = {"data": None, "ts": 0}


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = await get_or_create_user(user.id, user.username, user.full_name)
    lvl, emoji = get_level(u["balance"])
    await update.message.reply_text(
        f"🎰 <b>CasiniBot'a Hoş Geldiniz!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{user.full_name}</b> [{lvl}] {emoji}\n"
        f"💳 Başlangıç bakiyeniz: {format_amount(u['balance'])}\n\n"
        f"🍀 Bol şans!\n📌 Komutlar için /help",
        parse_mode="HTML")


async def cmd_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Yeni balance görünümü"""
    user = update.effective_user
    
    if is_rate_limited(user.id):
        return
    
    await get_or_create_user(user.id, user.username, user.full_name)
    u = await get_user(user.id)
    lvl, emoji = get_level(u["balance"])
    
    # Haftalık puan ve sıralama (geçici - sonra düzenlenecek)
    weekly_score = u.get("weekly_score", 0)
    rank = u.get("rank", 0)
    referans = u.get("referans", 0)
    
    await update.message.reply_text(
        f"📌 <b>Verilerim</b>\n\n"
        f"👤 <b>{user.full_name}</b>\n\n"
        f"🤴 Seviye 🔘 <b>{lvl}</b> {emoji}\n\n"
        f"🏧 Bakiye 🔘 <b>{format_amount(u['balance'])}</b> 🪙\n\n"
        f"🚀 Haftalık Puan 🔘 <b>{weekly_score}</b>\n\n"
        f"🌍 Genel Sıralamanız 🔘 <b>{rank}</b>\n\n"
        f"🔗 Referans Sayısı 🔘 <b>{referans}</b>",
        parse_mode="HTML"
    )


async def cmd_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Yeni liderlik tablosu görünümü"""
    if is_rate_limited(update.effective_user.id):
        return
    
    rows = await get_leaderboard(10)  # İlk 10 kullanıcı
    
    # Seviye emojileri ve isimleri
    level_styles = {
        "Elite": "🔥",
        "Diamond": "💎",
        "Platinum": "🔱",
        "Gold": "🥇",
        "Silver": "🥈",
        "Bronze": "🥉",
        "Starter": "⚪",
        "Broke": "💀"
    }
    
    # Sıra emojileri
    rank_emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    lines = ["🏆 <b>En Zengin 10 Kullanıcı</b> 🏆", ""]
    
    for i, row in enumerate(rows):
        telegram_id = row['telegram_id']
        name = row['display_name'][:15]  # 15 karakterle sınırla
        balance = row['balance']
        level, _ = get_level(balance)
        
        # Seviye stilini al
        level_style = level_styles.get(level, "⭐")
        level_name = level
        
        rank_emoji = rank_emojis[i] if i < 10 else f"{i+1}️⃣"
        
        # Miktarı formatla (T, B, M, K)
        formatted_balance = format_amount(balance)
        
        lines.append(
            f"{rank_emoji} {name} ❇️  {formatted_balance}  {level_style}{level_name}"
        )
    
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_moneys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_rate_limited(user.id): return
    args = ctx.args
    reply = update.message.reply_to_message

    if not args:
        await update.message.reply_text(
            "💸 Kullanım: /moneys &lt;miktar&gt;\n(Birine reply yaparak veya /moneys @kullaniciadi miktar)",
            parse_mode="HTML"); return

    if reply:
        target = reply.from_user
        amount_str = args[0]
    elif len(args) >= 2 and args[0].startswith("@"):
        db = await get_db()
        async with db.execute("SELECT * FROM users WHERE username=?", (args[0][1:],)) as c:
            row = await c.fetchone()
        if not row:
            await update.message.reply_text("❌ Kullanıcı bulunamadı."); return
        class _U:
            id = row["telegram_id"]
            full_name = row["display_name"]
        target = _U()
        amount_str = args[1]
    else:
        await update.message.reply_text("❌ Hedef kullanıcıyı belirtin."); return

    await get_or_create_user(user.id, user.username, user.full_name)
    bal = await get_balance(user.id)
    amount, err = parse_amount(amount_str, bal)
    if err:
        await update.message.reply_text(f"❌ {err}"); return

	 # ═══════════════════════════════════════════════════════════════
#  PARA TRANSFERİ - PROFESYONEL TASARIM (SON HAL)
# ═══════════════════════════════════════════════════════════════

from PIL import Image, ImageDraw, ImageFont
import io
from datetime import datetime
import os
import re

TRANSFER_TEMPLATE_PATH = "transfer.png"

def clean_name(name: str) -> str:
    """Sadece harf, rakam ve boşluk bırak"""
    cleaned = re.sub(r'[^a-zA-Z0-9ğüşıöçĞÜŞİÖÇ\s]', '', name)
    return cleaned.strip()


async def get_display_name(uid: int) -> str:
    """Kullanıcının görünen ismini al (changename ile oluşturulan)"""
    db = await get_db()
    async with db.execute("SELECT display_name FROM users WHERE telegram_id = ?", (uid,)) as c:
        row = await c.fetchone()
    if row and row['display_name']:
        return clean_name(row['display_name'])
    return str(uid)  # Yoksa ID kullan


def create_transfer_image(sender: str, receiver: str, amount: int) -> io.BytesIO:
    """Profesyonel transfer görseli"""
    
    if not os.path.exists(TRANSFER_TEMPLATE_PATH):
        raise Exception(f"Transfer görseli bulunamadı: {TRANSFER_TEMPLATE_PATH}")
    
    img = Image.open(TRANSFER_TEMPLATE_PATH).convert('RGBA')
    width, height = img.size
    
    txt_layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)
    
    # ==================== RENDER'DA VAR OLAN FONTLAR ====================
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf"
    ]
    
    font_isim = None
    font_miktar = None
    font_token = None
    
    for path in font_paths:
        try:
            font_isim = ImageFont.truetype(path, 82)
            font_miktar = ImageFont.truetype(path, 120)
            font_token = ImageFont.truetype(path, 56)
            print(f"✅ Font yüklendi: {path}")
            break
        except:
            continue
    
    if font_isim is None:
        font_isim = font_miktar = font_token = ImageFont.load_default()
        print("⚠️ Font bulunamadı, default kullanılıyor")
    
    # ... devam eden kod (yazı yazma kısmı) ...
    # ==================== KOORDİNATLAR ====================
    scale_x = width / 1024
    scale_y = height / 700
    
    sender_x = int(580 * scale_x)
    sender_y = int(130 * scale_y)
    
    receiver_x = int(580 * scale_x)
    receiver_y = int(370 * scale_y)
    
    amount_x = int(480 * scale_x)
    amount_y = int(600 * scale_y)
    
    # ==================== RENKLER ====================
    text_color = "#F5F5F5"
    gold_color = "#D4AF37"
    
    # ==================== GÖLGE ====================
    shadow_offset = 3
    shadow_color = (0, 0, 0, 77)
    
    # ==================== 1️⃣ GÖNDEREN ====================
    draw.text((sender_x + shadow_offset, sender_y + shadow_offset), sender, 
              fill=shadow_color, font=font_isim, anchor="mm")
    draw.text((sender_x, sender_y), sender, fill=text_color, font=font_isim, anchor="mm")
    
    # ==================== 2️⃣ ALICI ====================
    draw.text((receiver_x + shadow_offset, receiver_y + shadow_offset), receiver, 
              fill=shadow_color, font=font_isim, anchor="mm")
    draw.text((receiver_x, receiver_y), receiver, fill=text_color, font=font_isim, anchor="mm")
    
    # ==================== 3️⃣ MİKTAR ====================
    amount_text = format_amount(amount).replace("🪙", "").strip()
    
    draw.text((amount_x + shadow_offset, amount_y + shadow_offset), amount_text, 
              fill=shadow_color, font=font_miktar, anchor="lm")
    draw.text((amount_x, amount_y), amount_text, fill=gold_color, font=font_miktar, anchor="lm")
    
    # ==================== 4️⃣ TOKEN (sağ) ====================
    try:
        text_width = draw.textlength(amount_text, font=font_miktar)
    except:
        text_width = 200
    
    token_x = amount_x + text_width + 25
    token_y = amount_y + 15
    draw.text((token_x + shadow_offset, token_y + shadow_offset), "Token", 
              fill=shadow_color, font=font_token, anchor="lm")
    draw.text((token_x, token_y), "Token", fill=gold_color, font=font_token, anchor="lm")
    
    # ==================== KATMANLARI BİRLEŞTİR ====================
    img = Image.alpha_composite(img, txt_layer)
    
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (0, 0, 0))
        background.paste(img, mask=img.split()[3])
        img = background
    
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    return bio

async def cmd_moneys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Para transferi - Profesyonel görsel + Caption"""
    user = update.effective_user
    
    if is_rate_limited(user.id):
        return
    
    args = ctx.args
    reply = update.message.reply_to_message
    
    # Hedef kullanıcıyı belirle
    target = None
    amount_str = ""
    
    if reply:
        target = reply.from_user
        amount_str = args[0] if args else ""
    elif len(args) >= 2 and args[0].startswith("@"):
        username = args[0][1:]
        db = await get_db()
        async with db.execute("SELECT telegram_id, display_name FROM users WHERE username = ?", (username,)) as c:
            row = await c.fetchone()
        if not row:
            await update.message.reply_text("❌ Kullanıcı bulunamadı.")
            return
        target = type('User', (), {'id': row['telegram_id'], 'full_name': row['display_name']})()
        amount_str = args[1]
    elif len(args) >= 2:
        try:
            target_id = int(args[0])
            db = await get_db()
            async with db.execute("SELECT telegram_id, display_name FROM users WHERE telegram_id = ?", (target_id,)) as c:
                row = await c.fetchone()
            if not row:
                await update.message.reply_text("❌ Kullanıcı bulunamadı.")
                return
            target = type('User', (), {'id': row['telegram_id'], 'full_name': row['display_name']})()
            amount_str = args[1]
        except:
            await update.message.reply_text("❌ Kullanım: /moneys <@kullanici> <miktar>")
            return
    else:
        await update.message.reply_text("❌ Kullanım: /moneys <@kullanici> <miktar>")
        return
    
    # Miktar kontrolü
    await get_or_create_user(user.id, user.username, user.full_name)
    bal = await get_balance(user.id)
    amount, err = parse_amount(amount_str, bal)
    if err:
        await update.message.reply_text(f"❌ {err}")
        return
    
    # Transfer işlemi
    db = await get_db()
    
    async with db.execute("SELECT balance FROM users WHERE telegram_id = ?", (user.id,)) as c:
        row = await c.fetchone()
        if not row or row['balance'] < amount:
            await update.message.reply_text("❌ Yetersiz bakiye.")
            return
    
    await db.execute("UPDATE users SET balance = balance - ? WHERE telegram_id = ?", (amount, user.id))
    await db.execute("UPDATE users SET balance = balance + ? WHERE telegram_id = ?", (amount, target.id))
    await db.execute(
        "INSERT INTO transactions (from_id, to_id, amount, type, description) VALUES (?, ?, ?, 'transfer', 'Para transferi')",
        (user.id, target.id, amount)
    )
    await db.commit()
    
    # 👇 BURASI ÖNEMLİ: Changename veya ID kullan
    sender_name = await get_display_name(user.id)
    receiver_name = await get_display_name(target.id)
    
    # Görsel oluştur ve gönder
    try:
        img_bytes = create_transfer_image(
            sender=sender_name,
            receiver=receiver_name,
            amount=amount
        )
        
        now = datetime.now()
        caption = (
            f"🏧 Bakiye Transferi Gerçekleştirildi\n\n"
            f"🗓️ {now.strftime('%Y-%m-%d')} ⏰ {now.strftime('%H:%M:%S')} 🌍 (UTC+3:00)"
        )
        
        await update.message.reply_photo(
            photo=img_bytes,
            caption=caption,
            parse_mode="HTML"
        )
        
        # Transfer özeti (görselin altına)
        await update.message.reply_text(
            f"✅ <b>Transfer Başarılı!</b>\n"
            f"📤 {sender_name} → 📥 {receiver_name}\n"
            f"💰 {format_amount(amount)}\n"
            f"💳 Yeni bakiyeniz: {format_amount(await get_balance(user.id))}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Transfer görseli hatası: {e}")
        await update.message.reply_text(
            f"✅ <b>Transfer Başarılı!</b>\n"
            f"📤 {sender_name} → 📥 {receiver_name}\n"
            f"💰 {format_amount(amount)}\n"
            f"💳 Yeni bakiyeniz: {format_amount(await get_balance(user.id))}",
            parse_mode="HTML"
        )
        
        
        
        
async def cmd_changename(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_rate_limited(user.id): return
    if not ctx.args:
        await update.message.reply_text("✏️ Kullanım: /changename <yeni isim>"); return
    name = " ".join(ctx.args)[:32]
    if len(name) < 2:
        await update.message.reply_text("❌ En az 2 karakter."); return
    db = await get_db()
    await db.execute(
        "UPDATE users SET display_name=?,updated_at=datetime('now') WHERE telegram_id=?",
        (name, user.id))
    await db.commit()
    await update.message.reply_text(f"✅ İsminiz <b>{name}</b> olarak güncellendi!", parse_mode="HTML")


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎰 <b>CASINİBOT KOMUTLAR</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👤 <b>HESAP</b>\n"
        "/start — Kayıt / Hoş geldin\n"
        "/balance — Bakiyeni göster\n"
        "/changename — İsim değiştir\n"
        "/leaderboard — İlk 15 oyuncu\n"
        "/moneys &lt;miktar&gt; — Para gönder\n"
        "/daily — Günlük bonus al\n\n"
        "🎡 <b>RULETİ</b>\n"
        "/rulet — Rulet başlat\n"
        "/green &lt;miktar&gt;\n"
        "/red &lt;miktar&gt;\n"
        "/black &lt;miktar&gt;\n"
        "/number &lt;sayı&gt; &lt;miktar&gt;\n"
        "/numbers &lt;1,2,3&gt; &lt;miktar&gt;\n\n"
        "🎲 <b>ZAR (PvP)</b>\n"
        "/dicebet — Başlat | /dice &lt;miktar&gt; — Katıl\n\n"
        "🎡 <b>ÇARKIFELEK</b>\n"
        "/wheelbet — Başlat | /wheel &lt;miktar&gt; — Bahis\n\n"
        "🎟 <b>KAZI KAZAN</b>\n"
        "/kazi &lt;miktar&gt; — Oyna\n\n"
        "🃏 <b>BLACKJACK</b>\n"
        "/blackjack — Başlat | /bj &lt;miktar&gt; — Bahis\n\n"
        "💡 Miktar yerine <code>allin</code> yazarak tüm bakiyeni yatırabilirsin!",
        parse_mode="HTML")

# ═══════════════════════════════════════════════════════════════
#  ADMIN KOMUTLARI
# ═══════════════════════════════════════════════════════════════

# Admin ID'leri (kendi ID'nizi ekleyin)
ADMIN_IDS = [6927797531]  # Sizin ID'niz

async def cmd_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """ID öğrenme komutu"""
    user = update.effective_user
    await update.message.reply_text(
        f"🆔 <b>Telegram ID'niz:</b>\n"
        f"<code>{user.id}</code>\n\n"
        f"👤 Kullanıcı: {user.full_name}",
        parse_mode="HTML"
    )

async def cmd_addbalance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin komutu - Kendinize para ekleyin"""
    user = update.effective_user
    
    # Admin kontrolü
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Bu komutu kullanma yetkiniz yok!")
        return
    
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "💸 <b>Kullanım:</b> /addbalance &lt;miktar&gt;\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "Örnekler:\n"
            "• /addbalance 1000000\n"
            "• /addbalance 10m (10 milyon)\n"
            "• /addbalance 1b (1 milyar)\n"
            "• /addbalance 1t (1 trilyon)",
            parse_mode="HTML"
        )
        return
    
    # Miktarı parse et
    amount, err = parse_amount(args[0], 10**18)
    if err:
        await update.message.reply_text(f"❌ {err}")
        return
    
    # Para ekle
    await add_balance(user.id, amount, "admin", f"Admin tarafından eklendi: {args[0]}")
    
    await update.message.reply_text(
        f"✅ <b>BAKİYE EKLENDİ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Eklenen: +{format_amount(amount)}\n"
        f"💳 Yeni bakiye: {format_amount(await get_balance(user.id))}",
        parse_mode="HTML"
    )
# ═══════════════════════════════════════════════════════════════
#  AVRUPA RULETİ (DÜZELTİLMİŞ VERSİYON) - SADECE GÖRSEL EKLENDİ
# ═══════════════════════════════════════════════════════════════

def format_number_with_emoji(number: int) -> str:
    """Sayıyı emoji rakamlara çevir (2️⃣5️⃣ şeklinde)"""
    emoji_digits = {
        '0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
        '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'
    }
    return ''.join(emoji_digits[d] for d in str(number))


def get_roulette_image(number: int) -> str:
    """Rulet sonucuna göre görsel dosya yolunu döndürür"""
    # Görseller ana klasörde olduğu için doğrudan dosya adını kullan
    if number == 0:
        img_path = "0.jpg"
    else:
        img_path = f"{number}.jpg"
    
    # Görsel yoksa spin.jpg kullan
    if not os.path.exists(img_path):
        if os.path.exists("spin.jpg"):
            img_path = "spin.jpg"
    
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
    caption = (
        f"🎰 <b>AVRUPA RULETİ BAŞLADI!</b>\n"
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
                msg = await update.message.reply_photo(
                    photo=photo, 
                    caption=caption, 
                    parse_mode="HTML"
                )
        else:
            msg = await update.message.reply_text(caption, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Spin görseli gönderilemedi: {e}")
        msg = await update.message.reply_text(caption, parse_mode="HTML")
    
    game = await create_game(chat_id, "roulette", msg.message_id)
    asyncio.create_task(_roulette_timer(ctx, chat_id, game["game_id"], msg))
    
@safe_game("RULET")
async def _roulette_timer(ctx, chat_id, game_id, msg):
    await asyncio.sleep(BET_WINDOW)
    game = await get_active_game(chat_id, "roulette")
    if not game or game["game_id"] != game_id: return
    game["state"] = "CALCULATING"
    
    import random
    winning = random.randint(0, 36)
    color = ROUL_COLORS[winning]
    
    print(f"🎲 RULET SONUCU: {winning} - {color.upper()}")
    
    try:
        await ctx.bot.delete_message(chat_id, msg.message_id)
    except BadRequest:
        pass
    
    parts = await get_participants(chat_id, game_id)
    
    print(f"👥 TOPLAM BAHIS: {len(parts)}")
    for uid, data in parts.items():
        print(f"  - {data['bet_data']['name']}: {data['bet_data']} - Bet: {data['bet']}")
    
    winners = []
    losers = []
    
    for uid, data in parts.items():
        bet = data["bet"]
        bd = data["bet_data"]
        
        # 🔧 YENİ: Çoklu renk bahislerini kontrol et
        if bd.get("type") == "color":
            # Eski format (tek renk)
            if "color" in bd and bd["color"]:
                colors_to_check = [bd["color"]]
            # Yeni format (çoklu renk)
            elif "colors" in bd:
                colors_to_check = bd["colors"]
            else:
                colors_to_check = []
            
            print(f"🔍 RENK KONTROL: {bd['name']} bahisleri {colors_to_check} - Sonuç: {color}")
            
            # Her renk için ayrı bahis olarak işle
            per_color_bet = bet // len(colors_to_check) if colors_to_check else 0
            won_any = False
            
            for check_color in colors_to_check:
                if check_color == color:
                    multiplier = ROULETTE_MULTIPLIERS[color]
                    payout = per_color_bet * multiplier
                    await add_balance(uid, payout, "win", f"Rulet game:{game_id}")
                    await update_stats(uid, payout)
                    winners.append(f"{bd['name']} {ROUL_EMOJI[color]} {format_amount(payout)}")
                    won_any = True
                    print(f"  ✅ {check_color.upper()} KAZANDI! +{payout}")
            
            if not won_any:
                await update_stats(uid, 0)
                losers.append(f"❌ {bd['name']} — Tüm bahisler kaybetti -{format_amount(bet)}")
                print(f"  ❌ TÜM RENKLER KAYBETTI! -{bet}")
                
        elif bd.get("type") == "number":
            # Sayı bahisleri (benzer mantık)
            numbers_to_check = bd.get("numbers", [])
            per_number_bet = bet // len(numbers_to_check) if numbers_to_check else 0
            
            if winning in numbers_to_check:
                multiplier = ROULETTE_MULTIPLIERS["number"]
                payout = per_number_bet * multiplier
                await add_balance(uid, payout, "win", f"Rulet game:{game_id}")
                await update_stats(uid, payout)
                winners.append(f"{bd['name']} {ROUL_EMOJI[color]} {format_amount(payout)}")
                print(f"  ✅ SAYI KAZANDI! +{payout}")
            else:
                await update_stats(uid, 0)
                losers.append(f"❌ {bd['name']} — Sayı bahsi kaybetti -{format_amount(bet)}")
                print(f"  ❌ SAYI KAYBETTI! -{bet}")
    
    # 🆕 YENİ SONUÇ MESAJI (Görsel altına yazılacak)
    result_text = f"🆔 GAME ID: <code>{game_id}</code>\n\n"
    result_text += f"🏆 Kazanan Sayı 🔘 {format_number_with_emoji(winning)} {ROUL_EMOJI[color]}!\n\n"
    result_text += f"🏧 Kazanan Kişiler 🔘\n"
    
    if winners:
        for i, winner_text in enumerate(winners[:15], 1):
            if i == 1:
                rank_emoji = "🥇"
            elif i == 2:
                rank_emoji = "🥈"
            elif i == 3:
                rank_emoji = "🥉"
            else:
                rank_emoji = "📍"
            result_text += f" {rank_emoji} {winner_text}\n"
    else:
        result_text += " ❌ Hiç kimse kazanmadı!\n"
    
    print(f"📊 ÖZET: Toplam {len(parts)} bahisçi, Kazanan: {len(winners)} işlem, Kaybeden: {len(losers)} işlem")
    
    # SONUÇ GÖRSELİ GÖNDER
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
    
    # 🔧 DÜZELTİLMİŞ bet_data - TÜM ALANLARI AÇIKÇA BELİRT
    if bet_type == "color":
        bd = {
            "type": "color",
            "color": color,  # 'red', 'black', 'green'
            "numbers": [],
            "name": user.full_name
        }
    else:  # number
        bd = {
            "type": "number",
            "color": None,
            "numbers": numbers or [],
            "name": user.full_name
        }
    
    await add_participant(chat_id, game["game_id"], user.id, amount, bd)
    bal = await get_balance(user.id)
    
    # 🆕 YENİ BAHİS BİLDİRİMİ
    if bet_type == "color":
        color_emoji = {"red": "🔴", "black": "⚫", "green": "🟢"}.get(color, "🔵")
        await update.message.reply_text(
            f"🕹 <b>{user.full_name}</b> {color_emoji} {format_amount(amount)} bahis yaptı",
            parse_mode="HTML"
        )
    else:
        ns = ", ".join(map(str, numbers))
        await update.message.reply_text(
            f"🕹 <b>{user.full_name}</b> 🔵 {format_amount(amount)} sayı bahsi yaptı ([{ns}])",
            parse_mode="HTML"
        )


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
        if n < 0 or n > 36:
            await update.message.reply_text("❌ Geçersiz sayı (0-36).")
            return
    except:
        await update.message.reply_text("❌ Geçersiz sayı (0-36).")
        return
    await _rulet_bet(update, "number", numbers=[n], amount_str=ctx.args[1])

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
#  ZAR OYUNU (GELİŞMİŞ) - SIRALI ATIŞ + GÖRSELLER
# ═══════════════════════════════════════════════════════════════

def create_dice_image(value: int) -> io.BytesIO:
    """Zar görseli oluşturur (kahverengi zemin, siyah noktalar)"""
    size = 80
    img = Image.new('RGB', (size, size), '#8B4513')
    draw = ImageDraw.Draw(img)
    
    # Kenarlık
    draw.rectangle([2, 2, size-3, size-3], outline='#D2691E', width=2)
    
    # Nokta konumları
    positions = {
        1: [(size//2, size//2)],
        2: [(size//4, size//4), (3*size//4, 3*size//4)],
        3: [(size//4, size//4), (size//2, size//2), (3*size//4, 3*size//4)],
        4: [(size//4, size//4), (3*size//4, size//4), (size//4, 3*size//4), (3*size//4, 3*size//4)],
        5: [(size//4, size//4), (3*size//4, size//4), (size//2, size//2), (size//4, 3*size//4), (3*size//4, 3*size//4)],
        6: [(size//4, size//4), (3*size//4, size//4), (size//4, size//2), (3*size//4, size//2), (size//4, 3*size//4), (3*size//4, 3*size//4)]
    }
    
    r = size // 8
    for x, y in positions.get(value, []):
        draw.ellipse([x-r, y-r, x+r, y+r], fill='black')
    
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    return bio


async def cmd_dicebet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Zar oyunu başlat - Sıralı atış sistemi"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    if is_rate_limited(user.id): return
    
    ok, err = await can_open_game(chat_id, "dice")
    if not ok:
        await update.message.reply_text(f"❌ {err}")
        return
    
    msg = await update.message.reply_text(
        f"🎲 <b>ZAR OYUNU BAŞLADI! (Sıralı Atış)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>{BET_WINDOW} saniye</b> içinde katılın!\n\n"
        f"📌 /dice &lt;miktar&gt; veya /dice allin\n\n"
        f"🎯 Oyun Kuralları:\n"
        f"• Her oyuncu sırayla 2 zar atar\n"
        f"• En yüksek toplam kazanır\n"
        f"• Beraberlikte havuz bölüşülür\n"
        f"• Atış yapmayan en düşük puan (2) alır",
        parse_mode="HTML")
    
    game = await create_game(chat_id, "dice", msg.message_id)
    game["min_bet"] = 0
    game["players_rolled"] = {}
    game["current_player_index"] = 0
    game["order"] = []
    game["pool"] = 0
    game["participants_data"] = {}
    asyncio.create_task(_dice_bet_timer(ctx, chat_id, game["game_id"]))


async def cmd_dice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Zar oyununa katıl"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    if is_rate_limited(user.id): return
    if not ctx.args:
        await update.message.reply_text("❌ Kullanım: /dice &lt;miktar&gt;")
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
    """Bahis süresi bitince sıraya geç"""
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
    
    await _next_player_roll(ctx, chat_id, game_id)


async def _next_player_roll(ctx, chat_id, game_id):
    """Sıradaki oyuncuya zar atma butonunu gönder"""
    game = await get_active_game(chat_id, "dice")
    if not game or game["game_id"] != game_id:
        return
    
    idx = game["current_player_index"]
    order = game["order"]
    
    if idx >= len(order):
        await _calculate_dice_results(ctx, chat_id, game_id)
        return
    
    uid = order[idx]
    parts = game["participants_data"]
    player_name = parts[uid]["bet_data"]["name"]
    bet = parts[uid]["bet"]
    
    # Durum gösterimi
    rolled_list = []
    for u in order:
        if u in game["players_rolled"]:
            rolled_list.append(f"✅ {parts[u]['bet_data']['name']}: {game['players_rolled'][u]}")
        elif u == uid:
            rolled_list.append(f"🎯 {player_name}: (Sırada)")
        else:
            rolled_list.append(f"⏳ {parts[u]['bet_data']['name']}: (Bekliyor)")
    
    status_text = "\n".join(rolled_list)
    
    keyboard = [[InlineKeyboardButton("🎲 ZAR AT 🎲", callback_data=f"dice_roll:{game_id}:{uid}")]]
    
    await ctx.bot.send_message(
        chat_id,
        f"🎲 <b>SIRA SENDE!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Oyuncu: <b>{player_name}</b>\n"
        f"💰 Bahis: {format_amount(bet)}\n"
        f"🎯 Toplam havuz: {format_amount(game['pool'])}\n\n"
        f"📊 Durum:\n{status_text}\n\n"
        f"⏱ <b>15 saniyen var!</b>\n"
        f"⬇️ Zar atmak için butona tıkla ⬇️",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    
    game["roll_task"] = asyncio.create_task(_roll_timeout(ctx, chat_id, game_id, uid))


async def _roll_timeout(ctx, chat_id, game_id, uid):
    """Oyuncu süresinde zar atmazsa"""
    await asyncio.sleep(15)
    
    game = await get_active_game(chat_id, "dice")
    if not game or game["game_id"] != game_id:
        return
    
    if uid in game["players_rolled"]:
        return
    
    game["players_rolled"][uid] = 2  # En düşük puan
    parts = game["participants_data"]
    player_name = parts[uid]["bet_data"]["name"]
    
    await ctx.bot.send_message(
        chat_id,
        f"⏰ <b>{player_name}</b> süresinde zar atmadı!\n❌ En düşük puan (2) olarak kaydedildi.",
        parse_mode="HTML"
    )
    
    game["current_player_index"] += 1
    await _next_player_roll(ctx, chat_id, game_id)


async def dice_roll_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Zar atma callback'i"""
    query = update.callback_query
    await query.answer()
    
    try:
        _, game_id, uid = query.data.split(":")
        uid = int(uid)
    except:
        await query.answer("Hata!", show_alert=True)
        return
    
    user = query.from_user
    chat_id = query.message.chat_id
    
    if user.id != uid:
        await query.answer("Bu senin sıran değil!", show_alert=True)
        return
    
    game = await get_active_game(chat_id, "dice")
    if not game or game["game_id"] != game_id:
        await query.answer("Oyun bitti!", show_alert=True)
        return
    
    if uid in game["players_rolled"]:
        await query.answer("Zaten zar attın!", show_alert=True)
        return
    
    if game.get("roll_task"):
        game["roll_task"].cancel()
    
    dice1 = random.randint(1, 6)
    dice2 = random.randint(1, 6)
    total = dice1 + dice2
    
    game["players_rolled"][uid] = total
    parts = game["participants_data"]
    player_name = parts[uid]["bet_data"]["name"]
    
    # Zar görselleri
    try:
        img1 = create_dice_image(dice1)
        img2 = create_dice_image(dice2)
        
        await query.message.reply_photo(photo=img1, caption=f"🎲 <b>{player_name}</b> 1. zar: {dice1}", parse_mode="HTML")
        await query.message.reply_photo(photo=img2, caption=f"🎲 <b>{player_name}</b> 2. zar: {dice2}\n━━━━━━━━━━━━━━━━━━━━━\n📊 Toplam: <b>{total}</b>", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Zar görseli hatası: {e}")
        await query.message.reply_text(f"🎲 <b>{player_name}</b> zarları attı!\n├─ 1. zar: {dice1}\n├─ 2. zar: {dice2}\n└─ Toplam: <b>{total}</b>", parse_mode="HTML")
    
    game["current_player_index"] += 1
    await _next_player_roll(ctx, chat_id, game_id)
    
    try:
        await query.message.delete()
    except:
        pass


async def _calculate_dice_results(ctx, chat_id, game_id):
    """Tüm atışlar bitti, kazananları hesapla"""
    game = await get_active_game(chat_id, "dice")
    if not game or game["game_id"] != game_id:
        return
    
    parts = game["participants_data"]
    rolled = game["players_rolled"]
    pool = game["pool"]
    
    max_score = max(rolled.values())
    winners = [uid for uid, score in rolled.items() if score == max_score]
    share = pool // len(winners)
    
    lines = [
        f"🎲 <b>ZAR OYUNU SONUÇLARI</b>",
        f"━━━━━━━━━━━━━━━━━━━━━",
        f"💰 Toplam havuz: {format_amount(pool)}",
        f"🏆 En yüksek skor: <b>{max_score}</b>",
        f"👥 Kazanan sayısı: {len(winners)}",
        f"━━━━━━━━━━━━━━━━━━━━━",
        ""
    ]
    
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
#  ÇARKIFELEK (Aynı kalacak)
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
        f"❌ Pass (x5) | 2x | 3x | 5x | 10x | 50x",
        parse_mode="HTML")
    game = await create_game(chat_id, "wheel", msg.message_id)
    asyncio.create_task(_wheel_timer(ctx, chat_id, game["game_id"]))


async def cmd_wheel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    if is_rate_limited(user.id): return
    if not ctx.args:
        await update.message.reply_text("❌ Kullanım: /wheel &lt;miktar&gt;")
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
        f"🎡 <b>{user.full_name}</b> — {format_amount(amount)} bahis!\n💳 {format_amount(bal)}",
        parse_mode="HTML")

@safe_game("ÇARKIFELEK")
async def _wheel_timer(ctx, chat_id, game_id):
    # Normal oyun kodu
    await asyncio.sleep(BET_WINDOW)
    game = await get_active_game(chat_id, "wheel")
    if not game or game["game_id"] != game_id: return
    game["state"] = "CALCULATING"
    
    import secrets
    label, mult = secrets.choice(WHEEL_SEGMENTS)  # Bu satır değişti
    
    parts = await get_participants(chat_id, game_id)
    # ... devam eden kod aynı ...
    lines = [f"🎡 <b>ÇARK DÖNDÜ!</b>", f"━━━━━━━━━━━━━━━━━━━━━",
             f"🎯 Sonuç: <b>{label}</b>", f"🆔 <code>{game_id}</code>", ""]
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
            lines.append(f"  ✅ {d['bet_data']['name']} +{format_amount(payout - d['bet'])}")
    await ctx.bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")
    await finish_game(chat_id, game_id, label)
    await cleanup(chat_id)


# ═══════════════════════════════════════════════════════════════
#  KAZI KAZAN - GÖRSELLİ VERSİYON (Solo + Turnuva)
# ═══════════════════════════════════════════════════════════════

import os
import asyncio
import secrets
import io
from collections import Counter
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


# Görseller ana klasörde olduğu için doğrudan dosya adı
ACIK_KART_PATH = "acik.jpg"
KAPALI_KART_PATH = "Kapali.jpg"

def create_scratch_result_image(board: list, winner_mult: int) -> io.BytesIO:
    if not os.path.exists(ACIK_KART_PATH):
        raise Exception(f"Açık kart görseli bulunamadı: {ACIK_KART_PATH}")
    
    img = Image.open(ACIK_KART_PATH)
    draw = ImageDraw.Draw(img)
    
    # Render'da VAR olan font yolları
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    
    font = None
    font_size = 160
    
    for path in font_paths:
        try:
            font = ImageFont.truetype(path, font_size)
            print(f"✅ Font yüklendi: {path}")
            break
        except:
            continue
    
    if font is None:
        print("⚠️ Font bulunamadı, default kullanılıyor")
        font = ImageFont.load_default()
    
    # ============ DEVAMI (BURADAN İTİBAREN EKLEDİM) ============
    
    # Kazanç yazısı
    text = f"{winner_mult} KAT"
    
    # Yazıyı ortala
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (img.width - w) // 2
    y = (img.height - h) // 2
    
    # Yazıyı çiz
    draw.text((x, y), text, fill="gold", font=font)
    
    # Resmi byte'a çevir
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return img_byte_arr
    
    
    # KUTU KOORDİNATLARI (image_4.png için)
    boxes = [
        {"center": (170, 200), "index": 0},
        {"center": (550, 200), "index": 1},
        {"center": (900, 200), "index": 2},
        {"center": (170, 550), "index": 3},
        {"center": (550, 550), "index": 4},
        {"center": (900, 550), "index": 5},
    ]
    
    for box in boxes:
        center_x, center_y = box["center"]
        value = board[box["index"]]
        
        # 🎨 RENK DÜZENLEMESİ
        if value == winner_mult and winner_mult > 0:
            text_color = (0, 255, 0)      # Yeşil (kazanan)
        elif value == 0:
            text_color = (255, 0, 0)      # Kırmızı (0x)
        else:
            text_color = (0, 0, 0)        # Siyah (diğerleri)
        
        # 📝 METİN DÜZENLEMESİ
        text = f"{value}x"  # 0x de yazılacak, ❌ kalktı
        
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        text_x = center_x - text_width / 2
        text_y = center_y - text_height / 2
        
        draw.text((text_x, text_y), text, fill=text_color, font=font)
    
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    return bio


async def cmd_kazisolo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Tek kişilik Kazı Kazan - Görselli versiyon"""
    user = update.effective_user
    
    if is_rate_limited(user.id):
        return
    
    if not ctx.args:
        await update.message.reply_text(
            "🎟 <b>KAZI KAZAN (SOLO)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "📌 Kullanım: <code>/kazisolo &lt;miktar&gt;</code>\n"
            "veya <code>/kazisolo allin</code>\n\n"
            "🏆 Çarpanlar: 2x, 3x, 5x, 10x, 25x, 50x\n"
            "🎯 Kazanma Oranı: %80\n"
            "💡 3 aynı çarpan = kazanç!",
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
    
    # Kapalı kartı gönder
    if os.path.exists(KAPALI_KART_PATH):
        with open(KAPALI_KART_PATH, "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=f"🎟 <b>KAZI KAZAN (SOLO)</b>\n━━━━━━━━━━━━━━━━━━━━━\n💰 Bahis: {format_amount(amount)}\n✨ KAZIYORSUN... ✨",
                parse_mode="HTML"
            )
    else:
        await update.message.reply_text(f"❌ Kapalı kart görseli bulunamadı: {KAPALI_KART_PATH}")
        return
    
    await asyncio.sleep(1)
    
    # Kartı oluştur
    board = [SCRATCH_POOL[secrets.randbelow(len(SCRATCH_POOL))] for _ in range(6)]
    counts = Counter(board)
    
    # Kazanan çarpanı bul
    winner_mult = 0
    match = 0
    for mult, cnt in counts.most_common():
        if cnt >= 3 and mult > 0:
            winner_mult = mult
            match = cnt
            break
    
    # Sonuç görselini oluştur
    try:
        result_img = create_scratch_result_image(board, winner_mult)
    except Exception as e:
        await update.message.reply_text(f"❌ Sonuç görseli oluşturulamadı: {e}")
        return
    
    if winner_mult > 0:
        payout = amount * winner_mult
        await add_balance(user.id, payout, "win", f"Kazı Kazan solo ({winner_mult}x)")
        await update_stats(user.id, payout)
        new_bal = await get_balance(user.id)
        
        await update.message.reply_photo(
            photo=result_img,
            caption=f"🎟 <b>KAZI KAZAN (SOLO)</b>\n━━━━━━━━━━━━━━━━━━━━━\n✅ {match} tane {winner_mult}x bulundu! ({winner_mult}x)\n🎉 KAZANDIN! +{format_amount(payout - amount)}\n💳 Yeni bakiye: {format_amount(new_bal)}",
            parse_mode="HTML"
        )
    else:
        await update_stats(user.id, 0)
        new_bal = await get_balance(user.id)
        
        await update.message.reply_photo(
            photo=result_img,
            caption=f"🎟 <b>KAZI KAZAN (SOLO)</b>\n━━━━━━━━━━━━━━━━━━━━━\n❌ 3 eşleşme yok! KAYBETTİN!\n💰 Kayıp: -{format_amount(amount)}\n💳 Yeni bakiye: {format_amount(new_bal)}",
            parse_mode="HTML"
        )


async def cmd_kazibet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Kazı Kazan turnuvası başlat (PvP)"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    if is_rate_limited(user.id):
        return
    
    ok, err = await can_open_game(chat_id, "scratch_tournament")
    if not ok:
        await update.message.reply_text(f"❌ {err}")
        return
    
    # Kapalı kart görseli ile başlat
    if os.path.exists(KAPALI_KART_PATH):
        with open(KAPALI_KART_PATH, "rb") as photo:
            msg = await update.message.reply_photo(
                photo=photo,
                caption=f"🎟 <b>KAZI KAZAN TURNUVASI BAŞLADI!</b>\n━━━━━━━━━━━━━━━━━━━━━\n⏱ <b>{BET_WINDOW} saniye</b> içinde katılın!\n\n📌 /kazi &lt;miktar&gt; veya /kazi allin\n\n🎯 Herkes AYNI kartı kazır!\n✅ 3 eşleşme = HERKES KAZANIR\n❌ 3 eşleşme yok = HERKES KAYBEDER",
                parse_mode="HTML"
            )
    else:
        msg = await update.message.reply_text(
            f"🎟 <b>KAZI KAZAN TURNUVASI BAŞLADI!</b>\n━━━━━━━━━━━━━━━━━━━━━\n⏱ <b>{BET_WINDOW} saniye</b> içinde katılın!\n\n📌 /kazi &lt;miktar&gt; veya /kazi allin\n\n🎯 Herkes AYNI kartı kazır!\n✅ 3 eşleşme = HERKES KAZANIR\n❌ 3 eşleşme yok = HERKES KAYBEDER",
            parse_mode="HTML"
        )
    
    game = await create_game(chat_id, "scratch_tournament", msg.message_id)
    game["min_bet"] = 0
    game["pool"] = 0
    game["players"] = {}
    game["start_time"] = time.time()
    
    asyncio.create_task(_scratch_countdown(ctx, chat_id, game["game_id"], msg.message_id))
    asyncio.create_task(_scratch_tournament_timer(ctx, chat_id, game["game_id"]))


async def cmd_kazi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Kazı Kazan turnuvasına katıl"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    if is_rate_limited(user.id):
        return
    
    if not ctx.args:
        await update.message.reply_text(
            "🎟 <b>KAZI KAZAN TURNUVASI</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "📌 Kullanım: <code>/kazi &lt;miktar&gt;</code>\n"
            "veya <code>/kazi allin</code>\n\n"
            "💡 Örnek: <code>/kazi 1000</code>",
            parse_mode="HTML")
        return
    
    game = await get_active_game(chat_id, "scratch_tournament")
    if not game or game["state"] != "OPEN":
        await update.message.reply_text("❌ Açık Kazı Kazan turnuvası yok! /kazibet ile başlatın.")
        return
    
    await get_or_create_user(user.id, user.username, user.full_name)
    bal = await get_balance(user.id)
    amount, err = parse_amount(ctx.args[0], bal)
    if err:
        await update.message.reply_text(f"❌ {err}")
        return
    
    if not game.get("players"):
        game["min_bet"] = amount
    elif amount < game.get("min_bet", 0):
        await update.message.reply_text(f"❌ En az {format_amount(game['min_bet'])} gerekli.")
        return
    
    ok = await remove_balance(user.id, amount, "bet", f"Kazı Kazan turnuvası")
    if not ok:
        await update.message.reply_text("❌ Yetersiz bakiye.")
        return
    
    if user.id in game["players"]:
        game["players"][user.id]["bet"] += amount
    else:
        game["players"][user.id] = {"bet": amount, "name": user.full_name}
    
    game["pool"] += amount
    
    await update.message.reply_text(
        f"🕹 <b>{user.full_name}</b> 🎟️ {format_amount(amount)}🪙 bahis yaptı",
        parse_mode="HTML"
    )


async def _scratch_countdown(ctx, chat_id, game_id, message_id):
    """Her 5 saniyede bir süre bildirimi gönder"""
    for remaining in range(BET_WINDOW, 0, -5):
        await asyncio.sleep(5)
        
        game = await get_active_game(chat_id, "scratch_tournament")
        if not game or game["game_id"] != game_id:
            return
        
        if game["state"] != "OPEN":
            return
        
        players_count = len(game.get("players", {}))
        pool = game.get("pool", 0)
        
        try:
            await ctx.bot.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=f"🎟 <b>KAZI KAZAN TURNUVASI</b>\n━━━━━━━━━━━━━━━━━━━━━\n⏱ Kalan süre: <b>{remaining} saniye</b>\n👥 Katılımcı: <b>{players_count}</b> kişi\n💰 Toplam havuz: <b>{format_amount(pool)}</b>\n\n📌 /kazi &lt;miktar&gt; ile katılın!",
                parse_mode="HTML"
            )
        except:
            pass


async def _scratch_tournament_timer(ctx, chat_id, game_id):
    """Bahis süresi bitince kazı kazan oyna"""
    await asyncio.sleep(BET_WINDOW)
    
    game = await get_active_game(chat_id, "scratch_tournament")
    if not game or game["game_id"] != game_id:
        return
    
    players = game.get("players", {})
    
    if len(players) < 2:
        await ctx.bot.send_message(
            chat_id,
            "❌ <b>KAZI KAZAN TURNUVASI İPTAL!</b>\n━━━━━━━━━━━━━━━━━━━━━\nEn az 2 oyuncu gerekli.\nBahisler iade edildi.",
            parse_mode="HTML")
        for uid, data in players.items():
            await add_balance(uid, data["bet"], "refund", f"Kazı Kazan iade")
        await finish_game(chat_id, game_id, "iptal")
        await cleanup(chat_id)
        return
    
    game["state"] = "CALCULATING"
    
    # KARTI OLUŞTUR (HERKES İÇİN AYNI)
    board = [SCRATCH_POOL[secrets.randbelow(len(SCRATCH_POOL))] for _ in range(6)]
    counts = Counter(board)
    
    winner_mult = 0
    match = 0
    for mult, cnt in counts.most_common():
        if cnt >= 3 and mult > 0:
            winner_mult = mult
            match = cnt
            break
    
    pool = game["pool"]
    players_data = game["players"]
    
    # Sonuç görselini oluştur
    try:
        result_img = create_scratch_result_image(board, winner_mult)
    except Exception as e:
        await ctx.bot.send_message(chat_id, f"❌ Sonuç görseli hatası: {e}")
        return
    
    lines = [f"🎟 <b>KAZI KAZAN TURNUVASI SONUCU</b>"]
    
    if winner_mult > 0:
        total_payout = 0
        lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"✅ {match} tane {winner_mult}x bulundu! ({winner_mult}x)")
        lines.append(f"🎉 <b>HERKES KAZANDI!</b> 🎉")
        lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        for uid, data in players_data.items():
            payout = data["bet"] * winner_mult
            await add_balance(uid, payout, "win", f"Kazı Kazan turnuvası ({winner_mult}x)")
            await update_stats(uid, payout)
            total_payout += payout
            lines.append(f"✅ {data['name']}: {format_amount(data['bet'])} → {format_amount(payout)} (+{format_amount(payout - data['bet'])})")
        
        lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"💰 Toplam dağıtılan: {format_amount(total_payout)}")
        
    else:
        lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"❌ <b>3 EŞLEŞME YOK!</b>")
        lines.append(f"😢 <b>HERKES KAYBETTİ!</b> 😢")
        lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        for uid, data in players_data.items():
            await update_stats(uid, 0)
            lines.append(f"❌ {data['name']}: -{format_amount(data['bet'])}")
    
    lines.append(f"\n🆔 <code>{game_id}</code>")
    
    await ctx.bot.send_photo(
        chat_id,
        photo=result_img,
        caption="\n".join(lines),
        parse_mode="HTML"
    )
    
    await finish_game(chat_id, game_id, "kazikazan")
    await cleanup(chat_id)

# ═══════════════════════════════════════════════════════════════
#  BLACKJACK - BASİT VE ÇALIŞAN VERSİYON
# ═══════════════════════════════════════════════════════════════

import os
import random
import asyncio
import io
from typing import Dict, List, Tuple
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes

RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["♠️", "♥️", "♦️", "♣️"]
BJ_IMG_PATH = ""  # ✅ TELEFON YOLU SİLİNDİ, ANA KLASÖR
CARD_WIDTH = 60
CARD_HEIGHT = 84
_bj: Dict[int, dict] = {}


def get_card_image(card: tuple) -> Image.Image:
    rank, suit = card
    rank_map = {"A": "ace", "2": "2", "3": "3", "4": "4", "5": "5", "6": "6", "7": "7", "8": "8", "9": "9", "10": "10", "J": "jack", "Q": "queen", "K": "king"}
    suit_map = {"♠️": "spades", "♥️": "hearts", "♦️": "diamonds", "♣️": "clubs"}
    filename = f"{rank_map.get(rank, rank)}_of_{suit_map.get(suit, 'spades')}.png"
    img_path = filename  # ✅ Doğrudan dosya adı
    
    if os.path.exists(img_path):
        img = Image.open(img_path)
        img = img.resize((CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS)
        return img
    return Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), color='#2c2c2c')


def get_face_down_card() -> Image.Image:
    back_path = "back.png"  # ✅ Telefon yolu silindi
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


def _bj_kb(game_id: str):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🃏 Hit", callback_data=f"bj_hit:{game_id}"),
        InlineKeyboardButton("✋ Stand", callback_data=f"bj_stand:{game_id}"),
    ]])


async def cmd_blackjack(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if is_rate_limited(user.id):
        return
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
    """Bahis süresi bitince oyunu başlat"""
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
    
    for uid in bj["order"]:
        bj["players"][uid]["hand"] = [deck.pop(), deck.pop()]
        bj["players"][uid]["state"] = "PLAYING"
    
    bj["dealer"] = [deck.pop(), deck.pop()]
    bj["current"] = 0
    
    # KURPİYER GÖNDER
    dealer_img = combine_cards_with_hidden(bj["dealer"])
    first_card_value = _card_val(bj["dealer"][0][0])
    await ctx.bot.send_photo(
        chat_id, 
        photo=dealer_img, 
        caption=f"🎩 KURPİYER\n━━━━━━━━━━━━━━━━━━━━━\nAçık kart: {first_card_value}\nKapalı kart: ?", 
        parse_mode="HTML"
    )
    
    # OYUNCULARIN KARTLARINI GÖNDER
    for uid in bj["order"]:
        p = bj["players"][uid]
        hand_img = combine_cards(p["hand"])
        await ctx.bot.send_photo(
            chat_id,
            photo=hand_img,
            caption=f"🃏 <b>{p['name']}</b>\n━━━━━━━━━━━━━━━━━━━━━\n🃏 Eliniz: {_hand_val(p['hand'])}",
            parse_mode="HTML"
        )
    
    await _bj_next(ctx, chat_id, game_id)


async def _bj_next(ctx, chat_id, game_id):
    bj = _bj.get(chat_id)  # ← EKLENMESİ GEREKEN SATIR
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
    if val == 21:
        p["state"] = "STAND"
        bj["current"] += 1
        await _bj_next(ctx, chat_id, game_id)
        return
    hand_img = combine_cards(p["hand"])
    await ctx.bot.send_photo(
        chat_id, photo=hand_img,
        caption=f"🃏 {p['name']} sırası!\n━━━━━━━━━━━━━━━━━━━━━\n🃏 Eliniz: {val}\n\n⏱ {BLACKJACK_TURN} saniyen var!",
        reply_markup=_bj_kb(game_id), parse_mode="HTML"
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
            p["state"] = "BUST"
            await query.edit_message_media(media=InputMediaPhoto(media=hand_img, caption=f"💥 BUST!\n━━━━━━━━━━━━━━━━━━━━━\nOyuncu: {p['name']}\nEliniz: {val}\n❌ Kaybettiniz!"))
            bj["current"] += 1
            await _bj_next(ctx, chat_id, game_id)
        elif val == 21:
            p["state"] = "STAND"
            await query.edit_message_media(media=InputMediaPhoto(media=hand_img, caption=f"🎉 BLACKJACK! 21\n━━━━━━━━━━━━━━━━━━━━━\nOyuncu: {p['name']}\n✅ Otomatik Stand"))
            bj["current"] += 1
            await _bj_next(ctx, chat_id, game_id)
        else:
            await query.edit_message_media(media=InputMediaPhoto(media=hand_img, caption=f"🃏 SIRA SENDE\n━━━━━━━━━━━━━━━━━━━━━\nOyuncu: {p['name']}\nEliniz: {val}\n⏳ {BLACKJACK_TURN} saniyen var!"), reply_markup=_bj_kb(game_id))
            p["task"] = asyncio.create_task(_bj_timeout(ctx, chat_id, game_id, user.id))
            
    elif action == "bj_stand":
        hand_val = _hand_val(p["hand"])
        p["state"] = "STAND"
        bj["current"] += 1
        await query.edit_message_media(media=InputMediaPhoto(media=combine_cards(p["hand"]), caption=f"✋ STAND\n━━━━━━━━━━━━━━━━━━━━━\nOyuncu: {p['name']}\nEliniz: {hand_val} ile durdu."))
        await _bj_next(ctx, chat_id, game_id)



async def _bj_dealer(ctx, chat_id, game_id):
    bj = _bj.get(chat_id)  # ← BUNU EKLE
    if not bj or bj["game_id"] != game_id:
        return
    
    hand = bj["dealer"]
    while _hand_val(hand) < 17:
        hand.append(bj["deck"].pop())
    dval = _hand_val(hand)
    
    dealer_img = combine_cards(hand)
    first_card_value = _card_val(hand[0][0])
    second_card_value = _card_val(hand[1][0]) if len(hand) > 1 else 0
    await ctx.bot.send_photo(
        chat_id, 
        photo=dealer_img, 
        caption=f"🎩 KURPİYER\n━━━━━━━━━━━━━━━━━━━━━\nAçık kart: {first_card_value}\nKapalı kart: {second_card_value}\n📊 Toplam: {dval}", 
        parse_mode="HTML"
    )
    
    # Sonuçları ayır
    kazananlar = []
    kaybedenler = []
    beraberlikler = []
    total_payout = 0
    
    for uid in bj["order"]:
        p = bj["players"][uid]
        pval = _hand_val(p["hand"])
        bet = p["bet"]
        
        if p["state"] == "BUST":
            kaybedenler.append(f" ❌ {p['name']} 🃏 BUST → -{format_amount(bet)}")
        elif dval > 21:
            payout = bet * 2
            await add_balance(uid, payout, "win", f"BJ game:{game_id}")
            await update_stats(uid, payout)
            total_payout += payout
            kazananlar.append(f" ✅ {p['name']} 🃏 {pval} → +{format_amount(bet)}")
        elif pval > dval:
            payout = bet * 2
            await add_balance(uid, payout, "win", f"BJ game:{game_id}")
            await update_stats(uid, payout)
            total_payout += payout
            kazananlar.append(f" ✅ {p['name']} 🃏 {pval} → +{format_amount(bet)}")
        elif pval == dval:
            await add_balance(uid, bet, "refund", f"BJ iade game:{game_id}")
            beraberlikler.append(f" 🤝 {p['name']} 🃏 {pval} → İADE")
        else:
            kaybedenler.append(f" ❌ {p['name']} 🃏 {pval} → -{format_amount(bet)}")
    
    # Sonuç mesajını oluştur
    result_text = f"🆔 GAME ID: <code>{game_id}</code>\n\n"
    result_text += f"🏆 KURPİYER 🔘 {dval}\n\n"
    result_text += f"🏧 SONUÇLAR 🔘\n\n"
    
    for k in kazananlar:
        result_text += f"{k}\n"
    for k in kaybedenler:
        result_text += f"{k}\n"
    for b in beraberlikler:
        result_text += f"{b}\n"
    
    result_text += f"\n━━━━━━━━━━━━━━━━━━━━━\n"
    result_text += f"💰 Toplam Dağıtılan: {format_amount(total_payout)} 🪙"
    
    await ctx.bot.send_message(chat_id, result_text, parse_mode="HTML")
    
    del _bj[chat_id]
    await finish_game(chat_id, game_id, f"dealer:{dval}")
    await cleanup(chat_id)
    


# ═══════════════════════════════════════════════════════════════
#  GÜNLÜK BONUS (DÜZELTİLMİŞ)
# ═══════════════════════════════════════════════════════════════

def get_daily_bonus(streak: int) -> int:
    """
    Günlük bonus miktarını hesaplar
    Streak: Kaç gündür kesintisiz alıyor
    """
    if streak < 0:
        streak = 0
    # Maksimum 10 günlük seri (50.000 * 1024 = 51.2M)
    streak = min(streak, 10)
    return 50000 * (2 ** streak)


def can_claim_daily(last_daily: str) -> tuple[bool, int]:
    """
    Bonus alınıp alınamayacağını kontrol eder
    Returns: (alabilir mi, beklenecek saat)
    """
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
    """Günlük bonus komutu"""
    user = update.effective_user
    
    if is_rate_limited(user.id):
        return
    
    # Kullanıcıyı al/güncelle
    u = await get_or_create_user(user.id, user.username, user.full_name)
    
    db = await get_db()
    lock = await _get_lock(user.id)
    
    async with lock:
        # Son bonus tarihini kontrol et
        async with db.execute("SELECT last_daily, daily_streak FROM users WHERE telegram_id=?", (user.id,)) as c:
            row = await c.fetchone()
        
        last_daily = row["last_daily"]
        current_streak = row["daily_streak"] or 0
        
        can_claim, hours_left = can_claim_daily(last_daily)
        
        if not can_claim:
            await update.message.reply_text(
                f"⏰ <b>Günlük bonusunuzu zaten aldınız!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎁 Sonraki bonus: <b>{hours_left} saat</b> sonra\n"
                f"📈 Mevcut seri: <b>{current_streak} gün</b>\n\n"
                f"💡 Her gün düzenli alırsan bonus katlanır!",
                parse_mode="HTML"
            )
            return
        
        # Yeni streak hesapla
        new_streak = current_streak + 1
        
        # Bonus miktarını hesapla
        bonus_amount = get_daily_bonus(current_streak)
        
        # Bakiyeyi güncelle
        await db.execute(
            "UPDATE users SET balance = balance + ?, last_daily = datetime('now'), daily_streak = ?, updated_at = datetime('now') WHERE telegram_id = ?",
            (bonus_amount, new_streak, user.id)
        )
        
        # İşlem kaydı
        await db.execute(
            "INSERT INTO transactions (to_id, amount, type, description) VALUES (?, ?, 'daily', ?)",
            (user.id, bonus_amount, f"{new_streak}. gün bonusu")
        )
        await db.commit()
        
        # Yeni bakiyeyi al
        new_balance = await get_balance(user.id)
        
        # Sonraki bonus tahmini
        next_bonus = get_daily_bonus(new_streak)
        
        await update.message.reply_text(
            f"🎁 <b>GÜNLÜK BONUS!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>{user.full_name}</b>\n"
            f"📅 Seri: <b>{new_streak}</b> gün\n"
            f"💰 Kazanılan: <b>+{format_amount(bonus_amount)}</b>\n"
            f"💳 Yeni bakiye: <b>{format_amount(new_balance)}</b>\n\n"
            f"🎯 Yarınki bonus: <b>{format_amount(next_bonus)}</b>\n"
            f"📌 Her gün /daily yaparak katlamaya devam et!",
            parse_mode="HTML"
        )
        
        logger.info(f"Günlük bonus: {user.id} - {new_streak}. gün, {bonus_amount} kazandı")
 # ═══════════════════════════════════════════════════════════════
#  BUTONLU MENÜ SİSTEMİ
# ═══════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════
#  BUTONLU MENÜ SİSTEMİ
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
            InlineKeyboardButton("❓ YARDIM", callback_data="menu_help"),
            InlineKeyboardButton("🏠 ANA MENÜ", callback_data="menu_main")
        ]
    ]
    
    await update.message.reply_text(
        f"🎮 <b>CASİNİBOT ANA MENÜ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {user.full_name}\n"
        f"💰 Bakiyeniz: {format_amount(bal)}\n\n"
        f"Aşağıdaki butonlardan bir oyun seçin:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
async def menu_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Menü butonları için callback handler"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    data = query.data
    chat_id = query.message.chat_id
    message_id = query.message.message_id
    
    if data == "menu_roulette":
        # Rulet başlat
        await query.edit_message_text("🎰 Rulet başlatılıyor...")
        # Yeni bir update oluştur
        class FakeMessage:
            def __init__(self, chat_id, message_id):
                self.chat_id = chat_id
                self.message_id = message_id
                self.reply_text = query.message.reply_text
        
        class FakeUpdate:
            def __init__(self, chat_id, message_id, user):
                self.effective_chat = type('obj', (object,), {'id': chat_id})
                self.effective_user = user
                self.message = type('obj', (object,), {
                    'chat_id': chat_id,
                    'reply_text': query.message.reply_text,
                    'message_id': message_id
                })
        
        fake_update = FakeUpdate(chat_id, message_id, user)
        await cmd_rulet(fake_update, ctx)
        await query.delete_message()
        
    elif data == "menu_blackjack":
        await query.edit_message_text("🃏 Blackjack başlatılıyor...")
        class FakeMessage:
            def __init__(self, chat_id, message_id):
                self.chat_id = chat_id
                self.message_id = message_id
                self.reply_text = query.message.reply_text
        
        class FakeUpdate:
            def __init__(self, chat_id, message_id, user):
                self.effective_chat = type('obj', (object,), {'id': chat_id})
                self.effective_user = user
                self.message = type('obj', (object,), {
                    'chat_id': chat_id,
                    'reply_text': query.message.reply_text,
                    'message_id': message_id
                })
        
        fake_update = FakeUpdate(chat_id, message_id, user)
        await cmd_blackjack(fake_update, ctx)
        await query.delete_message()
        
    elif data == "menu_dice":
        await query.edit_message_text("🎲 Zar oyunu başlatılıyor...")
        class FakeUpdate:
            def __init__(self, chat_id, message_id, user):
                self.effective_chat = type('obj', (object,), {'id': chat_id})
                self.effective_user = user
                self.message = type('obj', (object,), {
                    'chat_id': chat_id,
                    'reply_text': query.message.reply_text,
                    'message_id': message_id
                })
        
        fake_update = FakeUpdate(chat_id, message_id, user)
        await cmd_dicebet(fake_update, ctx)
        await query.delete_message()
        
    elif data == "menu_wheel":
        await query.edit_message_text("🎡 Çarkıfelek başlatılıyor...")
        class FakeUpdate:
            def __init__(self, chat_id, message_id, user):
                self.effective_chat = type('obj', (object,), {'id': chat_id})
                self.effective_user = user
                self.message = type('obj', (object,), {
                    'chat_id': chat_id,
                    'reply_text': query.message.reply_text,
                    'message_id': message_id
                })
        
        fake_update = FakeUpdate(chat_id, message_id, user)
        await cmd_wheelbet(fake_update, ctx)
        await query.delete_message()
        
    elif data == "menu_scratch":
        # Kazı kazan için bilgi mesajı
        keyboard = [[InlineKeyboardButton("◀️ ANA MENÜ", callback_data="menu_main")]]
        await query.edit_message_text(
            "🎟 <b>KAZI KAZAN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "6 kutu — 3 aynı çarpan kazanır!\n\n"
            "📌 <code>/kazi &lt;miktar&gt;</code> veya <code>/kazi allin</code>\n\n"
            "💎 50x  |  🏆 20x\n"
            "⭐ 10x  |  🍀 5x\n"
            "🍋 3x   |  🍒 2x\n\n"
            "💡 Örnek: <code>/kazi 1000</code>\n\n"
            "⬅️ Ana menüye dönmek için butona tıklayın.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        
    elif data == "menu_balance":
        # Bakiye göster
        u = await get_user(user.id)
        if u:
            lvl, emoji = get_level(u["balance"])
            keyboard = [[InlineKeyboardButton("◀️ ANA MENÜ", callback_data="menu_main")]]
            await query.edit_message_text(
                f"💳 <b>{user.full_name}</b> [{lvl}] {emoji}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 Bakiye: <b>{format_amount(u['balance'])}</b>\n"
                f"🎮 Oynanan: {u['games_played']}\n"
                f"📊 Toplam bahis: {format_amount(u['total_wagered'])}\n"
                f"🏆 Toplam kazanç: {format_amount(u['total_won'])}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
        else:
            await query.edit_message_text("❌ Kullanıcı bulunamadı.")
            
    elif data == "menu_leaderboard":
        # Liderlik tablosu
        rows = await get_leaderboard(LEADERBOARD_SIZE)
        medals = ["🥇", "🥈", "🥉"]
        lines = ["🏆 <b>LİDERLİK TABLOSU</b>", "━━━━━━━━━━━━━━━━━━━━━"]
        for i, r in enumerate(rows):
            lvl, emoji = get_level(r["balance"])
            medal = medals[i] if i < 3 else f"{i+1}."
            lines.append(f"{medal} {r['display_name'][:15]} [{lvl}]{emoji} — {format_amount(r['balance'])}")
        
        keyboard = [[InlineKeyboardButton("◀️ ANA MENÜ", callback_data="menu_main")]]
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        
    elif data == "menu_daily":
        # Günlük bonus al - direkt komut çalıştır
        await query.edit_message_text("🎁 Günlük bonus alınıyor...")
        class FakeUpdate:
            def __init__(self, user, chat_id, message_id):
                self.effective_user = user
                self.effective_chat = type('obj', (object,), {'id': chat_id})
                self.message = type('obj', (object,), {
                    'chat_id': chat_id,
                    'reply_text': query.message.reply_text,
                    'message_id': message_id
                })
        
        fake_update = FakeUpdate(user, chat_id, message_id)
        await cmd_daily(fake_update, ctx)
        await query.delete_message()
        
    elif data == "menu_help":
        # Yardım
        keyboard = [[InlineKeyboardButton("◀️ ANA MENÜ", callback_data="menu_main")]]
        await query.edit_message_text(
            "🎰 <b>CASİNİBOT KOMUTLAR</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👤 <b>HESAP</b>\n"
            "• /start — Kayıt / Hoş geldin\n"
            "• /balance — Bakiyeni göster\n"
            "• /changename — İsim değiştir\n"
            "• /leaderboard — İlk 15 oyuncu\n"
            "• /moneys — Para gönder\n"
            "• /daily — Günlük bonus\n\n"
            "🎡 <b>RULET</b>\n"
            "• /rulet — Rulet başlat\n"
            "• /red &lt;miktar&gt;\n"
            "• /black &lt;miktar&gt;\n"
            "• /green &lt;miktar&gt;\n"
            "• /number &lt;sayı&gt; &lt;miktar&gt;\n"
            "• /numbers &lt;1,2,3&gt; &lt;miktar&gt;\n\n"
            "🎲 <b>ZAR (PvP)</b>\n"
            "• /dicebet — Başlat\n"
            "• /dice &lt;miktar&gt; — Katıl\n\n"
            "🎡 <b>ÇARKIFELEK</b>\n"
            "• /wheelbet — Başlat\n"
            "• /wheel &lt;miktar&gt; — Bahis\n\n"
            "🎟 <b>KAZI KAZAN</b>\n"
            "• /kazi &lt;miktar&gt; — Oyna\n\n"
            "🃏 <b>BLACKJACK</b>\n"
            "• /blackjack — Başlat\n"
            "• /bj &lt;miktar&gt; — Bahis\n\n"
            "💡 <b>İPUCU</b>\n"
            "Miktar yerine <code>allin</code> yazarak tüm bakiyeni yatırabilirsin!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        
    elif data == "menu_main":
        # Ana menüyü tekrar göster
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
                InlineKeyboardButton("❓ YARDIM", callback_data="menu_help"),
                InlineKeyboardButton("🏠 ANA MENÜ", callback_data="menu_main")
            ]
        ]
        await query.edit_message_text(
            f"🎮 <b>CASİNİBOT ANA MENÜ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {user.full_name}\n"
            f"💰 Bakiyeniz: {format_amount(bal)}\n\n"
            f"Aşağıdaki butonlardan bir oyun seçin:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )


# ═══════════════════════════════════════════════════════════════
#  ANA FONKSIYON
# ═══════════════════════════════════════════════════════════════
async def post_init(app):
    await init_db()
    # backup_task'i KALDIRDIK, sadece veritabanını başlat
    logger.info("🎰 CasiniBot başlatıldı!")

async def post_shutdown(app):
    global _db
    if _db:
        await _db.close()
    logger.info("CasiniBot kapatıldı.")


def main():
    if BOT_TOKEN == "7640572418:AAHhT1uzlpeNlTr7_sP2yJ3_6GNJ6Ph6JDs":
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
    app.add_handler(CommandHandler("id", cmd_id))
    
    # 🔥 BLACKJACK CALLBACK
    app.add_handler(CallbackQueryHandler(bj_callback, pattern=r"^bj_(hit|stand):"))
    
    # 🔥 MENÜ CALLBACK
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu_"))
    
    # Genel komutlar
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("moneys", cmd_moneys))
    app.add_handler(CommandHandler("changename", cmd_changename))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("daily", cmd_daily))
    app.add_handler(CommandHandler("menu", cmd_menu))
    
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
    app.add_handler(CallbackQueryHandler(dice_roll_callback, pattern=r"^dice_roll:"))
    
    # Çark
    app.add_handler(CommandHandler("wheelbet", cmd_wheelbet))
    app.add_handler(CommandHandler("wheel", cmd_wheel))
    
    # Kazı Kazan
    app.add_handler(CommandHandler("kazisolo", cmd_kazisolo))  # Solo
    app.add_handler(CommandHandler("kazibet", cmd_kazibet))    # Turnuva başlat
    app.add_handler(CommandHandler("kazi", cmd_kazi))          # Turnuvaya katıl
    
    # Blackjack
    app.add_handler(CommandHandler("blackjack", cmd_blackjack))
    app.add_handler(CommandHandler("bj", cmd_bj))
    
    logger.info("Handler'lar yüklendi. Polling başlıyor...")
    app.run_polling(drop_pending_updates=True, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()

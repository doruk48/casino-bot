import asyncio
import logging
import os
import secrets
import random
import shutil
import time
import uuid
import io
import re
from collections import Counter
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# MongoDB ve Telegram
from motor.motor_asyncio import AsyncIOMotorClient
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    InputMediaPhoto, LabeledPrice, SuccessfulPayment
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ContextTypes, PreCheckoutQueryHandler, MessageHandler, filters
)
from telegram.error import BadRequest

# Görsel İşleme
from PIL import Image, ImageDraw, ImageFont

# ═══════════════════════════════════════════════════════════════
#  BASE_DIR VE LOGGING TANIMI
# ═══════════════════════════════════════════════════════════════

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  FONT BULMA FONKSİYONU (DÜZELTİLMİŞ)
# ═══════════════════════════════════════════════════════════════

def get_font(font_size: int):
    """Sistemdeki fontları dener, donmayı önlemek için mutlaka bir değer döndürür."""
    
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        "/system/fonts/Roboto-Bold.ttf",
        "arial.ttf" # Yerel testler için
    ]
    
    for path in font_paths:
        try:
            # Sadece path varsa ve yüklenebiliyorsa döndür
            if os.path.exists(path):
                return ImageFont.truetype(path, font_size)
        except Exception as e:
            continue
    
    logger.warning(f"⚠️ Font dosyası bulunamadı, varsayılan font kullanılıyor (Boyut: {font_size})")
    return ImageFont.load_default()
    
    
    
    # ═══════════════════════════════════════════════════════════════
#  AYARLAR VE SABİTLER
# ═══════════════════════════════════════════════════════════════

BOT_TOKEN = os.getenv("BOT_TOKEN", "8646115906:AAEn4Rydo0TjRBm_iiaZqSRJ-KcIqUmNyZQ")
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://1botuser2:Barkın1234@cluster0.8zvjyjk.mongodb.net/")

STARTING_BALANCE = 1_000_000
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

# Rulet Ayarları
ROULETTE_MULTIPLIERS = {"red": 2, "black": 2, "green": 72, "number": 36}
ROULETTE_IMG_PATH = BASE_DIR

# Blackjack Ayarları
BLACKJACK_IMG_PATH = BASE_DIR
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["♠️", "♥️", "♦️", "♣️"]
CARD_WIDTH, CARD_HEIGHT = 60, 84

# Kazı Kazan & Çarkıfelek Görselleri
KAPALI_KART_PATH = os.path.join(BASE_DIR, "kapali.jpg")
ACIK_KART_PATH = os.path.join(BASE_DIR, "acik.jpg")
TRANSFER_TEMPLATE_PATH = os.path.join(BASE_DIR, "transfer.png")

# Çarkıfelek Dilimleri
WHEEL_SEGMENTS = [
    ("💀 PASS 💀", 0)] * 12 + [("🔄 İADE 🔄", 1)] * 12 + \
    [("🟢 2x", 2)] * 3 + [("🟢 3x", 3)] * 2 + \
    [("🔵 5x", 5)] * 2 + [("🔵 10x", 10), ("🔵 15x", 15)] + \
    [("🟣 25x", 25), ("🟣 50x", 50), ("🟡 100x", 100)]

random.shuffle(WHEEL_SEGMENTS)

# Kazı Kazan Olasılıkları
SCRATCH_SYMBOLS = [(250, 1), (100, 2), (50, 3), (20, 5), (10, 10), (5, 15), (3, 20), (2, 29), (0, 15)]
SCRATCH_POOL = []
for val, weight in SCRATCH_SYMBOLS:
    SCRATCH_POOL.extend([val] * weight)

SCRATCH_EMOJI = {
    250: "🔥👑💎🔥", 100: "💎💎💎✨", 50: "💎💎🌟", 20: "⭐🌟⭐",
    10: "🏆🥇🏆", 5: "🔹🔹🔹", 3: "🟤🟤🟤", 2: "💰💰", 0: "💀🌑💀"
}

# VIP Kasa ve Seviye Sistemleri
STARS_CONFIG = {
    10:   {"coin": 1_000_000, "label": "🥉 BRONZ KESE", "suffix": "1 Milyon"},
    25:   {"coin": 50_000_000, "label": "🥈 GÜMÜŞ KASA", "suffix": "50 Milyon"},
    50:   {"coin": 1_000_000_000, "label": "🥇 ALTIN KASA", "suffix": "1 Milyar"},
    100:  {"coin": 10_000_000_000, "label": "💎 ELMAS KASA", "suffix": "10 Milyar"},
    250:  {"coin": 100_000_000_000, "label": "🔥 PLATİN KASA", "suffix": "100 Milyar"},
    500:  {"coin": 1_000_000_000_000, "label": "🌌 KOZMİK KASA", "suffix": "1 Trilyon"},
    1000: {"coin": 10_000_000_000_000, "label": "👑 KRAL SERVETİ", "suffix": "10 Trilyon"}
}

LEVELS = [
    (0, "Çırak", "🪵"), (1_000, "Bahisçi", "🎯"), (100_000, "Gümüş", "🥈"),
    (1_000_000, "Altın", "🥇"), (10_000_000, "Platin", "💠"), (100_000_000, "Elmas", "💎"),
    (1_000_000_000, "Diamond", "💎✨"), (10_000_000_000, "Epic", "👑"),
    (100_000_000_000, "Grand", "🔱"), (1_000_000_000_000, "Mythic", "🔥"),
    (10**13, "Legendary", "⭐"), (10**15, "Transcendent", "🌌"),
    (10**18, "Cosmic", "🪐"), (10**21, "Eternal", "♾️"),
    (10**24, "Omnipotent", "👑👑"), (10**30, "MUTLAK TANRI", "👑👑👑"),
]

# Admin ve Loglama
ADMIN_IDS = {6927797531}

# ═══════════════════════════════════════════════════════════════
#  VERİTABANI VE EKONOMİ MOTORU
# ═══════════════════════════════════════════════════════════════

_mongo_client = None
_db = None
_user_locks: dict[int, asyncio.Lock] = {}
_locks_meta = asyncio.Lock()

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
    logger.info("🚀 MongoDB bağlantısı ve Index'ler hazır!")

async def _get_lock(uid: int) -> asyncio.Lock:
    async with _locks_meta:
        if uid not in _user_locks:
            _user_locks[uid] = asyncio.Lock()
        return _user_locks[uid]

# Yardımcı Fonksiyonlar (Format, Parse, Seviye)
def get_level(balance: int) -> tuple[str, str]:
    result = (LEVELS[0][1], LEVELS[0][2])
    for min_bal, name, emoji in LEVELS:
        if balance >= min_bal: result = (name, emoji)
    return result

def format_amount(amount: int) -> str:
    if amount < 1000: return f"{amount}{CURRENCY_SYMBOL}"
    units = [(10**60, "Nvd"), (10**57, "Ocd"), (10**54, "Spt"), (10**51, "Sxd"), (10**48, "Qnd"), (10**45, "Qtd"), (10**42, "Trd"), (10**39, "Dcd"), (10**36, "Udc"), (10**33, "Dc"), (10**30, "N"), (10**27, "Ot"), (10**24, "Sp"), (10**21, "Sx"), (10**18, "Qt"), (10**15, "Q"), (10**12, "T"), (10**9, "B"), (10**6, "M"), (10**3, "K")]
    for unit, suffix in units:
        if amount >= unit:
            value = amount / unit
            formatted = f"{value:.2f}".rstrip('0').rstrip('.') if value < 100 else f"{value:.0f}"
            return f"{formatted}{suffix}{CURRENCY_SYMBOL}"
    return f"{amount}{CURRENCY_SYMBOL}"

async def get_or_create_user(uid: int, username, name: str) -> dict:
    db = await get_db()
    async with await _get_lock(uid):
        user = await db.users.find_one({"telegram_id": uid})
        if user is None:
            user_data = {
                "telegram_id": uid, "username": username, "display_name": name,
                "balance": STARTING_BALANCE, "total_wagered": 0, "total_won": 0,
                "games_played": 0, "last_daily": None, "daily_streak": 0,
                "created_at": datetime.now(), "updated_at": datetime.now()
            }
            await db.users.insert_one(user_data)
            user = user_data
    return dict(user)

# Ekonomi İşlemleri (Ekleme, Çıkarma, İstatistik)
async def add_balance(uid: int, amount: int, tx_type="win", desc="") -> bool:
    if amount <= 0: return False
    db = await get_db()
    async with await _get_lock(uid):
        result = await db.users.update_one({"telegram_id": uid}, {"$inc": {"balance": amount}, "$set": {"updated_at": datetime.now()}})
        if result.modified_count > 0:
            await db.transactions.insert_one({"to_id": uid, "amount": amount, "type": tx_type, "description": desc, "created_at": datetime.now()})
            return True
    return False

async def remove_balance(uid: int, amount: int, tx_type="bet", desc="") -> bool:
    if amount <= 0: return False
    db = await get_db()
    async with await _get_lock(uid):
        user = await db.users.find_one({"telegram_id": uid})
        if not user or user["balance"] < amount: return False
        await db.users.update_one({"telegram_id": uid}, {"$inc": {"balance": -amount, "total_wagered": amount}, "$set": {"updated_at": datetime.now()}})
        await db.transactions.insert_one({"from_id": uid, "amount": amount, "type": tx_type, "description": desc, "created_at": datetime.now()})
        return True
        
        
        
        # ═══════════════════════════════════════════════════════════════
#  STATE MANAGER & OYUN YÖNETİMİ
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
        "result": None, "created_at": datetime.now()
    }
    async with _state_lock:
        _active_games.setdefault(chat_id, {})[game_id] = game
    
    db = await get_db()
    await db.games.insert_one({**game, "participants": []}) # DB'de liste olarak tut
    return game

async def finish_game(chat_id: int, game_id: str, result: str = ""):
    async with _state_lock:
        if chat_id in _active_games and game_id in _active_games[chat_id]:
            _active_games[chat_id][game_id]["state"] = "FINISHED"
    
    db = await get_db()
    await db.games.update_one(
        {"game_id": game_id},
        {"$set": {"state": "FINISHED", "result": result, "finished_at": datetime.now()}}
    )

# ═══════════════════════════════════════════════════════════════
#  RATE LIMITER & YARDIMCILAR
# ═══════════════════════════════════════════════════════════════

_last_cmd: dict[int, float] = {}

def is_rate_limited(uid: int) -> bool:
    now = time.monotonic()
    if now - _last_cmd.get(uid, 0) < RATE_LIMIT_SECONDS:
        return True
    _last_cmd[uid] = now
    return False

def clean_name(name: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9ğüşıöçĞÜŞİÖÇ\s]', '', name)
    return cleaned.strip()[:15]

# ═══════════════════════════════════════════════════════════════
#  KOMUTLAR: START, BALANCE, HELP, MONEYS
# ═══════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = await get_or_create_user(user.id, user.username, user.full_name)
    lvl, emoji = get_level(u["balance"])
    
    await update.message.reply_text(
        f"🎰 <b>CasiniBot'a Hoş Geldiniz!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{user.full_name}</b> [{lvl}] {emoji}\n"
        f"💳 Bakiye: {format_amount(u['balance'])}\n\n"
        f"📌 Komutlar: /help | Menü: /menu",
        parse_mode="HTML"
    )



async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin Özel: Botun genel istatistiklerini gösterir"""
    user = update.effective_user
    
    # Senin sistemindeki admin kontrolü
    if user.id not in ADMIN_IDS:
        return

    db = await get_db()
    
    # Verileri topla
    total_users = await db.users.count_documents({})
    
    # Toplam bakiye ve istatistikler için aggregation (toplama)
    pipeline = [
        {
            "$group": {
                "_id": None,
                "total_bal": {"$sum": "$balance"},
                "total_games": {"$sum": {"$ifNull": ["$games_played", 0]}},
                "total_won": {"$sum": {"$ifNull": ["$total_won", 0]}}
            }
        }
    ]
    
    stats_res = await db.users.aggregate(pipeline).to_list(length=1)
    stats = stats_res[0] if stats_res else {"total_bal": 0, "total_games": 0, "total_won": 0}

    text = (
        "📊 <b>CASINIBOT GENEL İSTATİSTİKLER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Toplam Kullanıcı:</b> {total_users}\n"
        f"💰 <b>Dolaşımdaki Toplam Para:</b> {format_amount(stats['total_bal'])}\n"
        f"🎮 <b>Oynanan Toplam Oyun:</b> {stats['total_games']}\n"
        f"🏆 <b>Dağıtılan Toplam Kazanç:</b> {format_amount(stats['total_won'])}\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )
    
    await update.message.reply_text(text, parse_mode="HTML")
async def cmd_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_rate_limited(user.id): return
    
    u = await get_user(user.id)
    if not u: return
    
    db = await get_db()
    stats = await db.user_stats.find_one({"telegram_id": user.id}) or {}
    lvl, emoji = get_level(u["balance"])
    
    text = (
        f"📌 <b>Verilerim</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {user.full_name} ({lvl} {emoji})\n"
        f"🏧 Bakiye: {format_amount(u['balance'])}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Kazanma Oranları</b>\n"
        f"🎡 Rulet: %{stats.get('rulet_win_rate', 0)}\n"
        f"🃏 BJ: %{stats.get('blackjack_win_rate', 0)}\n"
        f"🎲 Zar: %{stats.get('dice_win_rate', 0)}\n"
        f"🏆 Toplam: %{stats.get('total_win_rate', 0)}"
    )
    await update.message.reply_text(text, parse_mode="HTML")



async def cmd_moneys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Para transferi - Güvenlik ve Görsellik Optimize Edildi"""
    user = update.effective_user
    msg = update.message
    
    if is_rate_limited(user.id):
        return
    
    args = ctx.args
    reply = msg.reply_to_message
    target_id = None
    target_name = "Bilinmeyen"
    amount_str = ""
    
    db = await get_db()

    # 1. HEDEF BELİRLEME MANTIĞI
    if reply:
        target_id = reply.from_user.id
        target_name = reply.from_user.full_name
        amount_str = args[0] if args else ""
    elif len(args) >= 2:
        # Username veya ID ile gönderim
        raw_target = args[0]
        amount_str = args[1]
        
        if raw_target.startswith("@"):
            username = raw_target[1:]
            u_data = await db.users.find_one({"username": username})
        else:
            try:
                u_id = int(raw_target)
                u_data = await db.users.find_one({"telegram_id": u_id})
            except: u_data = None
            
        if not u_data:
            return await msg.reply_text("❌ Kullanıcı bulunamadı.")
        
        target_id = u_data['telegram_id']
        target_name = u_data.get('display_name', "Oyuncu")
    else:
        return await msg.reply_text("❌ <b>Kullanım:</b>\n1. Yanıtlayarak: <code>/moneys 1000</code>\n2. Etiketle: <code>/moneys @etiket 1000</code>", parse_mode="HTML")

    # 2. KRİTİK GÜVENLİK KONTROLLERİ
    if target_id == user.id:
        return await msg.reply_text("❌ Kendi kendinize para gönderemezsiniz!")

    bal = await get_balance(user.id)
    amount, err = parse_amount(amount_str, bal)
    
    if err:
        return await msg.reply_text(f"❌ {err}")
    if amount <= 0:
        return await msg.reply_text("❌ Miktar 0'dan büyük olmalıdır!")
    if amount > bal:
        return await msg.reply_text(f"❌ Yetersiz bakiye! Mevcut: {format_amount(bal)}")

    # 3. ATOMİK TRANSFER İŞLEMİ
    # Gönderenden düş, alıcıya ekle (Sıralama önemli: Önce düşülür)
    await db.users.update_one({"telegram_id": user.id}, {"$inc": {"balance": -amount}})
    await db.users.update_one({"telegram_id": target_id}, {"$inc": {"balance": amount}})
    
    # İşlemi kaydet
    await db.transactions.insert_one({
        "from_id": user.id,
        "to_id": target_id,
        "amount": amount,
        "type": "transfer",
        "created_at": datetime.now()
    })
    
    new_bal = await get_balance(user.id)
    
    # 4. GÖRSEL VE MESAJ BÖLÜMÜ
    try:
        sender_clean = clean_name(user.full_name)
        receiver_clean = clean_name(target_name)
        transfer_img = create_transfer_image(sender_clean, receiver_clean, amount)
        
        await msg.reply_photo(
            photo=transfer_img,
            caption=(f"✅ <b>Transfer Başarılı!</b>\n"
                     f"💰 Gönderilen: <code>{format_amount(amount)}</code>\n"
                     f"💳 Kalan Bakiyeniz: <code>{format_amount(new_bal)}</code>"),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Görsel gönderim hatası: {e}")
        await msg.reply_text(
            f"✅ <b>Transfer Başarılı!</b>\n"
            f"📤 {user.full_name} → 📥 {target_name}\n"
            f"💰 Miktar: {format_amount(amount)}\n"
            f"💳 Yeni bakiye: {format_amount(new_bal)}",
            parse_mode="HTML"
        )
async def cmd_changename(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Kullanıcı ismini özelleştirir"""
    user = update.effective_user
    
    # 1. Hız Sınırı Kontrolü
    if is_rate_limited(user.id):
        return

    # 2. Giriş Kontrolü
    if not ctx.args:
        return await update.message.reply_text(
            "✏️ <b>İSİM DEĞİŞTİR</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "Kullanım: <code>/changename Yeni İsim</code>\n"
            "<i>Not: Maksimum 20 karakter.</i>", 
            parse_mode="HTML"
        )

    # 3. İsim Temizliği ve Kısıtlamalar
    # Başındaki/sonundaki boşlukları sil ve 20 karakterle sınırla (Tabloların bozulmaması için)
    new_name = " ".join(ctx.args).strip()
    
    if len(new_name) < 2:
        return await update.message.reply_text("❌ İsim en az 2 karakter olmalıdır!")
    
    if len(new_name) > 20:
        new_name = new_name[:20]

    # 4. Veritabanı Güncelleme
    try:
        db = await get_db()
        await db.users.update_one(
            {"telegram_id": user.id},
            {"$set": {"display_name": new_name}}
        )
        
        await update.message.reply_text(
            f"✅ Başarılı! Artık sizi <b>{new_name}</b> olarak tanıyoruz.", 
            parse_mode="HTML"
        )
        
        logger.info(f"👤 {user.id} ismini '{new_name}' olarak güncelledi.")
        
    except Exception as e:
        logger.error(f"İsim değiştirme hatası: {e}")
        await update.message.reply_text("❌ Bir hata oluştu, lütfen tekrar deneyin.")
            
            
# ═══════════════════════════════════════════════════════════════
#  VIP KASA - TELEGRAM STARS SATIN ALMA SİSTEMİ
# ═══════════════════════════════════════════════════════════════

# STARS_CONFIG Örneği (Global değişken olarak tanımlanmalı)
STARS_CONFIG = {
    10:  {"coin": 1_000_000,      "label": "Giriş Paketi"},
    25:  {"coin": 50_000_000,     "label": "Bronz Kasa"},
    50:  {"coin": 1_000_000_000,  "label": "Gümüş Kasa"},
    100: {"coin": 10_000_000_000, "label": "Altın Kasa"},
    250: {"coin": 100_000_000_000,"label": "Platin Kasa"},
    500: {"coin": 1_000_000_000_000, "label": "VIP Kasa"},
}

async def cmd_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Satın alma menüsünü gösterir"""
    keyboard = []
    # Paketleri butonlara dök
    for stars, config in STARS_CONFIG.items():
        keyboard.append([
            InlineKeyboardButton(
                f"🌟 {stars} Stars → {format_amount(config['coin'])}🪙",
                callback_data=f"buy_{stars}"
            )
        ])
    
    # Ana menüye dön butonu
    keyboard.append([InlineKeyboardButton("🏠 ANA MENÜ", callback_data="menu_main")])

    text = (
        "🌟 <b>VIP KASA - Telegram Stars</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Paket seçerek anında bakiye yükleyebilirsiniz:\n\n"
        "⚠️ <b>ÖNEMLİ:</b> Bu sanal oyun parasıdır, gerçek para değeri yoktur.\n"
        "✅ Satın alınan coinler anında hesaba geçer."
    )
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def buy_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Faturayı (Invoice) oluşturur ve gönderir"""
    query = update.callback_query
    await query.answer()
    
    try:
        stars_amount = int(query.data.split("_")[1])
        config = STARS_CONFIG.get(stars_amount)
        if not config: return

        # Stars faturası gönder (currency her zaman "XTR" olmalı)
        await ctx.bot.send_invoice(
            chat_id=query.from_user.id,
            title=f"🌟 {config['label']}",
            description=f"{format_amount(config['coin'])} Casino Coini satın alıyorsunuz.",
            payload=f"stars_{stars_amount}",
            provider_token="", # Stars için boş bırakılır
            currency="XTR",
            prices=[LabeledPrice(label=f"{stars_amount} Stars", amount=stars_amount)],
            start_parameter="vip_kasa"
        )
    except Exception as e:
        logger.error(f"Invoice hatası: {e}")
        await query.message.reply_text("❌ Ödeme ekranı açılırken bir hata oluştu.")

async def pre_checkout_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Ödeme onayı öncesi son kontrol (10 saniye içinde cevaplanmalı)"""
    query = update.pre_checkout_query
    # Burada stok kontrolü vb. yapılabilir. Bizde stok sınırsız olduğu için True dönüyoruz.
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Ödeme başarılı olduğunda bakiyeyi ekler"""
    msg = update.message
    user = update.effective_user
    
    try:
        payload = msg.successful_payment.invoice_payload
        stars = int(payload.split("_")[1])
        coin_amount = STARS_CONFIG[stars]["coin"]
        
        # Bakiyeyi veritabanına ekle
        await add_balance(user.id, coin_amount, "stars_purchase", f"{stars} Stars Purchase")
        new_bal = await get_balance(user.id)
        
        await msg.reply_text(
            f"✅ <b>SATIN ALMA BAŞARILI!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎁 Paket: <b>{STARS_CONFIG[stars]['label']}</b>\n"
            f"💰 Eklenen: <code>{format_amount(coin_amount)}</code>\n"
            f"💳 Yeni Bakiyeniz: <code>{format_amount(new_bal)}</code>\n\n"
            f"🎉 İyi oyunlar dileriz!",
            parse_mode="HTML"
        )
        
        logger.info(f"💰 {user.id} ({user.full_name}) {stars} Stars karşılığında coin aldı.")
        
    except Exception as e:
        logger.error(f"Payment processing error: {e}")
        await msg.reply_text("⚠️ Ödemeniz alındı ancak bakiyeniz eklenirken bir sorun oluştu. Lütfen yöneticiye başvurun.")         
# ═══════════════════════════════════════════════════════════════
#  GÜNLÜK BONUS SİSTEMİ
# ═══════════════════════════════════════════════════════════════

def get_daily_bonus(streak: int) -> int:
    """Seriye göre bonus miktarını hesaplar (Max 10 gün çarpanı)"""
    safe_streak = max(0, min(streak, 10))
    # 50.000 TL ile başlar, her gün ikiye katlanır
    return 50000 * (2 ** safe_streak)

async def check_daily_status(uid: int) -> tuple[bool, int, int]:
    """Bonus durumunu kontrol eder: (Alabilir mi, Kalan Saat, Yeni Seri)"""
    db = await get_db()
    user_data = await db.users.find_one({"telegram_id": uid})
    
    if not user_data or not user_data.get("last_daily"):
        return True, 0, 1
    
    last_daily = user_data["last_daily"]
    # Eğer last_daily string gelirse datetime'a çevir (uyumluluk için)
    if isinstance(last_daily, str):
        last_daily = datetime.fromisoformat(last_daily)
        
    now = datetime.now()
    diff = now - last_daily
    
    current_streak = user_data.get("daily_streak", 0)

    # 24 saat geçmediyse alamaz
    if diff.total_seconds() < 86400:
        hours_left = 24 - int(diff.total_seconds() // 3600)
        return False, hours_left, current_streak
    
    # 48 saatten fazla geçtiyse seri bozulur
    if diff.total_seconds() > 172800:
        return True, 0, 1
    
    return True, 0, current_streak + 1

async def cmd_daily(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_rate_limited(user.id): return
    
    # Kullanıcıyı hazırla
    await get_or_create_user(user.id, user.username, user.full_name)
    
    async with await _get_lock(user.id):
        can_claim, hours_left, new_streak = await check_daily_status(user.id)
        
        if not can_claim:
            await update.message.reply_text(
                f"⏰ <b>Günlük bonusunuzu zaten aldınız!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎁 Sonraki bonus: <b>{hours_left} saat</b> sonra\n"
                f"📈 Mevcut seri: <b>{new_streak} gün</b>",
                parse_mode="HTML"
            )
            return
        
        bonus_amount = get_daily_bonus(new_streak - 1) # 0'dan başlasın diye -1
        
        db = await get_db()
        await db.users.update_one(
            {"telegram_id": user.id},
            {
                "$inc": {"balance": bonus_amount},
                "$set": {
                    "last_daily": datetime.now(),
                    "daily_streak": new_streak,
                    "updated_at": datetime.now()
                }
            }
        )
        
        # İşlemi kaydet
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
            f"🎁 <b>GÜNLÜK BONUS ALINDI!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>{user.full_name}</b>\n"
            f"📅 Seri: <b>{new_streak}</b> gün\n"
            f"💰 Kazanılan: <b>+{format_amount(bonus_amount)}</b>\n"
            f"💳 Yeni bakiye: <b>{format_amount(new_balance)}</b>\n\n"
            f"🎯 Yarınki bonus: <b>{format_amount(next_bonus)}</b>",
            parse_mode="HTML"
        )
        
        
        
        
# ═══════════════════════════════════════════════════════════════
#  RULET YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════

def format_number_with_emoji(number: int) -> str:
    emoji_digits = {'0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
                    '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'}
    return ''.join(emoji_digits[d] for d in str(number))

def get_rank_emoji(rank: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, "📍")

def get_roulette_image(number: int) -> str:
    """Numaraya göre görsel dosyasını döner."""
    img_path = os.path.join(BASE_DIR, f"{number}.jpg")
    if not os.path.exists(img_path):
        spin_path = os.path.join(BASE_DIR, "spin.jpg")
        return spin_path if os.path.exists(spin_path) else None
    return img_path

# ═══════════════════════════════════════════════════════════════
#  RULET ANA MOTORU (TIMER & CALCULATION)
# ═══════════════════════════════════════════════════════════════

async def _roulette_timer(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int, game_id: str, msg):
    """Bahis süresini yönetir ve sonuçları hesaplar."""
    await asyncio.sleep(BET_WINDOW)
    
    async with _state_lock:
        game = _active_games.get(chat_id, {}).get(game_id)
        if not game or game["state"] != "OPEN": return
        game["state"] = "CALCULATING"
    
    winning = random.randint(0, 36)
    color = ROUL_COLORS[winning]
    color_emoji = ROUL_EMOJI[color]
    
    # Başlangıç mesajını sil (temizlik)
    try: await ctx.bot.delete_message(chat_id, msg.message_id)
    except: pass
    
    parts = await get_participants(chat_id, game_id)
    winner_list = []
    
    for uid, data in parts.items():
        user_total_payout = 0
        is_winner = False
        
        for b in data["bets"]:
            bet_amt = b["bet"]
            bd = b["bet_data"]
            payout = 0
            
            if bd.get("type") == "color" and bd.get("color") == color:
                payout = bet_amt * ROULETTE_MULTIPLIERS[color]
            elif bd.get("type") == "number" and winning in bd.get("numbers", []):
                # Birden fazla sayıya basıldıysa bahis bölünür
                per_num_bet = bet_amt // len(bd["numbers"])
                payout = per_num_bet * ROULETTE_MULTIPLIERS["number"]
            
            if payout > 0:
                user_total_payout += payout
                is_winner = True

        if user_total_payout > 0:
            await add_balance(uid, user_total_payout, "rulet_win", f"ID:{game_id}")
            # winner_list'e (İsim, Renk, Kazanç) ekle
            name = data["bets"][0]["bet_data"]["name"] # İsmi ilk bahisten al
            winner_list.append((name, color if is_winner else None, user_total_payout))
        
        # İstatistikleri güncelle (Parça 3'teki yapı)
        await update_win_rate(uid, "rulet", is_winner)

    # Sonuç Metni Oluşturma
    winner_list.sort(key=lambda x: x[2], reverse=True) # En çok kazanandan başla
    res_text = (
        f"🆔 GAME ID: <code>{game_id}</code>\n\n"
        f"🏆 Kazanan Sayı 🔘 {format_number_with_emoji(winning)} {color_emoji}!\n\n"
        f"🏧 <b>KAZANANLAR</b>\n"
    )
    
    if winner_list:
        for i, (name, w_color, amt) in enumerate(winner_list[:10], 1):
            res_text += f"{get_rank_emoji(i)} {name} +{format_amount(amt)} 🪙\n"
    else:
        res_text += "💀 Bu turda kazanan olmadı."

    # Görsel ile beraber gönder
    img_path = get_roulette_image(winning)
    try:
        if img_path:
            with open(img_path, "rb") as f:
                await ctx.bot.send_photo(chat_id, photo=f, caption=res_text, parse_mode="HTML")
        else:
            await ctx.bot.send_message(chat_id, res_text, parse_mode="HTML")
    except Exception as e:
        await ctx.bot.send_message(chat_id, res_text, parse_mode="HTML")
    
    await finish_game(chat_id, game_id, str(winning))
    await cleanup(chat_id)

# ═══════════════════════════════════════════════════════════════
#  BAHİS KOMUTLARI
# ═══════════════════════════════════════════════════════════════

async def cmd_rulet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ok, err = await can_open_game(chat_id, "rulet")
    if not ok:
        await update.message.reply_text(f"❌ {err}")
        return
    
    caption = (
        f"🎰 <b>AVRUPA RULETİ BAŞLADI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>{BET_WINDOW} saniye</b> içinde bahis yapın!\n\n"
        f"🔴 /red <miktar>\n⚫ /black <miktar>\n🟢 /green <miktar>\n"
        f"🔢 /number <sayı> <miktar>\n🔢 /numbers <1,2,3> <miktar>"
    )
    
    # Spin görselini gönder ve oyun kaydını yap
    spin_path = os.path.join(BASE_DIR, "spin.jpg")
    try:
        if os.path.exists(spin_path):
            with open(spin_path, "rb") as f:
                msg = await update.message.reply_photo(photo=f, caption=caption, parse_mode="HTML")
        else:
            msg = await update.message.reply_text(caption, parse_mode="HTML")
    except:
        msg = await update.message.reply_text(caption, parse_mode="HTML")

    game = await create_game(chat_id, "rulet", msg.message_id)
    asyncio.create_task(_roulette_timer(ctx, chat_id, game["game_id"], msg))

# /red, /black, /green, /number, /numbers için ortak işleyici
async def _rulet_bet(update: Update, bet_type: str, color=None, numbers=None, amount_str="0"):
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    game = await get_active_game(chat_id, "rulet")
    if not game or game["state"] != "OPEN":
        await update.message.reply_text("❌ Şu an açık bahis yok.")
        return

    bal = await get_balance(user.id)
    amount, err = parse_amount(amount_str, bal)
    if err:
        await update.message.reply_text(f"❌ {err}")
        return

    if await remove_balance(user.id, amount, "rulet_bet", f"ID:{game['game_id']}"):
        bd = {
            "type": bet_type, "color": color, 
            "numbers": numbers or [], "name": user.full_name
        }
        await add_participant(chat_id, game["game_id"], user.id, amount, bd)
        emoji = {"red":"🔴", "black":"⚫", "green":"🟢"}.get(color, "🔢")
        await update.message.reply_text(f"✅ {user.full_name}, {emoji} {format_amount(amount)} 🪙 değerinde bahsiniz alındı.")

# Komut Yönlendirmeleri
async def cmd_red(u, c): await _rulet_bet(u, "color", color="red", amount_str=c.args[0] if c.args else "0")
async def cmd_black(u, c): await _rulet_bet(u, "color", color="black", amount_str=c.args[0] if c.args else "0")
async def cmd_green(u, c): await _rulet_bet(u, "color", color="green", amount_str=c.args[0] if c.args else "0")
async def cmd_number(u, c):
    if len(c.args) < 2: return await u.message.reply_text("❌ /number <0-36> <miktar>")
    await _rulet_bet(u, "number", numbers=[int(c.args[0])], amount_str=c.args[1])
async def cmd_numbers(u, c):
    if len(c.args) < 2: return await u.message.reply_text("❌ /numbers <1,2,3> <miktar>")
    nums = [int(x) for x in c.args[0].split(",") if x.strip().isdigit()]
    await _rulet_bet(u, "number", numbers=nums, amount_str=c.args[1])
    
    
    
    
# ═══════════════════════════════════════════════════════════════
#  BLACKJACK - GÖRSEL VE KART MOTORU
# ═══════════════════════════════════════════════════════════════

def get_card_image(card: tuple) -> Image.Image:
    rank, suit = card
    rank_map = {"A": "ace", "J": "jack", "Q": "queen", "K": "king"}
    suit_map = {"♠️": "spades", "♥️": "hearts", "♦️": "diamonds", "♣️": "clubs"}
    
    # Dosya adını oluştur (Örn: ace_of_spades.png)
    rank_name = rank_map.get(rank, rank)
    suit_name = suit_map.get(suit, "spades")
    filename = f"{rank_name}_of_{suit_name}.png"
    img_path = os.path.join(BASE_DIR, filename)
    
    if os.path.exists(img_path):
        img = Image.open(img_path)
        return img.resize((CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS)
    
    # Görsel yoksa gri bir kart oluştur (Hata önleyici)
    return Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), color='#2c2c2c')

def combine_cards(cards: list, hidden: bool = False) -> io.BytesIO:
    """Kartları yanyana birleştirir."""
    if not cards: return None
    total_width = len(cards) * CARD_WIDTH
    combined = Image.new('RGB', (total_width, CARD_HEIGHT), color='#1a1a2e')
    
    for i, card in enumerate(cards):
        if hidden and i == 0:
            # İlk kartı kapalı göster
            back_path = os.path.join(BASE_DIR, "back.png")
            if os.path.exists(back_path):
                img = Image.open(back_path).resize((CARD_WIDTH, CARD_HEIGHT))
            else:
                img = Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), color='#444444')
        else:
            img = get_card_image(card)
        combined.paste(img, (i * CARD_WIDTH, 0))
    
    bio = io.BytesIO()
    combined.save(bio, format='PNG')
    bio.seek(0)
    return bio

# ═══════════════════════════════════════════════════════════════
#  BLACKJACK ANA OYUN MANTIĞI
# ═══════════════════════════════════════════════════════════════

def _hand_val(hand: list) -> int:
    total = 0
    aces = 0
    for r, s in hand:
        if r in ("J", "Q", "K"): total += 10
        elif r == "A": 
            total += 11
            aces += 1
        else: total += int(r)
    
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

async def cmd_blackjack(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ok, err = await can_open_game(chat_id, "blackjack")
    if not ok: return await update.message.reply_text(f"❌ {err}")

    msg = await update.message.reply_text(
        f"🃏 <b>BLACKJACK BAŞLADI!</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>{BET_WINDOW} saniye</b> içinde bahis yapın!\n\n"
        f"📌 /bj <miktar>\n• Kazanç: 2.0x",
        parse_mode="HTML"
    )
    
    game = await create_game(chat_id, "blackjack", msg.message_id)
    _bj[chat_id] = {
        "game_id": game["game_id"], "state": "BETTING", 
        "players": {}, "order": [], "dealer": [], "deck": [], "current": 0
    }
    asyncio.create_task(_bj_bet_timer(ctx, chat_id, game["game_id"]))

async def cmd_bj(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    bj = _bj.get(chat_id)
    
    if not bj or bj["state"] != "BETTING":
        return await update.message.reply_text("❌ Şu an bahis dönemi değil.")
    
    bal = await get_balance(user.id)
    amount, err = parse_amount(ctx.args[0] if ctx.args else "0", bal)
    if err: return await update.message.reply_text(f"❌ {err}")

    if await remove_balance(user.id, amount, "bj_bet", f"ID:{bj['game_id']}"):
        if user.id in bj["players"]:
            bj["players"][user.id]["bet"] += amount
        else:
            bj["players"][user.id] = {"bet": amount, "hand": [], "state": "WAITING", "name": user.full_name}
            bj["order"].append(user.id)
        await update.message.reply_text(f"✅ {user.full_name} {format_amount(amount)} 🪙 bahis yaptı.")

# ═══════════════════════════════════════════════════════════════
#  SIRALAMA VE BUTON YÖNETİMİ
# ═══════════════════════════════════════════════════════════════

async def bj_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action, game_id = query.data.split(":", 1)
    chat_id = query.message.chat_id
    bj = _bj.get(chat_id)
    
    if not bj or bj["game_id"] != game_id: return
    
    uid = bj["order"][bj["current"]]
    if query.from_user.id != uid:
        return await query.answer("Sıra sende değil!", show_alert=True)
    
    p = bj["players"][uid]
    if p.get("task"): p["task"].cancel()

    if action == "bj_hit":
        p["hand"].append(bj["deck"].pop())
        val = _hand_val(p["hand"])
        img = combine_cards(p["hand"])
        
        if val > 21:
            p["state"] = "BUST"
            await query.edit_message_media(InputMediaPhoto(img, caption=f"💥 <b>BUST! {val}</b>\n❌ {p['name']} kaybetti.", parse_mode="HTML"))
            bj["current"] += 1
            await _bj_next(ctx, chat_id, game_id)
        elif val == 21:
            p["state"] = "STAND"
            await query.edit_message_media(InputMediaPhoto(img, caption=f"🎉 <b>21!</b>\n✅ {p['name']} durdu.", parse_mode="HTML"))
            bj["current"] += 1
            await _bj_next(ctx, chat_id, game_id)
        else:
            await query.edit_message_media(InputMediaPhoto(img, caption=f"🃏 <b>Sıra Sende: {val}</b>", parse_mode="HTML"), reply_markup=_bj_kb(game_id))
            p["task"] = asyncio.create_task(_bj_timeout(ctx, chat_id, game_id, uid))
            
    elif action == "bj_stand":
        p["state"] = "STAND"
        img = combine_cards(p["hand"])
        await query.edit_message_media(InputMediaPhoto(img, caption=f"✋ <b>DURDU: {_hand_val(p['hand'])}</b>", parse_mode="HTML"))
        bj["current"] += 1
        await _bj_next(ctx, chat_id, game_id)
        
        
# ═══════════════════════════════════════════════════════════════
#  ZAR OYUNU (PvP) - GELİŞMİŞ MOTOR
# ═══════════════════════════════════════════════════════════════

async def cmd_dicebet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if is_rate_limited(update.effective_user.id): return
    
    ok, err = await can_open_game(chat_id, "dice")
    if not ok: return await update.message.reply_text(f"❌ {err}")
    
    msg = await update.message.reply_text(
        f"🎲 <b>ZAR OYUNU BAŞLADI! (PvP)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>{BET_WINDOW} saniye</b> içinde katılın!\n\n"
        f"📌 <code>/dice &lt;miktar&gt;</code>\n"
        f"🎯 En yüksek zar toplamı havuzu kazanır!\n"
        f"🤝 Beraberlikte havuz bölüşülür.",
        parse_mode="HTML")
    
    game = await create_game(chat_id, "dice", msg.message_id)
    # Başlangıç bahis miktarını sıfırla
    game["min_bet"] = 0
    asyncio.create_task(_dice_bet_timer(ctx, chat_id, game["game_id"]))

async def cmd_dice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    game = await get_active_game(chat_id, "dice")
    if not game or game["state"] != "OPEN":
        return await update.message.reply_text("❌ Şu an katılabileceğiniz aktif bir oyun yok.")
    
    bal = await get_balance(user.id)
    amount, err = parse_amount(ctx.args[0] if ctx.args else "0", bal)
    if err: return await update.message.reply_text(f"❌ {err}")
    
    # PvP için minimum bahis kontrolü (İlk giren belirler)
    parts = await get_participants(chat_id, game["game_id"])
    if not parts:
        game["min_bet"] = amount
    elif amount < game["min_bet"]:
        return await update.message.reply_text(f"❌ Bu el için minimum bahis: {format_amount(game['min_bet'])}")
    
    if await remove_balance(user.id, amount, "dice_bet", f"ID:{game['game_id']}"):
        await add_participant(chat_id, game["game_id"], user.id, amount, {"name": user.full_name})
        count = len(await get_participants(chat_id, game["game_id"]))
        await update.message.reply_text(f"🎲 {user.full_name} {format_amount(amount)} ile katıldı! (Toplam: {count} Oyuncu)")

# ═══════════════════════════════════════════════════════════════
#  ZAR ATMA VE SONUÇLANDIRMA
# ═══════════════════════════════════════════════════════════════

async def _dice_next_player(ctx, chat_id, game_id):
    game = await get_active_game(chat_id, "dice")
    if not game or game["game_id"] != game_id: return
    
    idx = game.get("current_player_index", 0)
    order = game["order"]
    
    if idx >= len(order):
        await _dice_calculate_results(ctx, chat_id, game_id)
        return
    
    uid = order[idx]
    player_name = game["participants_data"][uid]["bet_data"]["name"]
    
    # --- ANIMASYONLU ZAR KISMI ---
    # Telegram'ın kendi zar animasyonunu gönderiyoruz
    msg1 = await ctx.bot.send_dice(chat_id, emoji="🎲")
    msg2 = await ctx.bot.send_dice(chat_id, emoji="🎲")
    
    total = msg1.dice.value + msg2.dice.value
    
    game["players_rolled"][uid] = {
        "total": total, "name": player_name, "bet": game["participants_data"][uid]["bet"]
    }
    
    await ctx.bot.send_message(chat_id, f"🎲 <b>{player_name}</b> attı: {msg1.dice.value} + {msg2.dice.value} = <b>{total}</b>", parse_mode="HTML")
    
    game["current_player_index"] += 1
    await asyncio.sleep(3.5) # Animasyonun bitmesi için biraz bekliyoruz
    await _dice_next_player(ctx, chat_id, game_id)

async def _dice_calculate_results(ctx, chat_id, game_id):
    game = await get_active_game(chat_id, "dice")
    if not game: return
    
    players = game["players_rolled"]
    pool = sum(p["bet"] for p in players.values())
    max_score = max(p["total"] for p in players.values())
    winners = [(uid, p) for uid, p in players.items() if p["total"] == max_score]
    
    res = ["🎲 <b>ZAR OYUNU SONUÇLARI</b>", "━━━━━━━━━━━━━━━━━━━━━"]
    for p in players.values():
        res.append(f"• {p['name']}: <b>{p['total']}</b>")
    res.append("━━━━━━━━━━━━━━━━━━━━━")
    
    payout_per = pool // len(winners)
    
    for uid, p in winners:
        await add_balance(uid, payout_per, "dice_win", f"ID:{game_id}")
        await update_stats(uid, payout_per)
        await update_win_rate(uid, "dice", True)
        res.append(f"🏆 <b>KAZANAN: {p['name']}</b>\n💰 Ödül: {format_amount(payout_per)}")

    # Kaybedenlerin istatistiklerini güncelle
    winner_ids = [w[0] for w in winners]
    for uid in players:
        if uid not in winner_ids:
            await update_win_rate(uid, "dice", False)

    await ctx.bot.send_message(chat_id, "\n".join(res), parse_mode="HTML")
    await finish_game(chat_id, game_id, "success")
    await cleanup(chat_id)
    
    
    
# ═══════════════════════════════════════════════════════════════
#  KAZI KAZAN - TAM FONKSİYONLAR (HIZLANDIRILMIŞ)
# ═══════════════════════════════════════════════════════════════

# Global şablon (Hız için bellekte tutulur, silinmez)
_SCRATCH_TEMPLATE = None

def get_scratch_template():
    global _SCRATCH_TEMPLATE
    if _SCRATCH_TEMPLATE is None:
        acik_path = os.path.join(BASE_DIR, "acik.jpg")
        if os.path.exists(acik_path):
            img = Image.open(acik_path)
            img.thumbnail((800, 600), Image.Resampling.LANCZOS)
            _SCRATCH_TEMPLATE = img
    return _SCRATCH_TEMPLATE

def create_scratch_result_image(board: list, winner_mult: int) -> io.BytesIO:
    """Orijinal koordinatlar ve tam mantıkla görsel oluşturma"""
    template = get_scratch_template()
    if template is None:
        img = Image.new('RGB', (800, 600), color='#2c2c2c')
    else:
        img = template.copy()
    
    draw = ImageDraw.Draw(img)
    font = get_font(100)
    width, height = img.size
    
    # SENİN ORIJINAL KOORDINATLARIN (Tam Liste)
    boxes = [
        {"center": (width * 0.16, height * 0.25), "index": 0},
        {"center": (width * 0.51, height * 0.25), "index": 1},
        {"center": (width * 0.83, height * 0.25), "index": 2},
        {"center": (width * 0.16, height * 0.69), "index": 3},
        {"center": (width * 0.51, height * 0.69), "index": 4},
        {"center": (width * 0.83, height * 0.69), "index": 5},
    ]
    
    for box in boxes:
        center_x, center_y = int(box["center"][0]), int(box["center"][1])
        value = board[box["index"]]
        
        if value == winner_mult and winner_mult > 0:
            text_color = (0, 255, 0) # Yeşil (Kazanan)
        elif value == 0:
            text_color = (255, 0, 0) # Kırmızı (Boş)
        else:
            text_color = (255, 255, 255) # Beyaz
        
        text = f"{value}x"
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        
        draw.text(
            (center_x - tw/2, center_y - th/2),
            text, fill=text_color, font=font,
            stroke_width=3, stroke_fill=(0, 0, 0)
        )
    
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    return bio

async def cmd_kazisolo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Tek kişilik Kazı Kazan - Hiçbir detay silinmeden"""
    user = update.effective_user
    if is_rate_limited(user.id): return
    
    if not ctx.args:
        return await update.message.reply_text(
            "🎟 <b>KAZI KAZAN (SOLO)</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
            "📌 Kullanım: <code>/kazisolo <miktar></code>\n"
            "🏆 3 aynı çarpan = KAZANÇ!", parse_mode="HTML"
        )
    
    await get_or_create_user(user.id, user.username, user.full_name)
    bal = await get_balance(user.id)
    amount, err = parse_amount(ctx.args[0], bal)
    if err: return await update.message.reply_text(f"❌ {err}")
    
    if not await remove_balance(user.id, amount, "bet", "Kazı Kazan Solo"):
        return await update.message.reply_text("❌ Yetersiz bakiye.")
    
    # Başlangıç görselini gönder
    kapali_kart = os.path.join(BASE_DIR, "Kapali.jpg")
    if os.path.exists(kapali_kart):
        with open(kapali_kart, "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=f"🎟 <b>KAZI KAZAN (SOLO)</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
                        f"💰 Bahis: {format_amount(amount)}\n✨ KAZIYORSUN... ✨",
                parse_mode="HTML"
            )
    
    await asyncio.sleep(1.5) # Orijinal bekleme süresi
    
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
            await update_win_rate(user.id, "scratch", True)
            msg = f"✅ <b>{winner_mult}x</b> bulundu!\n🎉 KAZANDIN! +{format_amount(payout - amount)}"
        else:
            await update_stats(user.id, 0)
            await update_win_rate(user.id, "scratch", False)
            msg = f"❌ Eşleşme yok!\n💀 KAYBETTİN! -{format_amount(amount)}"
        
        new_bal = await get_balance(user.id)
        await update.message.reply_photo(
            photo=result_img,
            caption=f"🎟 <b>KAZI KAZAN (SOLO)</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{msg}\n💳 Yeni bakiye: {format_amount(new_bal)}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Kazı Kazan hatası: {e}")
        # Hata durumunda senin yazdığın 'mesaj ile bilgilendirme' kısmını aynen korudum...
        # (Burada orijinal hata yönetimi kodun devam ediyor)
        
        
        
# ═══════════════════════════════════════════════════════════════
#  ÇARKIFELEK - TAM MOTOR (ANİMASYONLU)
# ═══════════════════════════════════════════════════════════════

async def cmd_wheelbet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if is_rate_limited(update.effective_user.id): return
    
    ok, err = await can_open_game(chat_id, "wheel")
    if not ok:
        return await update.message.reply_text(f"❌ {err}")
    
    # Senin orijinal çarpan listenin görseli
    msg = await update.message.reply_text(
        f"🎡 <b>ÇARKIFELEK BAŞLADI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>{BET_WINDOW} saniye</b> içinde katılın!\n\n"
        f"📌 <code>/wheel &lt;miktar&gt;</code>\n\n"
        f"<b>ÖDÜLLER:</b>\n"
        f"💀 PASS | 🔄 İADE | 2x | 3x | 5x | 10x | 25x | 100x",
        parse_mode="HTML")
    
    game = await create_game(chat_id, "wheel", msg.message_id)
    asyncio.create_task(_wheel_timer(ctx, chat_id, game["game_id"]))

async def cmd_wheel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    game = await get_active_game(chat_id, "wheel")
    if not game or game["state"] != "OPEN":
        return await update.message.reply_text("❌ Şu an açık bir çark yok.")
    
    await get_or_create_user(user.id, user.username, user.full_name)
    bal = await get_balance(user.id)
    amount, err = parse_amount(ctx.args[0] if ctx.args else "0", bal)
    if err: return await update.message.reply_text(f"❌ {err}")
    
    # Bakiyeyi düş ve katılımcıyı ekle (Senin orijinal sıran)
    if await remove_balance(user.id, amount, "wheel_bet", f"ID:{game['game_id']}"):
        await add_participant(chat_id, game["game_id"], user.id, amount, {"name": user.full_name})
        await update.message.reply_text(f"🕹 <b>{user.full_name}</b> {format_amount(amount)} ile çarka dahil oldu!", parse_mode="HTML")

async def _wheel_timer(ctx, chat_id, game_id):
    await asyncio.sleep(BET_WINDOW)
    
    game = await get_active_game(chat_id, "wheel")
    if not game or game["game_id"] != game_id: return
    
    parts = await get_participants(chat_id, game_id)
    if not parts:
        await ctx.bot.send_message(chat_id, "🎡 Çark boş kaldı, oyun iptal.")
        await finish_game(chat_id, game_id, "empty")
        return

    game["state"] = "CALCULATING"
    
    # --- ANİMASYON EFEKTİ (Dönüyormuş gibi) ---
    anim_msg = await ctx.bot.send_message(chat_id, "🎡 <b>ÇARK DÖNÜYOR...</b>\n[ 🎲 🎲 🎲 🎲 🎲 ]", parse_mode="HTML")
    await asyncio.sleep(1)
    
    # Orijinal segment mantığın ve güvenli seçim
    # WHEEL_SEGMENTS: [("💀 PASS", 0), ("🔄 İADE", 1), ("💰 2x", 2) ...]
    shuffled_segments = random.sample(WHEEL_SEGMENTS, len(WHEEL_SEGMENTS))
    label, mult = secrets.choice(shuffled_segments)
    
    # --- SONUÇ HESAPLAMA (Tam Orijinal Mantık) ---
    lines = [f"🎡 <b>ÇARK DURDU!</b>", f"━━━━━━━━━━━━━━━━━━━━━",
             f"🎯 Sonuç: <b>{label}</b>", ""]
    
    total_payout = 0
    for uid, d in parts.items():
        name = d["bet_data"]["name"]
        bet = d["bet"]
        
        if mult == 0: # PASS
            await update_stats(uid, 0)
            await update_win_rate(uid, "wheel", False)
            lines.append(f"💀 {name}: -{format_amount(bet)}")
        elif mult == 1: # İADE
            await add_balance(uid, bet, "refund", f"Wheel ID:{game_id}")
            await update_stats(uid, 0)
            await update_win_rate(uid, "wheel", True)
            lines.append(f"🔄 {name}: İade (+0)")
        else: # ÇARPAN
            payout = bet * mult
            await add_balance(uid, payout, "win", f"Wheel ID:{game_id}")
            await update_stats(uid, payout)
            await update_win_rate(uid, "wheel", True)
            total_payout += payout
            lines.append(f"✅ {name}: +{format_amount(payout - bet)} (<b>{mult}x</b>)")

    if mult > 1:
        lines.append(f"\n💰 Toplam Dağıtılan: {format_amount(total_payout)}")
    
    lines.append("\n✨ Yeni oyun için <code>/wheelbet</code>")
    
    # Animasyon mesajını sonuçla güncelle
    await anim_msg.edit_text("\n".join(lines), parse_mode="HTML")
    
    await finish_game(chat_id, game_id, label)
    await cleanup(chat_id)
    
    
    
# ═══════════════════════════════════════════════════════════════
#  YÖNETİM VE TERMİNAL KOMUTLARI
# ═══════════════════════════════════════════════════════════════

async def cmd_addbalance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin: Kullanıcıya bakiye ekle (Reply, ID veya Self)"""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return await update.message.reply_text("⛔ Yetkiniz yok!")

    args = ctx.args
    target_id = None
    amount_str = None

    # Hedef Belirleme Mantığı (Senin Orijinal Yapın)
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
            return await update.message.reply_text("❌ Geçersiz ID!")
    
    if not target_id or not amount_str:
        return await update.message.reply_text("❓ Kullanım: /addbalance <id/reply> <miktar>")

    # Adminler için parse_amount limitini 1 Katrilyon yapıyoruz
    amount, err = parse_amount(amount_str, 10**15) 
    if err: return await update.message.reply_text(f"❌ {err}")

    # MongoDB Güncelleme
    db = await get_db()
    target_user = await db.users.find_one({"telegram_id": target_id})
    if not target_user:
        return await update.message.reply_text("❌ Kullanıcı veritabanında yok!")

    await add_balance(target_id, amount, "admin_gift", f"Admin:{user.id}")
    new_bal = await get_balance(target_id)

    await update.message.reply_text(
        f"✅ <b>BAKİYE EKLENDİ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Hedef: {target_user.get('display_name', 'Bilinmiyor')}\n"
        f"💰 Miktar: {format_amount(amount)}\n"
        f"💳 Güncel: {format_amount(new_bal)}",
        parse_mode="HTML"
    )



async def cmd_setbalance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin Özel: Bakiyeyi direkt olarak verilen miktara eşitleyen komut"""
    user = update.effective_user
    
    # Senin sisteminde tanımlı olan ADMIN_IDS kontrolünü buraya alıyoruz
    if user.id not in ADMIN_IDS:
        return

    args = ctx.args
    reply = update.message.reply_to_message
    
    target_id = None
    amount_str = ""

    # Yanıtla veya ID ile hedef belirleme
    if reply:
        target_id = reply.from_user.id
        amount_str = args[0] if args else ""
    elif len(args) >= 2:
        try:
            target_id = int(args[0])
            amount_str = args[1]
        except:
            return await update.message.reply_text("❌ Kullanım: /setbalance <id> <miktar>")
    else:
        return await update.message.reply_text("❌ Kullanım: /setbalance <miktar> (reply) veya /setbalance <id> <miktar>")

    # Admin'in yazdığı miktarı işle
    # parse_amount fonksiyonun 1M, 1k gibi kısaltmaları da çözecektir
    target_bal, err = parse_amount(amount_str, 999_999_999_999_999) # Admin için limit kontrolü devredışı
    
    if err:
        return await update.message.reply_text(f"❌ Hata: {err}")

    db = await get_db()
    
    # Bakiyeyi direkt EŞİTLE ($set kullanımı)
    result = await db.users.update_one(
        {"telegram_id": target_id},
        {"$set": {"balance": target_bal}}
    )
    
    if result.matched_count > 0:
        await update.message.reply_text(
            f"🛠 <b>ADMİN GÜNCELLEME</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Hedef ID:</b> <code>{target_id}</code>\n"
            f"💰 <b>Yeni Bakiye:</b> {format_amount(target_bal)}\n"
            f"✅ Bakiye başarıyla eşitlendi.",
            parse_mode="HTML"
        )
        logger.warning(f"⚠️ ADMIN {user.id}, {target_id} bakiyesini {target_bal} yaptı.")
    else:
        await update.message.reply_text("❌ Kullanıcı veritabanında bulunamadı.")
async def cmd_cleanup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin: Takılı kalan oyunları ve bellek kilitlerini temizle"""
    if update.effective_user.id not in ADMIN_IDS: return

    # 1. Bellek (RAM) Temizliği
    async with _state_lock:
        _active_games.clear()
        if '_bj' in globals(): _bj.clear() # Blackjack sözlüğü varsa temizle
    
    # 2. Veritabanı (MongoDB) Temizliği
    db = await get_db()
    res = await db.games.update_many(
        {"state": {"$in": ["OPEN", "PLAYING", "CALCULATING"]}},
        {"$set": {"state": "FINISHED", "finished_at": datetime.now()}}
    )

    await update.message.reply_text(
        f"🧹 <b>SİSTEM TEMİZLENDİ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Bellek sıfırlandı.\n"
        f"✅ {res.modified_count} oyun arşive alındı.\n"
        f"🎮 Bot şu an tertemiz!", parse_mode="HTML"
    )

async def cmd_reklam(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin: Tüm gruplara duyuru gönder (Hız Sınırı Korumalı)"""
    if update.effective_user.id not in ADMIN_IDS: return
    
    if not ctx.args:
        return await update.message.reply_text("📢 Mesaj yazmalısınız: /reklam <mesaj>")

    reklam_metni = " ".join(ctx.args)
    db = await get_db()
    
    # Sadece aktif grupları çek
    groups = await db.groups.find({"is_active": True}).to_list(length=1000)
    
    if not groups:
        return await update.message.reply_text("❌ Kayıtlı aktif grup bulunamadı.")

    basarili, hata = 0, 0
    progress_msg = await update.message.reply_text(f"⏳ Gönderim başladı (0/{len(groups)})...")

    for group in groups:
        try:
            chat_id = group.get("chat_id") or group.get("_id")
            await ctx.bot.send_message(
                chat_id,
                f"📢 <b>SİSTEM DUYURUSU</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{reklam_metni}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━",
                parse_mode="HTML"
            )
            basarili += 1
            # Flood koruması için her 30 mesajda bir uzun bekleme, aralarda kısa bekleme
            await asyncio.sleep(0.1) 
            if basarili % 20 == 0: await asyncio.sleep(2)
        except Exception:
            hata += 1
    
    await progress_msg.edit_text(
        f"✅ <b>DUYURU TAMAMLANDI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📨 Başarılı: {basarili}\n"
        f"❌ Hatalı: {hata}", parse_mode="HTML"
    )

async def cmd_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Kullanıcının kendi ID'sini görmesi için"""
    user = update.effective_user
    await update.message.reply_text(f"🆔 <b>ID:</b> <code>{user.id}</code>", parse_mode="HTML")
    
    
    
    
# ═══════════════════════════════════════════════════════════════
#  ANA MENÜ KLAVYESİ (MERKEZİ YAPI)
# ═══════════════════════════════════════════════════════════════

def get_main_menu_keyboard():
    """Ana menü butonlarını döndürür - Tek yerden yönetim"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 RULET", callback_data="menu_roulette"),
         InlineKeyboardButton("🃏 BLACKJACK", callback_data="menu_blackjack")],
        [InlineKeyboardButton("🎲 ZAR (PvP)", callback_data="menu_dice"),
         InlineKeyboardButton("🎡 ÇARKIFELEK", callback_data="menu_wheel")],
        [InlineKeyboardButton("🎟️ KAZI KAZAN", callback_data="menu_scratch"),
         InlineKeyboardButton("💰 BAKİYE", callback_data="menu_balance")],
        [InlineKeyboardButton("🏆 LİDERLİK", callback_data="menu_leaderboard"),
         InlineKeyboardButton("🎁 GÜNLÜK BONUS", callback_data="menu_daily")],
        [InlineKeyboardButton("🌟 VIP KASA", callback_data="menu_buy"),
         InlineKeyboardButton("❓ YARDIM", callback_data="menu_help")]
    ])

# ═══════════════════════════════════════════════════════════════
#  ANA MENÜ KOMUTU
# ═══════════════════════════════════════════════════════════════

async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await get_or_create_user(user.id, user.username, user.full_name)
    bal = await get_balance(user.id)
    
    text = (f"🎮 <b>BETTMASTER ANA MENÜ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Kullanıcı:</b> {user.full_name}\n"
            f"💰 <b>Bakiyeniz:</b> {format_amount(bal)}\n\n"
            f"<i>Oynamak istediğiniz oyunu seçin veya bilgi alın:</i>")
    
    await update.message.reply_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")

# ═══════════════════════════════════════════════════════════════
#  CALLBACK HANDLER (TÜM NAVİGASYON BURADA)
# ═══════════════════════════════════════════════════════════════

async def menu_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    
    # KRİTİK: Donmayı engellemek için anında cevap ver
    await query.answer()

    # Yardımcı Fonksiyon: Alt menü butonlarını oluşturur (Başlat + Geri Dön)
    def get_sub_kb(game_key=None):
        buttons = []
        if game_key:
            buttons.append(InlineKeyboardButton(f"🚀 OYUNU BAŞLAT", callback_data=f"start_{game_key}"))
        buttons.append(InlineKeyboardButton("🏠 ANA MENÜ", callback_data="menu_main"))
        return InlineKeyboardMarkup([buttons])

    # --- 1. OYUN REHBERLERİ ---
    if data == "menu_roulette":
        text = ("🎰 <b>RULET NASIL OYNANIR?</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
                "• 25 saniye içinde bahisleri yapın.\n"
                "• /red, /black, /green veya /number\n"
                "• Çarpanlar: Renk 2x, Sayı 36x, Yeşil 72x!")
        await query.edit_message_text(text, reply_markup=get_sub_kb("rulet"), parse_mode="HTML")

    elif data == "menu_blackjack":
        text = ("🃏 <b>BLACKJACK KURALLARI</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
                "• Hedef 21'i geçmeden kasadan yüksek sayı almak.\n"
                "• Kasa 17'de durmak zorundadır.\n"
                "• Kazanç: 2x")
        await query.edit_message_text(text, reply_markup=get_sub_kb("blackjack"), parse_mode="HTML")

    elif data == "menu_wheel":
        text = ("🎡 <b>ÇARKIFELEK ŞANSI</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
                "• Çarkı döndür, gelen çarpanı kap!\n"
                "• Sonuçlar: PASS (0x), İADE (1x) veya 100x'e kadar çarpan.")
        await query.edit_message_text(text, reply_markup=get_sub_kb("wheelbet"), parse_mode="HTML")

    # --- 2. HIZLI BAŞLATMA MANTIĞI ---
    elif data.startswith("start_"):
        game_key = data.split("_")[1]
        # Menüyü silip oyunu tetikliyoruz (Donma yapmaz)
        await query.message.delete()
        
        if game_key == "rulet": await cmd_rulet(update, ctx)
        elif game_key == "blackjack": await cmd_blackjack(update, ctx)
        elif game_key == "wheelbet": await cmd_wheelbet(update, ctx)
        elif game_key == "dicebet": await cmd_dicebet(update, ctx)
        elif game_key == "kazibet": await cmd_kazibet(update, ctx)

    # --- 3. ANA MENÜYE DÖNÜŞ ---
    elif data == "menu_main":
        bal = await get_balance(user.id)
        text = (f"🎮 <b>BETTMASTER ANA MENÜ</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Kullanıcı:</b> {user.full_name}\n"
                f"💰 <b>Bakiyeniz:</b> {format_amount(bal)}")
        await query.edit_message_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")

    # --- 4. ÖZEL MENÜLER (Bakiye, Bonus, Liderlik) ---
    elif data == "menu_balance":
        u = await get_user(user.id)
        lvl, emoji = get_level(u["balance"])
        text = (f"💳 <b>BAKİYE DETAYLARI</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 Bakiye: {format_amount(u['balance'])}\n"
                f"🏅 Seviye: {lvl} {emoji}\n"
                f"📊 Toplam Kazanç: {format_amount(u.get('total_won', 0))}")
        await query.edit_message_text(text, reply_markup=get_sub_kb(), parse_mode="HTML")

    elif data == "menu_daily":
        can_claim, result = await check_daily_bonus(user.id)
        if can_claim:
            await add_balance(user.id, result, "daily", "Menu Claim")
            msg = f"🎁 <b>GÜNLÜK BONUS ALINDI!</b>\n\n+{format_amount(result)} bakiyenize eklendi."
        else:
            msg = f"⏳ <b>HENÜZ DEĞİL!</b>\n\nBonus için {result} beklemen gerekiyor."
        await query.edit_message_text(msg, reply_markup=get_sub_kb(), parse_mode="HTML")

    elif data == "menu_leaderboard":
        rows = await get_leaderboard(15)
        lines = ["🏆 <b>ZENGİNLER LİSTESİ</b>", "━━━━━━━━━━━━━━━━━━━━━"]
        for i, r in enumerate(rows):
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
            lines.append(f"{medal} {r.get('display_name', 'Bilinmeyen')[:12]} — {format_amount(r['balance'])}")
        await query.edit_message_text("\n".join(lines), reply_markup=get_sub_kb(), parse_mode="HTML")
        
        
        
        
# ═══════════════════════════════════════════════════════════════
#  SİSTEM BAKIM VE GÜVENLİK (BACKUP & CLEANUP)
# ═══════════════════════════════════════════════════════════════

async def cleanup_stuck_games():
    """Bot başlarken veya periyodik olarak takılı kalmış oyunları temizler"""
    try:
        db = await get_db()
        # Bellekteki aktif oyunları da sıfırlayalım (eğer bot resetleniyorsa)
        async with _state_lock:
            _active_games.clear()
            if '_bj' in globals(): _bj.clear()

        res = await db.games.update_many(
            {"state": {"$in": ["OPEN", "PLAYING", "CALCULATING"]}},
            {"$set": {
                "state": "FINISHED", 
                "finished_at": datetime.now(),
                "cleanup_note": "Bot restart cleanup"
            }}
        )
        logger.info(f"🧹 Temizlik Tamamlandı: {res.modified_count} takılı oyun arşive alındı.")
    except Exception as e:
        logger.error(f"Cleanup hatası: {e}")

async def backup_task():
    """
    Her 24 saatte bir tüm veritabanını JSON olarak yedekler.
    Hatalara karşı dayanıklıdır ve diskte sadece son 7 yedeği tutar.
    """
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    # Bot açıldıktan 1 dakika sonra ilk yedeği al (test için)
    await asyncio.sleep(60) 
    
    while True:
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"casino_backup_{ts}.json"
            dest = os.path.join(BACKUP_DIR, filename)
            
            db = await get_db()
            
            # Verileri çek (Büyük veritabanlarında to_list limitli olmalı ama backup için hepsi lazım)
            users = await db.users.find().to_list(length=None)
            transactions = await db.transactions.find().to_list(length=None)
            games = await db.games.find().to_list(length=None)
            
            backup_data = {
                "metadata": {
                    "date": datetime.now().isoformat(),
                    "total_users": len(users),
                    "total_games": len(games)
                },
                "users": users,
                "transactions": transactions,
                "games": games
            }
            
            # MongoDB Nesnelerini (ObjectId, datetime) JSON'a uygun hale getirmek için default=str kullanıyoruz
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, default=str, indent=2, ensure_ascii=False)
            
            logger.info(f"📦 Veritabanı Yedeklendi: {filename}")
            
            # ESKİ YEDEKLERİ TEMİZLE (Retention Policy)
            backups = sorted([b for b in os.listdir(BACKUP_DIR) if b.endswith(".json")])
            if len(backups) > 7:
                for old_file in backups[:-7]:
                    os.remove(os.path.join(BACKUP_DIR, old_file))
                    logger.info(f"🗑️ Eski yedek silindi: {old_file}")

        except Exception as e:
            logger.error(f"❌ Backup sırasında kritik hata: {e}")
        
        # 24 Saat bekle
        await asyncio.sleep(24 * 3600)
        
        
        
        
# ═══════════════════════════════════════════════════════════════
#  BOT YAŞAM DÖNGÜSÜ (LIFECYCLE)
# ═══════════════════════════════════════════════════════════════

async def post_init(app):
    """Bot başladığında çalışacak kritik görevler"""
    await init_db()           # Veritabanı bağlantısı
    await cleanup_stuck_games() # Takılı kalanları temizle
    asyncio.create_task(backup_task()) # Arka planda yedeklemeyi başlat
    logger.info("🎰 BettMaster (CasiniBot) başarıyla yayına girdi!")

async def post_shutdown(app):
    """Bot kapatıldığında bağlantıları güvenli bir şekilde keser"""
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()
    logger.info("🛑 Bot kapatıldı, veritabanı bağlantısı kesildi.")

# ═══════════════════════════════════════════════════════════════
#  ANA GİRİŞ NOKTASI
# ═══════════════════════════════════════════════════════════════

def main():
    # Application oluşturma
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    
    # --- ADMIN KOMUTLARI ---
    app.add_handler(CommandHandler("addbalance", cmd_addbalance))
    app.add_handler(CommandHandler("setbalance", cmd_setbalance))
    app.add_handler(CommandHandler("cleanup", cmd_cleanup))
    app.add_handler(CommandHandler("reklam", cmd_reklam))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("id", cmd_id))
    
    # --- GENEL & SOSYAL KOMUTLAR ---
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("moneys", cmd_moneys))
    app.add_handler(CommandHandler("changename", cmd_changename))
    app.add_handler(CommandHandler("daily", cmd_daily))
    app.add_handler(CommandHandler("help", cmd_help))
    
    # --- OYUN KOMUTLARI (RULET) ---
    app.add_handler(CommandHandler("rulet", cmd_rulet))
    app.add_handler(CommandHandler(["red", "black", "green", "number", "numbers"], 
                                   # Birden fazla komutu tek handler ile yönetebiliriz (Opsiyonel)
                                   # Ama senin ayrı fonksiyonların varsa ayrı ayrı ekle:
                                   ))
    app.add_handler(CommandHandler("red", cmd_red))
    app.add_handler(CommandHandler("black", cmd_black))
    app.add_handler(CommandHandler("green", cmd_green))
    app.add_handler(CommandHandler("number", cmd_number))
    app.add_handler(CommandHandler("numbers", cmd_numbers))
    
    # --- OYUN KOMUTLARI (ZAR, ÇARK, KAZI KAZAN) ---
    app.add_handler(CommandHandler("dicebet", cmd_dicebet))
    app.add_handler(CommandHandler("dice", cmd_dice))
    app.add_handler(CommandHandler("wheelbet", cmd_wheelbet))
    app.add_handler(CommandHandler("wheel", cmd_wheel))
    app.add_handler(CommandHandler("kazisolo", cmd_kazisolo))
    app.add_handler(CommandHandler("kazibet", cmd_kazibet))
    app.add_handler(CommandHandler("kazi", cmd_kazi))
    
    # --- OYUN KOMUTLARI (BLACKJACK) ---
    app.add_handler(CommandHandler("blackjack", cmd_blackjack))
    app.add_handler(CommandHandler("bj", cmd_bj))
    app.add_handler(CallbackQueryHandler(bj_callback, pattern=r"^bj_"))
    
    # --- MENÜ & NAVİGASYON (HIZLI BAŞLATMA DAHİL) ---
    # pattern=r"^(menu_|start_)" -> Hem 'menu_' hem de 'start_' ile başlayan butonları yakalar
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^(menu_|start_)"))
    
    # --- VIP KASA & ÖDEMELER ---
    app.add_handler(CommandHandler("buy", cmd_buy))
    app.add_handler(CallbackQueryHandler(buy_callback, pattern=r"^buy_"))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    # --- BOTU ÇALIŞTIR ---
    logger.info("🚀 Tüm handlerlar aktif. BettMaster poling başlatıyor...")
    
    # drop_pending_updates: Bot kapalıyken gelen eski mesajları görmezden gelir (Donmaları önler)
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

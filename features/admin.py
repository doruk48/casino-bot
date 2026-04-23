# features/admin.py - Admin Komutları
import asyncio
from datetime import datetime
from bson.decimal128 import Decimal128
from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_IDS, DATABASE_NAME
from core.database import get_db
from core.economy import add_balance, get_balance
from core.users import get_user
from utils.format import format_amount, parse_amount, logger
from core.state import _state_lock, _active_games

async def cmd_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    
    message = f"🆔 <b>Kullanıcı ID:</b> <code>{user.id}</code>\n"
    message += f"👤 İsim: {user.full_name}\n"
    
    if chat.type in ["group", "supergroup"]:
        message += f"\n💬 <b>Grup ID:</b> <code>{chat.id}</code>\n"
        message += f"📌 Grup Adı: {chat.title}"
    
    await update.message.reply_text(message, parse_mode="HTML")

async def cmd_addbalance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
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
    
    amount, err = parse_amount(amount_str, float('inf'))
    if err:
        await update.message.reply_text(f"❌ {err}")
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
        amount_str = args[1]
    except:
        await update.message.reply_text("❌ Geçersiz kullanıcı ID'si!")
        return
    
    amount, err = parse_amount(amount_str, float('inf'))
    if err:
        await update.message.reply_text(f"❌ {err}")
        return
    
    if amount < 0:
        await update.message.reply_text("❌ Miktar 0'dan küçük olamaz!")
        return
    
    try:
        dec_amount = Decimal128(str(amount))
    except:
        await update.message.reply_text("❌ Geçersiz miktar!")
        return
    
    db = await get_db()
    await db.users.update_one(
        {"telegram_id": target_id},
        {"$set": {"balance": dec_amount, "updated_at": datetime.now()}}
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
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Bu komutu kullanma yetkiniz yok!")
        return
    
    async with _state_lock:
        _active_games.clear()
    
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

# features/transfer.py - Para Transferi
from datetime import datetime
from bson.decimal128 import Decimal128
from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_IDS
from core.database import get_db
from core.economy import get_balance, _get_lock
from core.users import get_or_create_user, get_user
from utils.format import format_amount, parse_amount, logger
from utils.helpers import clean_name
from utils.images import create_transfer_image
from core.state import is_rate_limited

async def cmd_moneys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
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
    
    try:
        dec_amount = Decimal128(str(amount))
        dec_negative = Decimal128("-" + str(amount))
    except Exception as e:
        logger.error(f"Decimal128 dönüşüm hatası: {e}")
        await update.message.reply_text("❌ Geçersiz miktar!")
        return
    
    await db.users.update_one(
        {"telegram_id": user.id},
        {"$inc": {"balance": dec_negative}}
    )
    await db.users.update_one(
        {"telegram_id": target.id},
        {"$inc": {"balance": dec_amount}}
    )
    
    await db.transactions.insert_one({
        "from_id": user.id,
        "to_id": target.id,
        "amount": dec_amount,
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

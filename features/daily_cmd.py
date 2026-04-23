# features/daily_cmd.py - Günlük Bonus Komutu
from datetime import datetime
from bson.decimal128 import Decimal128
from telegram import Update
from telegram.ext import ContextTypes

from core.database import get_db
from core.users import get_or_create_user, get_user
from core.economy import get_balance, _get_lock
from core.daily import get_daily_bonus, can_claim_daily
from core.state import is_rate_limited
from utils.format import format_amount

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
            {"$inc": {"balance": Decimal128(str(bonus_amount))},
             "$set": {"last_daily": datetime.now().isoformat(), "daily_streak": new_streak, "updated_at": datetime.now()}}
        )
        
        await db.transactions.insert_one({
            "to_id": user.id,
            "amount": Decimal128(str(bonus_amount)),
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

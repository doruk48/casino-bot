# features/balance.py - Bakiye Sorgulama
from telegram import Update
from telegram.ext import ContextTypes
from bson.decimal128 import Decimal128
from decimal import Decimal

from core.database import get_db
from core.users import get_user
from core.state import is_rate_limited
from utils.format import format_amount
from utils.helpers import get_level

async def cmd_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_rate_limited(user.id):
        return
    
    u = await get_user(user.id)
    if not u:
        await update.message.reply_text("❌ Kullanıcı bulunamadı. /start yazın.")
        return
    
    db = await get_db()
    
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
    
    lvl, emoji = get_level(current_balance)
    balance = format_amount(u['balance'])
    
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

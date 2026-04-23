# features/leaderboard_cmd.py - Liderlik Tablosu Komutu
from telegram import Update
from telegram.ext import ContextTypes

from config import LEADERBOARD_SIZE
from core.leaderboard import get_leaderboard
from core.state import is_rate_limited
from utils.format import format_amount
from utils.helpers import get_level

async def cmd_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if is_rate_limited(update.effective_user.id):
        return
    
    rows = await get_leaderboard(LEADERBOARD_SIZE)
    
    chat = update.effective_chat
    if chat.type in ["group", "supergroup"]:
        group_name = chat.title
    else:
        group_name = "Casino Bot"
    
    lines = [f"🏆 <b>{group_name}</b> En Zengin {LEADERBOARD_SIZE} Kullanıcı 🏆", ""]
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

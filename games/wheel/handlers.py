# games/wheel/handlers.py - Çarkıfelek Komutları
import asyncio
from telegram import Update
from telegram.ext import ContextTypes

from config import BET_WINDOW
from core.state import can_open_game, create_game, is_rate_limited, _state_lock, _active_games
from core.users import get_or_create_user
from core.economy import get_balance, remove_balance
from utils.format import format_amount, parse_amount
from games.wheel.engine import _wheel_timer

async def cmd_wheelbet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if is_rate_limited(user.id):
        return
    
    ok, err = await can_open_game(chat_id, "wheel")
    if not ok:
        await update.message.reply_text(f"❌ {err}")
        return
    
    game = await create_game(chat_id, "wheel", 0)
    gid = game["game_id"]
    
    msg = await update.message.reply_text(
        f"🎡 <b>ÇARKIFELEK BAŞLADI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 GAME ID: {gid}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>{BET_WINDOW} saniye</b> içinde bahis yapın!\n\n"
        f"📌 /wheel &lt;miktar&gt; veya /wheel allin\n\n"
        f"💀 PASS | 🔄 İADE | 2x | 3x | 5x | 10x | 15x | 25x | 50x | 100x | 🎰 JACKPOT",
        parse_mode="HTML"
    )
    
    async with _state_lock:
        if chat_id in _active_games and gid in _active_games[chat_id]:
            _active_games[chat_id][gid]["message_id"] = msg.message_id
    
    asyncio.create_task(_wheel_timer(ctx, chat_id, gid))

async def cmd_wheel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
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
    
    from core.state import get_active_game, add_participant, get_participants
    game = await get_active_game(chat_id, "wheel")
    if not game or game["state"] != "OPEN":
        await update.message.reply_text("❌ Açık çarkıfelek yok veya süre doldu.")
        return
    
    ok = await remove_balance(user.id, amount, "bet", f"Çark game:{game['game_id']}")
    if not ok:
        await update.message.reply_text("❌ Yetersiz bakiye.")
        return
    
    bd = {"type": "wheel", "name": user.full_name}
    await add_participant(chat_id, game["game_id"], user.id, amount, bd)
    
    parts = await get_participants(chat_id, game["game_id"])
    user_bets = parts.get(user.id, {}).get("bets", [])
    total_bet = sum(b["bet"] for b in user_bets)
    
    try:
        formatted_amount = format_amount(amount)
    except:
        formatted_amount = f"{amount}🪙BTK"
    
    try:
        formatted_total = format_amount(total_bet)
    except:
        formatted_total = f"{total_bet}🪙BTK"
    
    await update.message.reply_text(
        f"🕹 <b>{user.full_name}</b> 🎡 {formatted_amount} bahis yaptı\n"
        f"💰 Bu oyunda toplam bahsiniz: {formatted_total}",
        parse_mode="HTML"
    )

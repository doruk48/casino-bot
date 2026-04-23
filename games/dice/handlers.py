# games/dice/handlers.py - Zar Oyunu Komutları
from telegram import Update
from telegram.ext import ContextTypes

from config import BET_WINDOW
from core.state import can_open_game, create_game, is_rate_limited, _state_lock, _active_games
from core.users import get_or_create_user
from core.economy import get_balance, remove_balance
from utils.format import format_amount, parse_amount
from games.dice.engine import _dice_bet_timer
import asyncio

async def cmd_dicebet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
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
                "current_msg_id": None,
                "current_index": 0
            }
    
    asyncio.create_task(_dice_bet_timer(ctx, chat_id, gid))

async def cmd_dice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
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
    
    from core.state import get_active_game
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
                
                try:
                    formatted_amount = format_amount(amount)
                except:
                    formatted_amount = f"{amount}🪙BTK"
                
                try:
                    formatted_total = format_amount(total_bet)
                except:
                    formatted_total = f"{total_bet}🪙BTK"
                
                await update.message.reply_text(
                    f"🕹 <b>{user.full_name}</b> 🎲 +{formatted_amount} "
                    f"(Toplam: {formatted_total})",
                    parse_mode="HTML"
                )
            else:
                game_data["players_data"][user.id] = {"bet": amount, "name": user.full_name}
                
                try:
                    formatted_amount = format_amount(amount)
                except:
                    formatted_amount = f"{amount}🪙BTK"
                
                await update.message.reply_text(
                    f"🕹 <b>{user.full_name}</b> 🎲 {formatted_amount} katıldı!",
                    parse_mode="HTML"
                )
            game_data["pool"] = game_data.get("pool", 0) + amount

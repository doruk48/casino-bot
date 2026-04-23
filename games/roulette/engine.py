# games/roulette/engine.py - Rulet Oyun Mantığı
import asyncio
import random
import os
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from config import BET_WINDOW, ROULETTE_MULTIPLIERS, ROUL_COLORS, ROUL_EMOJI, BASE_DIR
from core.state import get_active_game, finish_game, cleanup, add_participant, get_participants
from core.economy import add_balance
from core.stats import update_stats, update_win_rate
from utils.format import format_amount, logger
from games.roulette.visuals import format_number_with_emoji, get_rank_emoji, get_roulette_image

async def _roulette_timer(ctx, chat_id, game_id, msg):
    await asyncio.sleep(BET_WINDOW)
    
    game = await get_active_game(chat_id, "roulette")
    if not game or game["game_id"] != game_id:
        return
    
    game["state"] = "CALCULATING"
    
    winning = random.randint(0, 36)
    color = ROUL_COLORS[winning]
    color_emoji = ROUL_EMOJI[color]
    
    try:
        await ctx.bot.delete_message(chat_id, msg.message_id)
    except BadRequest:
        pass
    
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
    
    result_text = f"🆔 GAME ID: {game_id}\n\n"
    result_text += f"🏆 Kazanan Sayı 🔘 {format_number_with_emoji(winning)} {color_emoji}!\n\n"
    result_text += f"🏧 Kazanan Kişiler 🔘\n"
    
    if winners:
        winners.sort(key=lambda x: x["payout"], reverse=True)
        
        for i, w in enumerate(winners[:15], 1):
            rank_emoji = get_rank_emoji(i)
            result_text += f" {rank_emoji} {w['name']} {color_emoji} {format_amount(w['payout'])}\n"
    else:
        result_text += " 💀 Kazanan olmadı!\n"
    
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
    
    await finish_game(chat_id, game_id, str(winning), ctx)
    await cleanup(chat_id)

async def _rulet_bet(update: Update, bet_type: str, color=None, numbers=None, amount_str="0"):
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    from core.state import is_rate_limited
    if is_rate_limited(user.id):
        return
    
    from core.users import get_or_create_user
    from core.economy import get_balance, remove_balance
    
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
    
    if bet_type == "color":
        bd = {"type": "color", "color": color, "name": user.full_name}
        color_emoji = {"red": "🔴", "black": "⚫", "green": "🟢"}.get(color, "🔵")
    else:
        bd = {"type": "number", "numbers": numbers or [], "name": user.full_name}
        color_emoji = "🔵"
    
    await add_participant(chat_id, game["game_id"], user.id, amount, bd)
    
    parts = await get_participants(chat_id, game["game_id"])
    user_bets = parts.get(user.id, {}).get("bets", [])
    total_bet = sum(b["bet"] for b in user_bets)
    
    try:
        formatted = format_amount(amount)
    except:
        formatted = f"{amount}🪙BTK"
    
    await update.message.reply_text(
        f"🕹 <b>{user.full_name}</b> {color_emoji} {formatted} bahis yaptı",
        parse_mode="HTML"
    )

from utils.format import parse_amount

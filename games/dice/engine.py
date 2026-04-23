# games/dice/engine.py - Zar Oyunu Mantığı
import asyncio
import random
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes

from config import BET_WINDOW, BLACKJACK_TURN
from core.state import get_active_game, finish_game, cleanup, _state_lock, _active_games
from core.economy import add_balance
from core.stats import update_stats, update_win_rate
from utils.format import format_amount, logger
from utils.images import create_dice_image, combine_dice_with_total

def _dice_kb(game_id: str, roll_num: int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"🎲 {roll_num}. Zarı At", callback_data=f"dice_roll:{game_id}")
    ]])

# ═══════════════════════════════════════════════════════════════
#  BAHİS ZAMANLAYICISI
# ═══════════════════════════════════════════════════════════════
async def _dice_bet_timer(ctx, chat_id, game_id):
    await asyncio.sleep(BET_WINDOW)
    
    game = await get_active_game(chat_id, "dice")
    if not game or game["game_id"] != game_id:
        return
    
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data:
            return
        players = game_data.get("players_data", {}).copy()
        pool = game_data.get("pool", 0)
    
    if len(players) < 2:
        for uid, data in players.items():
            await add_balance(uid, data["bet"], "refund", f"Zar iade game:{game_id}")
        await ctx.bot.send_message(
            chat_id,
            f"❌ <b>Zar oyunu iptal!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"En az 2 oyuncu gerekli. Bahisler iade edildi.",
            parse_mode="HTML"
        )
        await finish_game(chat_id, game_id, "iptal", ctx)
        await cleanup(chat_id)
        return
    
    game["state"] = "ROLLING"
    
    async with _state_lock:
        if chat_id in _active_games and game_id in _active_games[chat_id]:
            _active_games[chat_id][game_id]["order"] = list(players.keys())
            _active_games[chat_id][game_id]["players_rolled"] = {}
            _active_games[chat_id][game_id]["pool"] = pool
            _active_games[chat_id][game_id]["dice_state"]["current_index"] = 0
    
    await ctx.bot.send_message(
        chat_id,
        f"🎲 <b>BAHİS SÜRESİ DOLDU!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Oyuncu sayısı: {len(players)}\n"
        f"💰 Havuz: {format_amount(pool)}\n\n"
        f"🎯 Sırayla zar atılacak...",
        parse_mode="HTML"
    )
    
    await _dice_start_next_player(ctx, chat_id, game_id)

# ═══════════════════════════════════════════════════════════════
#  SIRADAKİ OYUNCU
# ═══════════════════════════════════════════════════════════════
async def _dice_start_next_player(ctx, chat_id, game_id):
    game = await get_active_game(chat_id, "dice")
    if not game or game["game_id"] != game_id:
        return
    
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data:
            return
        
        idx = game_data["dice_state"]["current_index"]
        order = game_data["order"]
        players_data = game_data["players_data"]
    
    if idx >= len(order):
        await _dice_calculate_results(ctx, chat_id, game_id)
        return
    
    uid = order[idx]
    player_name = players_data[uid]["name"]
    player_bet = players_data[uid]["bet"]
    
    async with _state_lock:
        if chat_id in _active_games and game_id in _active_games[chat_id]:
            _active_games[chat_id][game_id]["dice_state"]["current_player"] = uid
            _active_games[chat_id][game_id]["dice_state"]["roll_count"] = 0
            _active_games[chat_id][game_id]["dice_state"]["dice1"] = None
            _active_games[chat_id][game_id]["dice_state"]["dice2"] = None
            _active_games[chat_id][game_id]["dice_state"]["task"] = None
    
    msg = await ctx.bot.send_message(
        chat_id,
        f"🎲 <b>SIRA SENDE - {player_name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Bahsin: {format_amount(player_bet)}\n"
        f"🎯 1. zarı at!\n\n"
        f"⏳ {BLACKJACK_TURN} saniye içinde butona tıkla!",
        reply_markup=_dice_kb(game_id, 1),
        parse_mode="HTML"
    )
    
    async with _state_lock:
        if chat_id in _active_games and game_id in _active_games[chat_id]:
            _active_games[chat_id][game_id]["dice_state"]["current_msg_id"] = msg.message_id
    
    task = asyncio.create_task(_dice_timeout(ctx, chat_id, game_id, uid))
    async with _state_lock:
        if chat_id in _active_games and game_id in _active_games[chat_id]:
            _active_games[chat_id][game_id]["dice_state"]["task"] = task

# ═══════════════════════════════════════════════════════════════
#  ZAMAN AŞIMI
# ═══════════════════════════════════════════════════════════════
async def _dice_timeout(ctx, chat_id, game_id, uid):
    await asyncio.sleep(BLACKJACK_TURN)
    
    game = await get_active_game(chat_id, "dice")
    if not game or game["game_id"] != game_id:
        return
    
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data:
            return
        current_player = game_data["dice_state"]["current_player"]
    
    if current_player != uid:
        return
    
    await _dice_auto_roll(ctx, chat_id, game_id, uid)

# ═══════════════════════════════════════════════════════════════
#  OTOMATİK ZAR ATMA
# ═══════════════════════════════════════════════════════════════
async def _dice_auto_roll(ctx, chat_id, game_id, uid):
    game = await get_active_game(chat_id, "dice")
    if not game:
        return
    
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data:
            return
        
        dice_state = game_data["dice_state"]
        roll_count = dice_state["roll_count"]
        dice1 = dice_state["dice1"]
        msg_id = dice_state["current_msg_id"]
        players_data = game_data["players_data"]
        player_name = players_data[uid]["name"]
        player_bet = players_data[uid]["bet"]
    
    if roll_count == 0:
        dice1 = random.randint(1, 6)
        dice_img = create_dice_image(dice1)
        
        try:
            await ctx.bot.delete_message(chat_id, msg_id)
        except:
            pass
        
        msg = await ctx.bot.send_photo(
            chat_id,
            photo=dice_img,
            caption=f"🎲 <b>SIRA SENDE - {player_name}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 Bahsin: {format_amount(player_bet)}\n"
                    f"🎲 1. Zar: {dice1} (otomatik)\n"
                    f"🎯 2. zarı at!\n\n"
                    f"⏳ {BLACKJACK_TURN} saniye içinde butona tıkla!",
            reply_markup=_dice_kb(game_id, 2),
            parse_mode="HTML"
        )
        
        async with _state_lock:
            if chat_id in _active_games and game_id in _active_games[chat_id]:
                _active_games[chat_id][game_id]["dice_state"]["roll_count"] = 1
                _active_games[chat_id][game_id]["dice_state"]["dice1"] = dice1
                _active_games[chat_id][game_id]["dice_state"]["current_msg_id"] = msg.message_id
                if dice_state.get("task"):
                    dice_state["task"].cancel()
                new_task = asyncio.create_task(_dice_timeout(ctx, chat_id, game_id, uid))
                _active_games[chat_id][game_id]["dice_state"]["task"] = new_task
        
    else:
        dice2 = random.randint(1, 6)
        combined_img = combine_dice_with_total(dice1, dice2)
        total = dice1 + dice2
        
        try:
            await ctx.bot.delete_message(chat_id, msg_id)
        except:
            pass
        
        await ctx.bot.send_photo(
            chat_id,
            photo=combined_img,
            caption=f"🎲 <b>{player_name} - SONUÇ</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🎲 Zarlar: {dice1} + {dice2} = {total} (otomatik)\n"
                    f"✅ Tamamlandı!\n\n"
                    f"⏳ Sıradaki oyuncuya geçiliyor...",
            parse_mode="HTML"
        )
        
        async with _state_lock:
            if chat_id in _active_games and game_id in _active_games[chat_id]:
                _active_games[chat_id][game_id]["players_rolled"][uid] = {
                    "total": total, "dice1": dice1, "dice2": dice2,
                    "name": player_name, "bet": player_bet
                }
                _active_games[chat_id][game_id]["dice_state"]["current_index"] += 1
                _active_games[chat_id][game_id]["dice_state"]["current_player"] = None
                _active_games[chat_id][game_id]["dice_state"]["roll_count"] = 0
                _active_games[chat_id][game_id]["dice_state"]["dice1"] = None
                _active_games[chat_id][game_id]["dice_state"]["dice2"] = None
                if dice_state.get("task"):
                    dice_state["task"].cancel()
        
        await asyncio.sleep(2)
        await _dice_start_next_player(ctx, chat_id, game_id)

# ═══════════════════════════════════════════════════════════════
#  ZAR ATMA CALLBACK
# ═══════════════════════════════════════════════════════════════
async def dice_callback(update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        action, game_id = query.data.split(":", 1)
    except:
        await query.answer("Hata!", show_alert=True)
        return
    
    user = query.from_user
    chat_id = query.message.chat_id
    
    game = await get_active_game(chat_id, "dice")
    if not game or game["game_id"] != game_id:
        await query.answer("Oyun bitti.", show_alert=True)
        return
    
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data:
            await query.answer("Oyun bulunamadı.", show_alert=True)
            return
        
        current_player = game_data["dice_state"]["current_player"]
    
    if current_player != user.id:
        await query.answer("Şu an sıra sende değil!", show_alert=True)
        return
    
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data:
            return
        
        dice_state = game_data["dice_state"]
        roll_count = dice_state["roll_count"]
        dice1 = dice_state["dice1"]
        players_data = game_data["players_data"]
        player_name = players_data[user.id]["name"]
        player_bet = players_data[user.id]["bet"]
        
        if dice_state.get("task"):
            dice_state["task"].cancel()
    
    if roll_count == 0:
        dice1 = random.randint(1, 6)
        dice_img = create_dice_image(dice1)
        
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=dice_img,
                caption=f"🎲 <b>SIRA SENDE - {player_name}</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"💰 Bahsin: {format_amount(player_bet)}\n"
                        f"🎲 1. Zar: {dice1}\n"
                        f"🎯 2. zarı at!\n\n"
                        f"⏳ {BLACKJACK_TURN} saniye içinde butona tıkla!",
                parse_mode="HTML"
            ),
            reply_markup=_dice_kb(game_id, 2)
        )
        
        async with _state_lock:
            if chat_id in _active_games and game_id in _active_games[chat_id]:
                _active_games[chat_id][game_id]["dice_state"]["roll_count"] = 1
                _active_games[chat_id][game_id]["dice_state"]["dice1"] = dice1
                new_task = asyncio.create_task(_dice_timeout(ctx, chat_id, game_id, user.id))
                _active_games[chat_id][game_id]["dice_state"]["task"] = new_task
        
    else:
        dice2 = random.randint(1, 6)
        combined_img = combine_dice_with_total(dice1, dice2)
        total = dice1 + dice2
        
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=combined_img,
                caption=f"🎲 <b>{player_name} - SONUÇ</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🎲 Zarlar: {dice1} + {dice2} = {total}\n"
                        f"✅ Tamamlandı!\n\n"
                        f"⏳ Sıradaki oyuncuya geçiliyor...",
                parse_mode="HTML"
            )
        )
        
        async with _state_lock:
            if chat_id in _active_games and game_id in _active_games[chat_id]:
                _active_games[chat_id][game_id]["players_rolled"][user.id] = {
                    "total": total, "dice1": dice1, "dice2": dice2,
                    "name": player_name, "bet": player_bet
                }
                _active_games[chat_id][game_id]["dice_state"]["current_index"] += 1
                _active_games[chat_id][game_id]["dice_state"]["current_player"] = None
                _active_games[chat_id][game_id]["dice_state"]["roll_count"] = 0
                _active_games[chat_id][game_id]["dice_state"]["dice1"] = None
                _active_games[chat_id][game_id]["dice_state"]["dice2"] = None
        
        await asyncio.sleep(2)
        await _dice_start_next_player(ctx, chat_id, game_id)

# ═══════════════════════════════════════════════════════════════
#  SONUÇ HESAPLAMA
# ═══════════════════════════════════════════════════════════════
async def _dice_calculate_results(ctx, chat_id, game_id):
    game = await get_active_game(chat_id, "dice")
    if not game or game["game_id"] != game_id:
        return
    
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data:
            return
        players = game_data["players_rolled"]
        pool = game_data["pool"]
    
    max_score = max(p["total"] for p in players.values())
    winners = [(uid, data) for uid, data in players.items() if data["total"] == max_score]
    
    prize_per_winner = pool // len(winners)
    remaining = pool - (prize_per_winner * len(winners))
    
    results = [
        f"🆔 GAME ID: {game_id}\n",
        f"🎲 <b>ZAR OYUNU SONUÇLARI</b>",
        f"━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    for uid, data in players.items():
        results.append(f"🎲 {data['name']}: {data['dice1']} + {data['dice2']} = {data['total']}")
    
    results.append("━━━━━━━━━━━━━━━━━━━━━")
    
    if len(winners) == 1:
        uid, data = winners[0]
        payout = prize_per_winner + remaining
        await add_balance(uid, payout, "win", f"Zar game:{game_id}")
        await update_stats(uid, payout)
        await update_win_rate(uid, "dice", True)
        
        results.append(f"🏆 <b>KAZANAN: {data['name']}</b>")
        results.append(f"💰 Kazanç: {format_amount(payout)}")
        
        for uid2 in players.keys():
            if uid2 != uid:
                await update_win_rate(uid2, "dice", False)
    else:
        results.append(f"🤝 <b>BERABERLİK! {len(winners)} kazanan</b>")
        for uid, data in winners:
            await add_balance(uid, prize_per_winner, "win", f"Zar game:{game_id}")
            await update_stats(uid, prize_per_winner)
            await update_win_rate(uid, "dice", True)
            results.append(f"💰 {data['name']}: +{format_amount(prize_per_winner)}")
        
        for uid2 in players.keys():
            if uid2 not in [w[0] for w in winners]:
                await update_win_rate(uid2, "dice", False)
        
        if remaining > 0:
            results.append(f"📦 Kalan: {format_amount(remaining)} (sistemde kaldı)")
    
    results.append("━━━━━━━━━━━━━━━━━━━━━")
    results.append("✨ Yeni oyun için /dicebet")
    
    await ctx.bot.send_message(chat_id, "\n".join(results), parse_mode="HTML")
    await finish_game(chat_id, game_id, f"kazanan:{len(winners)}", ctx)
    await cleanup(chat_id)

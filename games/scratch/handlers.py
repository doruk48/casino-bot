# games/scratch/handlers.py - Kazı Kazan Komutları (Solo + Turnuva)
import asyncio
import os
import secrets
from collections import Counter
from telegram import Update
from telegram.ext import ContextTypes

from config import BET_WINDOW, BASE_DIR, SCRATCH_POOL
from core.state import can_open_game, create_game, is_rate_limited, _state_lock, _active_games
from core.users import get_or_create_user
from core.economy import get_balance, remove_balance, add_balance
from core.stats import update_stats, update_win_rate
from utils.format import format_amount, parse_amount, logger
from utils.images import create_scratch_result_image
from games.scratch.engine import _scratch_countdown, _scratch_tournament_timer

# ═══════════════════════════════════════════════════════════════
#  SOLO KAZI KAZAN
# ═══════════════════════════════════════════════════════════════
async def cmd_kazisolo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_rate_limited(user.id):
        return
    
    if not ctx.args:
        await update.message.reply_text(
            "🎟 <b>KAZI KAZAN (SOLO)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "📌 Kullanım: <code>/kazisolo &lt;miktar&gt;</code>\n"
            "veya <code>/kazisolo allin</code>\n\n"
            "🏆 3 aynı çarpan = KAZANÇ!",
            parse_mode="HTML"
        )
        return
    
    await get_or_create_user(user.id, user.username, user.full_name)
    bal = await get_balance(user.id)
    amount, err = parse_amount(ctx.args[0], bal)
    if err:
        await update.message.reply_text(f"❌ {err}")
        return
    
    ok = await remove_balance(user.id, amount, "bet", "Kazı Kazan Solo")
    if not ok:
        await update.message.reply_text("❌ Yetersiz bakiye.")
        return
    
    kapali_kart = os.path.join(BASE_DIR, "Kapali.jpg")
    if os.path.exists(kapali_kart):
        with open(kapali_kart, "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=f"🎟 <b>KAZI KAZAN (SOLO)</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"💰 Bahis: {format_amount(amount)}\n"
                        f"✨ KAZIYORSUN... ✨",
                parse_mode="HTML"
            )
    else:
        await update.message.reply_text(
            f"🎟 <b>KAZI KAZAN (SOLO)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Bahis: {format_amount(amount)}\n"
            f"✨ KAZIYORSUN... ✨",
            parse_mode="HTML"
        )
    
    await asyncio.sleep(1.5)
    
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
            msg = f"✅ <b>{winner_mult}x</b> bulundu!\n🎉 KAZANDIN! +{format_amount(payout - amount)}"
            await update_win_rate(user.id, "scratch", True)
        else:
            await update_stats(user.id, 0)
            msg = f"❌ Eşleşme yok!\n💀 KAYBETTİN! -{format_amount(amount)}"
            await update_win_rate(user.id, "scratch", False)
        
        new_bal = await get_balance(user.id)
        
        await update.message.reply_photo(
            photo=result_img,
            caption=f"🎟 <b>KAZI KAZAN (SOLO)</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{msg}\n"
                    f"💳 Yeni bakiye: {format_amount(new_bal)}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Kazı Kazan görsel hatası: {e}")
        new_bal = await get_balance(user.id)
        if winner_mult > 0:
            await add_balance(user.id, payout, "win", f"Kazı Solo {winner_mult}x")
            await update_stats(user.id, payout)
            await update_win_rate(user.id, "scratch", True)
            await update.message.reply_text(
                f"🎟 <b>KAZI KAZAN (SOLO)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ {winner_mult}x bulundu!\n"
                f"🎉 KAZANDIN! +{format_amount(payout - amount)}\n"
                f"💳 Yeni bakiye: {format_amount(new_bal)}",
                parse_mode="HTML"
            )
        else:
            await update_stats(user.id, 0)
            await update_win_rate(user.id, "scratch", False)
            await update.message.reply_text(
                f"🎟 <b>KAZI KAZAN (SOLO)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"❌ Eşleşme yok!\n"
                f"💀 KAYBETTİN! -{format_amount(amount)}",
                parse_mode="HTML"
            )

# ═══════════════════════════════════════════════════════════════
#  TURNUVA KAZI KAZAN
# ═══════════════════════════════════════════════════════════════
async def cmd_kazibet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    if is_rate_limited(user.id):
        return
    
    ok, err = await can_open_game(chat_id, "scratch_tournament")
    if not ok:
        await update.message.reply_text(f"❌ {err}")
        return
    
    game = await create_game(chat_id, "scratch_tournament", 0)
    gid = game["game_id"]
    
    caption = (
        f"🎟 <b>KAZI KAZAN TURNUVASI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 GAME ID: {gid}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>{BET_WINDOW} saniye</b> içinde katıl!\n"
        f"📌 /kazi &lt;miktar&gt;\n"
        f"🎯 Herkes aynı kartı kazır!\n"
        f"🏆 3 aynı çarpan = HERKES KAZANIR!"
    )
    
    kapali_kart = os.path.join(BASE_DIR, "Kapali.jpg")
    if os.path.exists(kapali_kart):
        with open(kapali_kart, "rb") as photo:
            msg = await update.message.reply_photo(photo=photo, caption=caption, parse_mode="HTML")
    else:
        msg = await update.message.reply_text(caption, parse_mode="HTML")
    
    async with _state_lock:
        if chat_id in _active_games and gid in _active_games[chat_id]:
            _active_games[chat_id][gid]["message_id"] = msg.message_id
            _active_games[chat_id][gid]["min_bet"] = 0
            _active_games[chat_id][gid]["pool"] = 0
            _active_games[chat_id][gid]["players_data"] = {}
    
    asyncio.create_task(_scratch_countdown(ctx, chat_id, gid, msg.message_id))
    asyncio.create_task(_scratch_tournament_timer(ctx, chat_id, gid))

async def cmd_kazi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    if is_rate_limited(user.id):
        return
    
    if not ctx.args:
        await update.message.reply_text("❌ Kullanım: /kazi <miktar>")
        return
    
    from core.state import get_active_game
    game = await get_active_game(chat_id, "scratch_tournament")
    if not game or game["state"] != "OPEN":
        await update.message.reply_text("❌ Açık turnuva yok veya süre doldu.")
        return
    
    await get_or_create_user(user.id, user.username, user.full_name)
    bal = await get_balance(user.id)
    amount, err = parse_amount(ctx.args[0], bal)
    if err:
        await update.message.reply_text(f"❌ {err}")
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
    
    ok = await remove_balance(user.id, amount, "bet", f"Kazi Turnuva {game['game_id']}")
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
                    f"🕹 <b>{user.full_name}</b> 🎟️ +{formatted_amount} "
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
                    f"🕹 <b>{user.full_name}</b> 🎟️ {formatted_amount} ile katıldı!",
                    parse_mode="HTML"
                )
            game_data["pool"] = game_data.get("pool", 0) + amount

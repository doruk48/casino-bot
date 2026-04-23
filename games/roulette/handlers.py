# games/roulette/handlers.py - Rulet Komutları
import asyncio
import os
from telegram import Update
from telegram.ext import ContextTypes

from config import BET_WINDOW, BASE_DIR
from core.state import can_open_game, create_game, is_rate_limited
from games.roulette.engine import _roulette_timer, _rulet_bet

async def cmd_rulet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if is_rate_limited(user.id):
        return
    
    ok, err = await can_open_game(chat_id, "roulette")
    if not ok:
        await update.message.reply_text(f"❌ {err}")
        return
    
    game = await create_game(chat_id, "roulette", 0)
    game_id = game["game_id"]
    
    spin_img_path = os.path.join(BASE_DIR, "spin.jpg")
    caption = (
        f"🎰 <b>AVRUPA RULETİ BAŞLADI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 GAME ID: {game_id}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>{BET_WINDOW} saniye</b> içinde bahis yapın!\n\n"
        f"🔴 /red &lt;miktar&gt;\n"
        f"⚫ /black &lt;miktar&gt;\n"
        f"🟢 /green &lt;miktar&gt;\n"
        f"🔢 /number &lt;sayı 0-36&gt; &lt;miktar&gt;\n"
        f"🔢 /numbers &lt;1,2,3,...&gt; &lt;miktar&gt;"
    )
    
    try:
        if os.path.exists(spin_img_path):
            with open(spin_img_path, "rb") as photo:
                msg = await update.message.reply_photo(photo=photo, caption=caption, parse_mode="HTML")
        else:
            msg = await update.message.reply_text(caption, parse_mode="HTML")
    except Exception as e:
        from utils.format import logger
        logger.error(f"Spin görseli gönderilemedi: {e}")
        msg = await update.message.reply_text(caption, parse_mode="HTML")
    
    from core.state import _state_lock, _active_games
    async with _state_lock:
        if chat_id in _active_games and game_id in _active_games[chat_id]:
            _active_games[chat_id][game_id]["message_id"] = msg.message_id
    
    asyncio.create_task(_roulette_timer(ctx, chat_id, game_id, msg))

async def cmd_green(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("❌ Kullanım: /green <miktar>")
        return
    await _rulet_bet(update, "color", color="green", amount_str=ctx.args[0])

async def cmd_red(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("❌ Kullanım: /red <miktar>")
        return
    await _rulet_bet(update, "color", color="red", amount_str=ctx.args[0])

async def cmd_black(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("❌ Kullanım: /black <miktar>")
        return
    await _rulet_bet(update, "color", color="black", amount_str=ctx.args[0])

async def cmd_number(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("❌ Kullanım: /number <sayı> <miktar>")
        return
    try:
        n = int(ctx.args[0])
        if 0 <= n <= 36:
            await _rulet_bet(update, "number", numbers=[n], amount_str=ctx.args[1])
        else:
            await update.message.reply_text("❌ Geçersiz sayı (0-36).")
    except:
        await update.message.reply_text("❌ Geçersiz sayı (0-36).")

async def cmd_numbers(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("❌ Kullanım: /numbers <1,2,3> <miktar>")
        return
    try:
        nums = [int(x.strip()) for x in ctx.args[0].split(",")]
        if not all(0 <= n <= 36 for n in nums):
            await update.message.reply_text("❌ Sayılar 0-36 arasında olmalı.")
            return
        if len(nums) < 1:
            await update.message.reply_text("❌ En az 1 sayı belirtmelisiniz.")
            return
        await _rulet_bet(update, "number", numbers=nums, amount_str=ctx.args[1])
    except:
        await update.message.reply_text("❌ Geçersiz sayı listesi.")

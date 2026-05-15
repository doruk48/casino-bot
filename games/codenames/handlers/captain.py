"""
Kaptanın DM'den ipucu verdiği /cipucu komutu.
"""
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from ..engine import GameState, TeamColor, _active_games, set_game
from ..timers import cancel_timer, start_timer
from ..engine import _active_games

async def cipucu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kaptan sadece DM'den ipucu verir."""
    user = update.effective_user
    message = update.message

    # Aktif oyunda bu kullanıcı kaptan mı?
    game = None
    for g in _active_games.values():  # ← .values() ile düzelt
        if g.blue_captain == user.id or g.red_captain == user.id:
            game = g
            chat_id = g.chat_id
            break
    
    if not game:
        await message.reply_text("⚠️ Aktif bir oyunda kaptan değilsiniz.")
        return
    
    # ... devamı ...

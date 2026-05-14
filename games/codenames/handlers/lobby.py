"""
Lobi komutları: /cstart, /cjoin, /ciptal
"""
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from ..engine import (
    GameRoom, GameState, generate_game_id,
    get_game, set_game, remove_game
)
from .messages import update_lobby_message


async def cstart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yeni bir Codenames lobisi açar."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    existing = await get_game(chat_id)
    if existing:
        await update.message.reply_text("⚠️ Bu grupta zaten bir oyun var.")
        return

    game = GameRoom(
        game_id=generate_game_id(),
        chat_id=chat_id,
        host_id=user.id
    )
    game.add_player(user.id, user.first_name, user.username)
    await set_game(chat_id, game)

    msg = await update.message.reply_text(
        await update_lobby_message(game, context),
        reply_markup=build_lobby_keyboard(game),
        parse_mode=ParseMode.HTML
    )
    game.lobby_msg_id = msg.message_id
    await set_game(chat_id, game)


async def cjoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lobiye katıl."""
    # ... (önceki handlers.py'deki cjoin kodu)
    pass


async def ciptal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lobiyi iptal et."""
    # ... (önceki handlers.py'deki ciptal kodu)
    pass

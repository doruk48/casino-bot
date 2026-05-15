"""
Lobi komutları: /cstart, /cjoin, /ciptal
"""
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from ..engine import (
    GameRoom, GameState,
    get_game, set_game, remove_game,
    generate_game_id
)
from .messages import build_lobby_text, build_lobby_keyboard, update_lobby_message


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
        build_lobby_text(game),
        reply_markup=build_lobby_keyboard(game),
        parse_mode=ParseMode.HTML
    )
    game.lobby_msg_id = msg.message_id
    await set_game(chat_id, game)


async def cjoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lobiye katıl."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = await get_game(chat_id)

    if not game or game.state != GameState.LOBBY:
        await update.message.reply_text("⚠️ Şu anda lobi açık değil.")
        return

    if user.id in game.players:
        await update.message.reply_text("✅ Zaten lobidesiniz.")
        return

    game.add_player(user.id, user.first_name, user.username)
    await set_game(chat_id, game)

    await update_lobby_message(game, context)
    mention = f"@{user.username}" if user.username else user.first_name
    await update.message.reply_text(f"✅ {mention} oyuna katıldı!")


async def ciptal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lobiyi iptal et."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = await get_game(chat_id)

    if not game or game.state != GameState.LOBBY:
        await update.message.reply_text("⚠️ İptal edilecek lobi yok.")
        return

    if user.id != game.host_id:
        await update.message.reply_text("🛡️ Sadece oyunu başlatan iptal edebilir.")
        return

    await remove_game(chat_id)
    await update.message.reply_text("❌ Oyun iptal edildi.")

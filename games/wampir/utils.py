# games/vampir/utils.py - Yardımcı fonksiyonlar
import logging
from typing import Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def safe_send_message(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str = "Markdown",
) -> bool:
    try:
        await context.bot.send_message(
            chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode
        )
        return True
    except Exception as e:
        logger.error(f"Mesaj hatası {chat_id}: {e}")
        return False

async def safe_send_photo(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    photo_url: str,
    caption: str = "",
    parse_mode: str = "Markdown",
) -> bool:
    try:
        await context.bot.send_photo(
            chat_id=chat_id, photo=photo_url, caption=caption, parse_mode=parse_mode
        )
        return True
    except Exception as e:
        logger.error(f"Fotoğraf hatası {chat_id}: {e}")
        await safe_send_message(context, chat_id, caption, parse_mode=parse_mode)
        return False

async def safe_send_pm(
    app,
    user_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> bool:
    try:
        await app.bot.send_message(
            chat_id=user_id, text=text, reply_markup=reply_markup, parse_mode="Markdown"
        )
        return True
    except Exception as e:
        logger.error(f"PM hatası {user_id}: {e}")
        return False

async def send_mention(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, text: str
) -> bool:
    try:
        from games.vampir.state import get_game
        game = get_game(chat_id)
        player_name = next(
            (p.username for p in game.players.values() if p.user_id == user_id),
            "Bilinmeyen",
        )
        mention = f"[{player_name}](tg://user?id={user_id})"
        await safe_send_message(context, chat_id, f"{mention} {text}", parse_mode="Markdown")
        return True
    except Exception as e:
        logger.error(f"Mention hatası: {e}")
        return False

def build_player_buttons(game, only_alive: bool = True, group_id: int = None, phase: str = "night") -> Optional[InlineKeyboardMarkup]:
    if not game.players:
        return None

    buttons = []
    player_list = game.get_alive_players() if only_alive else list(game.players.values())

    row = []
    for player in player_list:
        if not only_alive and not player.alive:
            continue

        button = InlineKeyboardButton(
            f"{player.username} {'💀' if not player.alive else ''}",
            callback_data=f"vampir_target_{group_id}_{player.user_id}_{phase}",
        )
        row.append(button)

        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(buttons) if buttons else None

def build_join_button() -> InlineKeyboardMarkup:
    button = InlineKeyboardButton("🎮 Oyuna Katıl", callback_data="vampir_join")
    return InlineKeyboardMarkup([[button]])

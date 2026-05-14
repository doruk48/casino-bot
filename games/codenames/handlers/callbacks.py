"""
Tüm buton callback'leri.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from ..engine import (
    GameRoom, GameState, TeamColor,
    get_game, set_game, remove_game
)
from ..renderer import create_board_image
from ..timers import cancel_timer, start_timer
from .messages import (
    build_lobby_text, build_lobby_keyboard, build_team_selection_text,
    build_game_start_text, build_guess_info
)
from .ingame import switch_turn, clue_timeout, guess_timeout, end_game


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tüm Codenames buton callback'lerini yönetir."""
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id
    user = query.from_user

    if data == "c_join":
        await handle_join(query, chat_id, user, context)

    elif data == "c_start_game":
        await handle_start_game(query, chat_id, user, context)

    elif data == "c_cancel":
        await handle_cancel(query, chat_id, user, context)

    elif data == "c_guess":
        await handle_guess(query, chat_id, user, context)

    elif data == "c_pass":
        await handle_pass(query, chat_id, user, context)


# ═══════════════════════════════════════════════════════
#  Callback İşleyicileri
# ═══════════════════════════════════════════════════════

async def handle_join(query, chat_id, user, context):
    """Katıl butonu."""
    game = await get_game(chat_id)
    if not game or game.state != GameState.LOBBY:
        await query.answer("⚠️ Lobi kapalı.", show_alert=True)
        return

    if user.id in game.players:
        await query.answer("✅ Zaten lobidesiniz.")
        return

    game.add_player(user.id, user.first_name, user.username)
    await set_game(chat_id, game)

    # Lobi mesajını güncelle
    try:
        await query.message.edit_text(
            build_lobby_text(game),
            reply_markup=build_lobby_keyboard(game),
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass

    await query.answer(f"✅ {user.first_name} oyuna katıldı!")


async def handle_start_game(query, chat_id, user, context):
    """Oyunu Başlat butonu."""
    game = await get_game(chat_id)

    if not game or game.state != GameState.LOBBY:
        await query.answer("⚠️ Oyun zaten başlamış.", show_alert=True)
        return

    if user.id != game.host_id:
        await query.answer("🛡️ Sadece oyun sahibi başlatabilir.", show_alert=True)
        return

    if len(game.players) < 4:
        await query.answer("⚠️ En az 4 oyuncu gerekli.", show_alert=True)
        return

    if not game.blue_captain or not game.red_captain:
        await query.answer("⚠️ İki kaptan da seçilmeli.", show_alert=True)
        return

    # Lobi mesajını sil
    try:
        await query.message.delete()
    except Exception:
        pass

    # Oyun durumunu PLAYER_DRAFT yap
    game.state = GameState.PLAYER_DRAFT
    game.current_turn = TeamColor.BLUE  # Mavi başlar
    game.setup_board()  # Tahtayı oluştur
    await set_game(chat_id, game)

    # Takım seçimi başlangıç mesajı
    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=build_team_selection_text(game),
        parse_mode=ParseMode.HTML
    )
    game.info_msg_id = msg.message_id
    await set_game(chat_id, game)

    await query.answer("🚀 Oyun başlatıldı!")


async def handle_cancel(query, chat_id, user, context):
    """İptal butonu."""
    game = await get_game(chat_id)

    if not game or game.state != GameState.LOBBY:
        await query.answer("⚠️ İptal edilecek oyun yok.", show_alert=True)
        return

    if user.id != game.host_id:
        await query.answer("🛡️ Sadece oyun sahibi iptal edebilir.", show_alert=True)
        return

    await remove_game(chat_id)

    try:
        await query.message.edit_text("❌ Oyun iptal edildi.")
    except Exception:
        pass

    await query.answer("✅ Oyun iptal edildi.")


async def handle_guess(query, chat_id, user, context):
    """Yeni Tahmin butonu."""
    game = await get_game(chat_id)

    if not game or game.state not in [GameState.BLUE_GUESS, GameState.RED_GUESS]:
        await query.answer("⏳ Şu an tahmin yapılamaz.", show_alert=True)
        return

    player = game.get_player(user.id)
    if not player or not player.is_spokesperson:
        await query.answer("🎤 Bu buton sadece sözcüye özel.", show_alert=True)
        return

    if player.team != game.current_turn:
        await query.answer("⏳ Sıra sizin takımınızda değil.", show_alert=True)
        return

    if game.guesses_remaining <= 0:
        await query.answer("⚠️ Tahmin hakkınız kalmadı.", show_alert=True)
        return

    # Buton mesajını sil
    try:
        await query.message.delete()
    except Exception:
        pass

    # Süreyi sıfırla ve yeni süre başlat
    cancel_timer(game)
    await start_timer(game, 60, guess_timeout, chat_id, context)

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🎤 Sözcü {game.get_mention(user.id)}, 1 dakika içinde /ctahmin kelime yazın.",
        parse_mode=ParseMode.HTML
    )

    await query.answer("✅ Yeni tahmin için süre başladı!")


async def handle_pass(query, chat_id, user, context):
    """Pas butonu."""
    game = await get_game(chat_id)

    if not game or game.state not in [GameState.BLUE_GUESS, GameState.RED_GUESS]:
        await query.answer("⏳ Şu an pas verilemez.", show_alert=True)
        return

    player = game.get_player(user.id)
    if not player or not player.is_spokesperson:
        await query.answer("🎤 Bu buton sadece sözcüye özel.", show_alert=True)
        return

    if player.team != game.current_turn:
        await query.answer("⏳ Sıra sizin takımınızda değil.", show_alert=True)
        return

    switch_turn(game)
    await set_game(chat_id, game)

    # Buton mesajını sil
    try:
        await query.message.delete()
    except Exception:
        pass

    next_captain = game.blue_captain if game.current_turn == TeamColor.BLUE else game.red_captain
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏩ Pas verildi! Sıra {game.current_turn.value} takımda.\n"
             f"Kaptan {game.get_mention(next_captain)} DM'den /cipucu kelime sayı yazsın.",
        parse_mode=ParseMode.HTML
    )

    # İpucu süresi başlat
    await start_timer(game, 120, clue_timeout, chat_id, context)

    await query.answer("✅ Pas verildi.")

"""
Oyun içi komutlar: /ctahmin, /cpas, /cdurum, /cson
"""
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from ..engine import (
    GameRoom, GameState, TeamColor,
    get_game, set_game, remove_game
)
from ..validators import validate_command
from ..renderer import create_board_image
from ..timers import cancel_timer, start_timer
from .messages import build_clue_announcement, build_guess_info


async def ctahmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sözcü tahmin yapar."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = await get_game(chat_id)

    # Yetki kontrolü
    is_valid, player, error = validate_command(
        game, user.id,
        allowed_states=[GameState.BLUE_GUESS, GameState.RED_GUESS],
        allowed_roles=["spokesperson"]
    )
    if not is_valid:
        await update.message.reply_text(error)
        return

    if game.guesses_remaining <= 0:
        await update.message.reply_text("⏳ Tahmin hakkınız kalmadı. /cpas yapın.")
        return

    args = update.message.text.split()
    if len(args) < 2:
        await update.message.reply_text("⚠️ Kullanım: /ctahmin kelime\nÖrnek: /ctahmin araba")
        return

    word = args[1].lower()
    idx, role = game.get_cell(word)

    if idx is None:
        await update.message.reply_text("⚠️ Bu kelime tahtada yok.")
        return

    if game.revealed_mask[idx]:
        await update.message.reply_text("⚠️ Bu kelime zaten açıldı.")
        return

    # Kartı aç
    game.reveal(idx)
    game.guesses_remaining -= 1
    cancel_timer(game)

    # Eski görseli sil
    if game.board_msg_id:
        try:
            await context.bot.delete_message(chat_id, game.board_msg_id)
        except Exception:
            pass

    # Yeni görsel oluştur
    img_buffer = create_board_image(game.board_cells, game.revealed_mask, game.board_roles)

    # Sonuç mesajı
    team_emoji = "🔵" if player.team == TeamColor.BLUE else "🔴"

    if role == "blue" or role == "red":
        color_name = "Mavi" if role == "blue" else "Kırmızı"
        own_team = (role == "blue" and player.team == TeamColor.BLUE) or \
                   (role == "red" and player.team == TeamColor.RED)
        if own_team:
            caption = (
                f"🎉 <b>DOĞRU TAHMİN!</b>\n"
                f"{team_emoji} <b>{word}</b> mavi kelimeymiş!\n"
                f"Kalan tahmin hakkı: {game.guesses_remaining}"
            )
        else:
            caption = (
                f"😬 <b>RAKİP RENK!</b>\n"
                f"{team_emoji} <b>{word}</b> {color_name} takımınmış.\n"
                f"Sıra rakibe geçti."
            )
            switch_turn(game)

    elif role == "civilian":
        caption = (
            f"⬜️ <b>BOŞ KELİME!</b>\n"
            f"<b>{word}</b> renksiz bir kelimeymiş.\n"
            f"Sıra rakibe geçti."
        )
        switch_turn(game)

    elif role == "assassin":
        caption = (
            f"💀 <b>SUİKASTÇI!</b>\n"
            f"<b>{word}</b> suikastçı çıktı!\n"
            f"☠️ {player.team.value.upper()} TAKIM KAYBETTİ!"
        )
        game.state = GameState.GAME_OVER
        game.revealed_mask = [True] * 25
        # Son görseli tamamen açık göster
        img_buffer = create_board_image(game.board_cells, game.revealed_mask, game.board_roles)

    else:
        caption = f"<b>{word}</b> açıldı."

    # Yeni görseli gönder
    msg = await context.bot.send_photo(
        chat_id=chat_id,
        photo=img_buffer,
        caption=caption,
        parse_mode=ParseMode.HTML
    )
    game.board_msg_id = msg.message_id

    if game.state == GameState.GAME_OVER:
        await end_game(game, context)
        return

    # Kazanma kontrolü
    if game.blue_remaining == 0:
        game.state = GameState.GAME_OVER
        game.revealed_mask = [True] * 25
        img_buffer = create_board_image(game.board_cells, game.revealed_mask, game.board_roles)
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=img_buffer,
            caption="🎉 <b>MAVİ TAKIM KAZANDI!</b> Tüm mavi kelimeler açıldı!",
            parse_mode=ParseMode.HTML
        )
        await end_game(game, context)
        return

    if game.red_remaining == 0:
        game.state = GameState.GAME_OVER
        game.revealed_mask = [True] * 25
        img_buffer = create_board_image(game.board_cells, game.revealed_mask, game.board_roles)
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=img_buffer,
            caption="🎉 <b>KIRMIZI TAKIM KAZANDI!</b> Tüm kırmızı kelimeler açıldı!",
            parse_mode=ParseMode.HTML
        )
        await end_game(game, context)
        return

    # Tahmin hakkı devam ediyorsa buton göster
    if role in ("blue", "red") and game.guesses_remaining > 0:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔍 Yeni Tahmin", callback_data="c_guess"),
                InlineKeyboardButton("⏩ Pas", callback_data="c_pass")
            ]
        ])
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{build_guess_info(game)}\n\nNe yapmak istersiniz?",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    else:
        # Yeni ipucu için sıra karşı takıma geçtiyse bildir
        if game.state in [GameState.BLUE_CLUE, GameState.RED_CLUE]:
            next_captain = game.blue_captain if game.current_turn == TeamColor.BLUE else game.red_captain
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⏩ Sıra {game.current_turn.value} takımda.\n"
                     f"Kaptan {game.get_mention(next_captain)} DM'den /cipucu kelime sayı yazsın.",
                parse_mode=ParseMode.HTML
            )
            # İpucu süresi başlat
            await start_timer(game, 120, clue_timeout, chat_id, context)

    await set_game(chat_id, game)


async def cpas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sözcü pas verir."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = await get_game(chat_id)

    is_valid, player, error = validate_command(
        game, user.id,
        allowed_states=[GameState.BLUE_GUESS, GameState.RED_GUESS],
        allowed_roles=["spokesperson"]
    )
    if not is_valid:
        await update.message.reply_text(error)
        return

    switch_turn(game)
    await set_game(chat_id, game)

    next_captain = game.blue_captain if game.current_turn == TeamColor.BLUE else game.red_captain
    await update.message.reply_text(
        f"⏩ Pas verildi! Sıra {game.current_turn.value} takımda.\n"
        f"Kaptan {game.get_mention(next_captain)} DM'den /cipucu kelime sayı yazsın.",
        parse_mode=ParseMode.HTML
    )

    # İpucu süresi başlat
    await start_timer(game, 120, clue_timeout, chat_id, context)


async def cdurum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Oyun durumunu gösterir."""
    chat_id = update.effective_chat.id
    game = await get_game(chat_id)

    if not game:
        await update.message.reply_text("⚠️ Aktif bir oyun bulunamadı.")
        return

    text = (
        f"🆔 <b>Oyun ID:</b> <code>{game.game_id}</code>\n"
        f"📊 <b>Aşama:</b> {game.state.value}\n"
        f"🔵 Kalan mavi: <b>{game.blue_remaining}</b>\n"
        f"🔴 Kalan kırmızı: <b>{game.red_remaining}</b>\n"
    )
    if game.current_turn:
        text += f"⏳ Sıra: <b>{game.current_turn.value}</b> takım\n"
    if game.clue_word:
        text += f"💬 Son ipucu: <b>{game.clue_word}</b> ({game.clue_number})\n"
    if game.state in [GameState.BLUE_GUESS, GameState.RED_GUESS]:
        text += f"🎯 Kalan tahmin hakkı: <b>{game.guesses_remaining}</b>\n"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Oyunu erken bitir."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = await get_game(chat_id)

    if not game:
        await update.message.reply_text("⚠️ Aktif oyun yok.")
        return

    if user.id not in (game.blue_captain, game.red_captain, game.host_id):
        await update.message.reply_text("🛡️ Sadece kaptanlar veya oyun sahibi bitirebilir.")
        return

    game.state = GameState.GAME_OVER
    game.revealed_mask = [True] * 25
    img_buffer = create_board_image(game.board_cells, game.revealed_mask, game.board_roles)
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=img_buffer,
        caption="🏁 Oyun erken sonlandırıldı.",
        parse_mode=ParseMode.HTML
    )
    await end_game(game, context)


# ═══════════════════════════════════════════════════════
#  Yardımcı Fonksiyonlar
# ═══════════════════════════════════════════════════════

def switch_turn(game: GameRoom):
    """Sırayı diğer takıma geçirir."""
    cancel_timer(game)
    if game.current_turn == TeamColor.BLUE:
        game.current_turn = TeamColor.RED
        game.state = GameState.RED_CLUE
    else:
        game.current_turn = TeamColor.BLUE
        game.state = GameState.BLUE_CLUE
    game.guesses_remaining = 0
    game.clue_word = None
    game.clue_number = None


async def clue_timeout(game: GameRoom, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """İpucu süresi dolduğunda çağrılır."""
    if game.state not in [GameState.BLUE_CLUE, GameState.RED_CLUE]:
        return
    team = game.current_turn.value if game.current_turn else ""
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏰ {team.upper()} takım kaptanı süresi doldu! Sıra rakibe geçiyor."
    )
    switch_turn(game)
    await set_game(chat_id, game)


async def guess_timeout(game: GameRoom, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Tahmin süresi dolduğunda çağrılır."""
    if game.state not in [GameState.BLUE_GUESS, GameState.RED_GUESS]:
        return
    await context.bot.send_message(
        chat_id=chat_id,
        text="⏰ Tahmin süresi doldu! Otomatik pas."
    )
    switch_turn(game)
    await set_game(chat_id, game)


async def end_game(game: GameRoom, context: ContextTypes.DEFAULT_TYPE):
    """Oyunu temizle."""
    cancel_timer(game)
    await remove_game(game.chat_id)
    await context.bot.send_message(
        chat_id=game.chat_id,
        text="🔄 Oyun sona erdi. Yeni oyun için /cstart yazabilirsiniz."
  )

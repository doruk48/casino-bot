"""
Takım kurulum komutları: /ckaptan, /csec, /csozcu, /cistifa
"""
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from ..engine import (
    GameRoom, GameState, TeamColor, Player,
    get_game, set_game
)
from ..validators import validate_command
from .messages import build_team_selection_text


async def ckaptan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tek komutla kaptan ol ve takımını seç."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    args = update.message.text.split()

    if len(args) < 2 or args[1] not in ["mavi", "kirmizi"]:
        await update.message.reply_text(
            "⚠️ Kullanım: /ckaptan mavi veya /ckaptan kirmizi"
        )
        return

    takim = args[1]
    game = await get_game(chat_id)

    if not game or game.state != GameState.LOBBY:
        await update.message.reply_text("⚠️ Şu anda lobi açık değil. /cstart ile başlatın.")
        return

    if user.id not in game.players:
        await update.message.reply_text("⚠️ Önce /cjoin ile oyuna katılmalısınız.")
        return

    if takim == "mavi":
        if game.blue_captain is not None:
            await update.message.reply_text(
                f"🔵 Mavi takım kaptanı zaten {game.get_mention(game.blue_captain)}"
            )
            return
        game.blue_captain = user.id
        game.players[user.id].is_captain = True
        game.players[user.id].team = TeamColor.BLUE
        await update.message.reply_text(
            f"🔵 {user.first_name} mavi takım kaptanı oldu!\n"
            "⚠️ Lütfen 'PM'ye Git' butonuyla botu özelden başlatın."
        )
    else:
        if game.red_captain is not None:
            await update.message.reply_text(
                f"🔴 Kırmızı takım kaptanı zaten {game.get_mention(game.red_captain)}"
            )
            return
        game.red_captain = user.id
        game.players[user.id].is_captain = True
        game.players[user.id].team = TeamColor.RED
        await update.message.reply_text(
            f"🔴 {user.first_name} kırmızı takım kaptanı oldu!\n"
            "⚠️ Lütfen 'PM'ye Git' butonuyla botu özelden başlatın."
        )

    await set_game(chat_id, game)
    from .messages import update_lobby_message
    await update_lobby_message(game, context)


async def csec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kaptan reply ile oyuncu seçer."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = await get_game(chat_id)

    # Yetki kontrolü
    is_valid, player, error = validate_command(
        game, user.id,
        allowed_states=[GameState.PLAYER_DRAFT],
        allowed_roles=["captain"]
    )
    if not is_valid:
        await update.message.reply_text(error)
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ Lütfen seçmek istediğiniz oyuncunun mesajını yanıtlayarak /csec yazın."
        )
        return

    target_user = update.message.reply_to_message.from_user
    if target_user.id not in game.players:
        await update.message.reply_text("⚠️ Bu kişi lobide değil.")
        return

    target_player = game.players[target_user.id]
    if target_player.team is not None:
        await update.message.reply_text("⚠️ Bu oyuncu zaten bir takımda.")
        return

    # Sıra kontrolü
    if (game.current_turn == TeamColor.BLUE and player.team != TeamColor.BLUE) or \
       (game.current_turn == TeamColor.RED and player.team != TeamColor.RED):
        await update.message.reply_text("⏳ Sıra sizde değil.")
        return

    # Oyuncuyu takıma ekle
    if player.team == TeamColor.BLUE:
        game.blue_players.append(target_user.id)
    else:
        game.red_players.append(target_user.id)
    target_player.team = player.team

    # Sırayı değiştir
    all_remaining = [p for p in game.players.values() if p.team is None]

    if not all_remaining:
        game.state = GameState.DRAFT_FINISHED
        game.current_turn = None
        await set_game(chat_id, game)
        await update.message.reply_text(
            "✅ Tüm oyuncular seçildi!\n\n"
            "🔵 Mavi takım, aranızdan bir sözcü seçin: /csozcu\n"
            "🔴 Kırmızı takım, aranızdan bir sözcü seçin: /csozcu"
        )
    else:
        game.current_turn = TeamColor.RED if player.team == TeamColor.BLUE else TeamColor.BLUE
        await set_game(chat_id, game)
        next_captain = game.red_captain if game.current_turn == TeamColor.RED else game.blue_captain
        await update.message.reply_text(
            f"✅ {target_user.first_name} {player.team.value} takıma eklendi.\n"
            f"⏳ Sıra {game.current_turn.value} takımda — "
            f"Kaptan {game.get_mention(next_captain)} /csec ile seçim yapsın."
        )

    # Takım listesini güncelle
    if game.info_msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=game.info_msg_id,
                text=build_team_selection_text(game),
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
    else:
        msg = await update.message.reply_text(
            build_team_selection_text(game),
            parse_mode=ParseMode.HTML
        )
        game.info_msg_id = msg.message_id
        await set_game(chat_id, game)


async def csozcu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Takım oyuncusu kendini sözcü yapar."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = await get_game(chat_id)

    is_valid, player, error = validate_command(
        game, user.id,
        allowed_states=[GameState.DRAFT_FINISHED, GameState.BLUE_CLUE, GameState.RED_CLUE,
                       GameState.BLUE_GUESS, GameState.RED_GUESS],
        allowed_roles=["any"]  # Takım oyuncusu olmak yeterli
    )
    if not is_valid or not player:
        await update.message.reply_text(error or "⚠️ Oyunda değilsiniz.")
        return

    if player.team == TeamColor.BLUE:
        if game.blue_spokesperson is not None:
            await update.message.reply_text(
                f"🔵 Mavi takım sözcüsü zaten {game.get_mention(game.blue_spokesperson)}.\n"
                "Değiştirmek için sözcü /cistifa yapmalı."
            )
            return
        game.blue_spokesperson = user.id
        player.is_spokesperson = True
        await update.message.reply_text(f"🎤 {user.first_name} mavi takım sözcüsü oldu!")
    elif player.team == TeamColor.RED:
        if game.red_spokesperson is not None:
            await update.message.reply_text(
                f"🔴 Kırmızı takım sözcüsü zaten {game.get_mention(game.red_spokesperson)}.\n"
                "Değiştirmek için sözcü /cistifa yapmalı."
            )
            return
        game.red_spokesperson = user.id
        player.is_spokesperson = True
        await update.message.reply_text(f"🎤 {user.first_name} kırmızı takım sözcüsü oldu!")
    else:
        await update.message.reply_text("⚠️ Henüz bir takımda değilsiniz.")
        return

    await set_game(chat_id, game)

    # İki sözcü de seçildiyse bilgi ver
    if game.blue_spokesperson and game.red_spokesperson:
        from .messages import build_game_start_text
        await update.message.reply_text(
            "✅ Her iki sözcü seçildi!\n\n" + build_game_start_text(game),
            parse_mode=ParseMode.HTML
        )
        await update.message.reply_text(
            "🚀 Oyunu başlatmak için bir kaptan /cson yazabilir veya aşağıdaki butonu kullanın:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🚀 Oyunu Başlat", callback_data="c_start_game")
            ]])
        )


async def cistifa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sözcü istifa eder."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = await get_game(chat_id)

    if not game:
        await update.message.reply_text("⚠️ Aktif oyun yok.")
        return

    player = game.get_player(user.id)
    if not player or not player.is_spokesperson:
        await update.message.reply_text("⚠️ Sadece takım sözcüsü istifa edebilir.")
        return

    if player.team == TeamColor.BLUE:
        game.blue_spokesperson = None
    else:
        game.red_spokesperson = None
    player.is_spokesperson = False

    await update.message.reply_text(
        f"🔄 {user.first_name} sözcülükten ayrıldı.\n"
        "Takımınız yeni sözcü seçebilir: /csozcu"
    )
    await set_game(chat_id, game)


# InlineKeyboardMarkup import için
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

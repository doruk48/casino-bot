import asyncio
import random
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode

from .engine import (GameRoom, GameState, TeamColor, Player,
                     get_game, set_game, remove_game, _active_games)
from .validators import validate_command
from .timers import start_timer, cancel_timer
from .renderer import create_board_image

# ----- Yardımcı Fonksiyonlar -----

def generate_game_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def build_lobby_keyboard(game: GameRoom):
    buttons = []
    if len(game.players) < 12:
        buttons.append([InlineKeyboardButton("➕ Katıl", callback_data="c_join")])
    buttons.append([InlineKeyboardButton("🤖 PM'ye Git (Botu Başlat)", url="https://t.me/CodenamesBot")])  # bot adını düzenle
    if game.host_id:
        buttons.append([
            InlineKeyboardButton("🚀 Oyunu Başlat", callback_data="c_start_game"),
            InlineKeyboardButton("❌ İptal", callback_data="c_cancel")
        ])
    return InlineKeyboardMarkup(buttons)

def build_lobby_text(game: GameRoom):
    text = "🎭 <b>CODENAMES LOBI</b>\n\n"
    if not game.players:
        text += "Henüz katılım yok.\n"
    else:
        for i, (uid, p) in enumerate(game.players.items(), 1):
            text += f"{i}. {p.first_name}"
            if p.username:
                text += f" (@{p.username})"
            text += "\n"
    text += "\n📢 Kaptan olmak için: /ckaptan mavi veya /ckaptan kirmizi"
    return text

async def update_lobby_message(game: GameRoom, context: ContextTypes.DEFAULT_TYPE):
    if game.lobby_msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=game.chat_id,
                message_id=game.lobby_msg_id,
                text=build_lobby_text(game),
                reply_markup=build_lobby_keyboard(game),
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass

# ----- Komut Handler'ları -----

async def cstart(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await update.message.reply_text(f"✅ @{user.username if user.username else user.first_name} oyuna katıldı!")

async def ckaptan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    args = update.message.text.split()
    if len(args) < 2 or args[1] not in ["mavi", "kirmizi"]:
        await update.message.reply_text("⚠️ Kullanım: /ckaptan mavi veya /ckaptan kirmizi")
        return
    takim = args[1]
    game = await get_game(chat_id)
    if not game or game.state != GameState.LOBBY:
        await update.message.reply_text("⚠️ Şu anda lobi açık değil.")
        return
    if user.id not in game.players:
        await update.message.reply_text("⚠️ Önce oyuna katılmalısınız.")
        return
    if takim == "mavi":
        if game.blue_captain is not None:
            await update.message.reply_text(f"🔵 Mavi takım kaptanı zaten {game.get_mention(game.blue_captain)}")
            return
        game.blue_captain = user.id
        game.players[user.id].is_captain = True
        game.players[user.id].team = TeamColor.BLUE
        await update.message.reply_text(f"🔵 {user.first_name} mavi takım kaptanı oldu!")
    else:
        if game.red_captain is not None:
            await update.message.reply_text(f"🔴 Kırmızı takım kaptanı zaten {game.get_mention(game.red_captain)}")
            return
        game.red_captain = user.id
        game.players[user.id].is_captain = True
        game.players[user.id].team = TeamColor.RED
        await update.message.reply_text(f"🔴 {user.first_name} kırmızı takım kaptanı oldu!")
    await set_game(chat_id, game)
    await update_lobby_message(game, context)

async def csec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = await get_game(chat_id)
    # Yetki kontrolü
    is_valid, player, error = validate_command(game, user.id,
        allowed_states=[GameState.PLAYER_DRAFT],
        allowed_roles=["captain"])
    if not is_valid:
        await update.message.reply_text(error)
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Lütfen seçmek istediğiniz oyuncunun mesajını yanıtlayarak /csec yazın.")
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
    all_players = [p for p in game.players.values() if p.team is None]
    if not all_players:
        game.state = GameState.DRAFT_FINISHED
        game.current_turn = None
        await update.message.reply_text("✅ Tüm oyuncular seçildi! Şimdi sözcülerinizi /csozcu ile belirleyin.")
    else:
        game.current_turn = TeamColor.RED if player.team == TeamColor.BLUE else TeamColor.BLUE
        await update.message.reply_text(
            f"✅ {target_user.first_name} {player.team.value} takıma eklendi.\n"
            f"⏳ Sıra {game.current_turn.value} takımda, kaptan {game.get_mention(game.red_captain if game.current_turn==TeamColor.RED else game.blue_captain)} /csec ile seçim yapsın."
        )
    await set_game(chat_id, game)
    # Takım listesini yayınla
    await show_team_status(game, context)

async def csozcu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = await get_game(chat_id)
    is_valid, player, error = validate_command(game, user.id,
        allowed_states=[GameState.DRAFT_FINISHED, GameState.BLUE_CLUE, GameState.RED_CLUE, GameState.BLUE_GUESS, GameState.RED_GUESS],
        allowed_roles=["player"])
    if not is_valid:
        await update.message.reply_text(error)
        return
    if player.team == TeamColor.BLUE:
        if game.blue_spokesperson is not None:
            await update.message.reply_text(f"🔵 Mavi takım sözcüsü zaten {game.get_mention(game.blue_spokesperson)}. Değişiklik için önce /cistifa yapılmalı.")
            return
        game.blue_spokesperson = user.id
        player.is_spokesperson = True
        await update.message.reply_text(f"🎤 {user.first_name} mavi takım sözcüsü oldu!")
    else:
        if game.red_spokesperson is not None:
            await update.message.reply_text(f"🔴 Kırmızı takım sözcüsü zaten {game.get_mention(game.red_spokesperson)}. Değişiklik için önce /cistifa yapılmalı.")
            return
        game.red_spokesperson = user.id
        player.is_spokesperson = True
        await update.message.reply_text(f"🎤 {user.first_name} kırmızı takım sözcüsü oldu!")
    await set_game(chat_id, game)
    # İki sözcü de seçildiyse oyunu başlatma butonu göster
    if game.blue_spokesperson and game.red_spokesperson:
        await update.message.reply_text("✅ Her iki sözcü seçildi! Oyun başlatılabilir.")

async def cistifa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = await get_game(chat_id)
    if not game:
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
    await update.message.reply_text(f"🔄 {user.first_name} sözcülükten ayrıldı. Takımı yeni sözcü seçebilir.")
    await set_game(chat_id, game)

async def cipucu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("🤫 Bu komutu sadece bana özelden kullanabilirsiniz.")
        return
    user = update.effective_user
    # Kaptanın hangi oyunda olduğunu bul
    for chat_id, game in _active_games.items():
        if game.blue_captain == user.id or game.red_captain == user.id:
            break
    else:
        await update.message.reply_text("⚠️ Aktif bir oyunda kaptan değilsiniz.")
        return
    # Durum ve sıra kontrolü
    if game.state not in [GameState.BLUE_CLUE, GameState.RED_CLUE]:
        await update.message.reply_text("⏳ Şu an ipucu sırası değil.")
        return
    if (game.state == GameState.BLUE_CLUE and game.blue_captain != user.id) or \
       (game.state == GameState.RED_CLUE and game.red_captain != user.id):
        await update.message.reply_text("⏳ Sıra sizde değil.")
        return
    args = update.message.text.split()
    if len(args) < 3:
        await update.message.reply_text("⚠️ Kullanım: /cipucu kelime sayı\nÖrnek: /cipucu hayvan 2")
        return
    clue_word = args[1]
    try:
        clue_number = int(args[2])
    except ValueError:
        await update.message.reply_text("⚠️ Sayı geçerli değil.")
        return
    if clue_number < 0 or clue_number > 9:
        await update.message.reply_text("⚠️ Sayı 0-9 arasında olmalı.")
        return
    # İpucunu kaydet ve gruba bildir
    game.clue_word = clue_word
    game.clue_number = clue_number
    game.guesses_remaining = min(clue_number + 1, game.max_guesses)
    if game.state == GameState.BLUE_CLUE:
        game.state = GameState.BLUE_GUESS
    else:
        game.state = GameState.RED_GUESS
    cancel_timer(game)
    await set_game(game.chat_id, game)
    # Gruba ipucu mesajı
    team_emoji = "🔵" if game.current_turn == TeamColor.BLUE else "🔴"
    await context.bot.send_message(
        chat_id=game.chat_id,
        text=f"{team_emoji} {game.get_mention(user.id)} ipucu: <b>{clue_word.upper()}</b>, <b>{clue_number}</b>",
        parse_mode=ParseMode.HTML
    )
    # Tahmin süresi başlat
    from .timers import start_timer as st
    await st(game, 60, guess_timeout, game.chat_id, context)

async def ctahmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = await get_game(chat_id)
    is_valid, player, error = validate_command(game, user.id,
        allowed_states=[GameState.BLUE_GUESS, GameState.RED_GUESS],
        allowed_roles=["spokesperson"])
    if not is_valid:
        await update.message.reply_text(error)
        return
    if game.guesses_remaining <= 0:
        await update.message.reply_text("⏳ Tahmin hakkınız kalmadı. /cpas yapın.")
        return
    args = update.message.text.split()
    if len(args) < 2:
        await update.message.reply_text("⚠️ Lütfen bir kelime girin: /ctahmin araba")
        return
    word = args[1]
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
    cancel_timer(game)  # süreyi durdur

    # Görseli güncelle
    img = create_board_image(game.board_cells, game.revealed_mask, game.board_roles)
    # Eski görseli sil
    if game.board_msg_id:
        try:
            await context.bot.delete_message(chat_id, game.board_msg_id)
        except:
            pass
    # Yeni görsel ve bildirim
    if role == "blue" or role == "red":
        color_name = "Mavi" if role=="blue" else "Kırmızı"
        team_mention = game.get_mention(game.blue_captain if role=="blue" else game.red_captain)
        text = f"✅ {word} {color_name} kelime! Doğru tahmin."
    elif role == "civilian":
        text = f"⬜️ {word} boş kelime. Sıra rakibe geçti."
        switch_turn(game)
    elif role == "assassin":
        text = f"💀 {word} SUİKASTÇI! Oyun bitti."
        game.state = GameState.GAME_OVER
        # Tüm kartları aç
        game.revealed_mask = [True]*25
    msg = await context.bot.send_photo(chat_id, photo=img, caption=text)
    game.board_msg_id = msg.message_id

    if game.state != GameState.GAME_OVER:
        if role in ("blue", "red") and game.guesses_remaining > 0:
            # Buton ekle: Yeni Tahmin, Pas
            keyboard = [
                [InlineKeyboardButton("Yeni Tahmin", callback_data="c_guess"),
                 InlineKeyboardButton("Pas", callback_data="c_pass")]
            ]
            await context.bot.send_message(chat_id, "Ne yapmak istersiniz?",
                                           reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            switch_turn(game)
        # Tekrar tahmin süresi başlat (opsiyonel)
        if game.state in [GameState.BLUE_GUESS, GameState.RED_GUESS]:
            from .timers import start_timer as st
            await st(game, 60, guess_timeout, chat_id, context)
    else:
        await end_game(game, context)

async def cpas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = await get_game(chat_id)
    is_valid, player, error = validate_command(game, user.id,
        allowed_states=[GameState.BLUE_GUESS, GameState.RED_GUESS],
        allowed_roles=["spokesperson"])
    if not is_valid:
        await update.message.reply_text(error)
        return
    switch_turn(game)
    await update.message.reply_text("⏩ Pas verildi, sıra rakibe geçti.")

async def cdurum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = await get_game(chat_id)
    if not game:
        await update.message.reply_text("⚠️ Aktif oyun yok.")
        return
    text = f"Oyun ID: {game.game_id}\nAşama: {game.state.value}\n"
    if game.current_turn:
        text += f"Sıra: {game.current_turn.value} takım\n"
    text += f"Kalan Mavi: {game.blue_remaining}, Kalan Kırmızı: {game.red_remaining}"
    await update.message.reply_text(text)

async def cson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = await get_game(chat_id)
    if not game:
        return
    if user.id not in (game.blue_captain, game.red_captain, game.host_id):
        await update.message.reply_text("🛡️ Sadece kaptanlar veya oyun sahibi bitirebilir.")
        return
    game.state = GameState.GAME_OVER
    game.revealed_mask = [True]*25
    await end_game(game, context)

async def ciptal(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def chelp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🕵️ <b>CODENAMES KOMUTLARI</b>\n\n"
        "/cstart - Yeni oyun başlat\n"
        "/cjoin - Oyuna katıl\n"
        "/ckaptan mavi|kirmizi - Kaptan ol\n"
        "/csec (reply) - Oyuncu seç\n"
        "/csozcu - Sözcü ol\n"
        "/cistifa - Sözcülükten ayrıl\n"
        "/cipucu kelime sayı (DM) - İpucu ver\n"
        "/ctahmin kelime - Tahmin yap\n"
        "/cpas - Pas geç\n"
        "/cdurum - Oyun durumu\n"
        "/cson - Oyunu bitir\n"
        "/ciptal - Lobiyi iptal et\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

# ----- Buton Callback'leri -----

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id
    user = query.from_user

    if data == "c_join":
        # Aynı join komutu gibi
        game = await get_game(chat_id)
        if not game or game.state != GameState.LOBBY:
            await query.message.reply_text("⚠️ Lobi kapalı.")
            return
        if user.id in game.players:
            await query.answer("Zaten katılı durumdasınız.")
            return
        game.add_player(user.id, user.first_name, user.username)
        await set_game(chat_id, game)
        await update_lobby_message(game, context)

    elif data == "c_start_game":
        game = await get_game(chat_id)
        if not game or game.state != GameState.LOBBY:
            await query.answer("Oyun zaten başlamış.")
            return
        if user.id != game.host_id:
            await query.answer("Sadece oyun sahibi başlatabilir.", show_alert=True)
            return
        # Oyuncu sayısı yeterli mi
        if len(game.players) < 4:
            await query.answer("En az 4 oyuncu gerekli.", show_alert=True)
            return
        # Kaptanlar seçildi mi
        if not game.blue_captain or not game.red_captain:
            await query.answer("İki kaptan da seçilmeli.", show_alert=True)
            return
        # Başlangıç state'ini PLAYER_DRAFT yap
        game.state = GameState.PLAYER_DRAFT
        game.current_turn = TeamColor.BLUE  # mavi başlar
        await set_game(chat_id, game)
        # Lobi mesajını sil
        try:
            await context.bot.delete_message(chat_id, game.lobby_msg_id)
        except:
            pass
        await query.message.reply_text(
            f"🔵 Mavi takım kaptanı {game.get_mention(game.blue_captain)}, "
            f"oyuncu seçmek için bir mesajı yanıtlayarak /csec komutunu kullanın."
        )
        # Draft mesajını gönder
        await show_team_status(game, context)

    elif data == "c_cancel":
        game = await get_game(chat_id)
        if game and game.state == GameState.LOBBY and user.id == game.host_id:
            await remove_game(chat_id)
            await query.message.edit_text("❌ Oyun iptal edildi.")
        else:
            await query.answer("Sadece oyun sahibi iptal edebilir.", show_alert=True)

    elif data == "c_guess":
        # Yeni tahmin butonu
        game = await get_game(chat_id)
        if not game or game.state not in [GameState.BLUE_GUESS, GameState.RED_GUESS]:
            await query.answer("Şu an tahmin yapılamaz.")
            return
        player = game.get_player(user.id)
        if not player or not player.is_spokesperson or player.team != game.current_turn:
            await query.answer("Bu butonu sadece sıradaki takım sözcüsü kullanabilir.", show_alert=True)
            return
        if game.guesses_remaining <= 0:
            await query.answer("Tahmin hakkınız kalmadı.")
            return
        await query.message.delete()
        # Zamanlayıcıyı sıfırla ve 1 dakika ver
        cancel_timer(game)
        await query.message.reply_text(
            f"⏳ @{user.username}, 1 dakika içinde /ctahmin kelime yaz."
        )
        from .timers import start_timer as st
        await st(game, 60, guess_timeout, chat_id, context)

    elif data == "c_pass":
        game = await get_game(chat_id)
        player = game.get_player(user.id) if game else None
        if not player or not player.is_spokesperson or player.team != game.current_turn:
            await query.answer("Bu butonu sadece sıradaki takım sözcüsü kullanabilir.", show_alert=True)
            return
        switch_turn(game)
        await query.message.edit_text("⏩ Pas verildi, sıra rakibe geçti.")

# ----- Yardımcı Oyun Akışı -----

def switch_turn(game: GameRoom):
    cancel_timer(game)
    if game.state in [GameState.BLUE_GUESS, GameState.BLUE_CLUE]:
        game.state = GameState.RED_CLUE
        game.current_turn = TeamColor.RED
    else:
        game.state = GameState.BLUE_CLUE
        game.current_turn = TeamColor.BLUE
    game.guesses_remaining = 0

async def guess_timeout(game: GameRoom, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Tahmin süresi dolunca otomatik pas."""
    if game.state not in [GameState.BLUE_GUESS, GameState.RED_GUESS]:
        return
    await context.bot.send_message(chat_id, "⏰ Süre bitti! Otomatik pas.")
    switch_turn(game)
    await set_game(chat_id, game)

async def clue_timeout(game: GameRoom, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    if game.state not in [GameState.BLUE_CLUE, GameState.RED_CLUE]:
        return
    await context.bot.send_message(chat_id, "⏰ İpucu süresi doldu! Sıra rakibe geçiyor.")
    switch_turn(game)
    await set_game(chat_id, game)

async def show_team_status(game: GameRoom, context):
    text = "🎭 <b>TAKIMLAR</b>\n\n"
    text += "🔵 <b>Mavi Takım</b>\n"
    text += f"Kaptan: {game.get_mention(game.blue_captain)}\n"
    if game.blue_spokesperson:
        text += f"Sözcü: {game.get_mention(game.blue_spokesperson)}\n"
    for i, uid in enumerate(game.blue_players, 1):
        text += f"{i}. {game.get_mention(uid)}\n"
    text += "\n🔴 <b>Kırmızı Takım</b>\n"
    text += f"Kaptan: {game.get_mention(game.red_captain)}\n"
    if game.red_spokesperson:
        text += f"Sözcü: {game.get_mention(game.red_spokesperson)}\n"
    for i, uid in enumerate(game.red_players, 1):
        text += f"{i}. {game.get_mention(uid)}\n"
    await context.bot.send_message(game.chat_id, text, parse_mode=ParseMode.HTML)

async def end_game(game, context):
    # Son görseli gönder
    img = create_board_image(game.board_cells, [True]*25, game.board_roles)
    await context.bot.send_photo(game.chat_id, photo=img, caption="🏁 Oyun bitti!")
    await remove_game(game.chat_id)

# ----- Handler Kaydı -----

def register_handlers(app):
    app.add_handler(CommandHandler("cstart", cstart))
    app.add_handler(CommandHandler("cjoin", cjoin))
    app.add_handler(CommandHandler("ckaptan", ckaptan))
    app.add_handler(CommandHandler("csec", csec))
    app.add_handler(CommandHandler("csozcu", csozcu))
    app.add_handler(CommandHandler("cistifa", cistifa))
    app.add_handler(CommandHandler("cipucu", cipucu, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("ctahmin", ctahmin))
    app.add_handler(CommandHandler("cpas", cpas))
    app.add_handler(CommandHandler("cdurum", cdurum))
    app.add_handler(CommandHandler("cson", cson))
    app.add_handler(CommandHandler("ciptal", ciptal))
    app.add_handler(CommandHandler("chelp", chelp))
    app.add_handler(CallbackQueryHandler(button_handler))

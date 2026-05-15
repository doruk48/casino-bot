"""
Lobi, takım listesi ve buton mesaj şablonları.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from ..engine import GameRoom, TeamColor


def build_lobby_keyboard(game: GameRoom) -> InlineKeyboardMarkup:
    """Lobi mesajı için butonları oluştur."""
    buttons = []

    if len(game.players) < 12:
        buttons.append([
            InlineKeyboardButton("➕ Katıl", callback_data="c_join")
        ])

    buttons.append([
        InlineKeyboardButton(
            "🤖 PM'ye Git (Botu Başlat)",
            url="https://t.me/BOT_KULLANICI_ADIN"  # ⚠️ Kendi bot adresinle değiştir
        )
    ])

    buttons.append([
        InlineKeyboardButton("🚀 Oyunu Başlat", callback_data="c_start_game"),
        InlineKeyboardButton("❌ İptal", callback_data="c_cancel")
    ])

    return InlineKeyboardMarkup(buttons)


def build_lobby_text(game: GameRoom) -> str:
    """Lobi mesajı metnini oluştur."""
    text = "🎭 <b>CODENAMES LOBI</b>\n\n"
    text += f"🆔 Oyun ID: <code>{game.game_id}</code>\n\n"

    if not game.players:
        text += "Henüz katılım yok.\n"
    else:
        text += "<b>👥 Oyuncular:</b>\n"
        for i, (uid, p) in enumerate(game.players.items(), 1):
            text += f"{i}. {p.first_name}"
            if p.username:
                text += f" (@{p.username})"
            if game.blue_captain == uid:
                text += " 🔵 Kaptan"
            elif game.red_captain == uid:
                text += " 🔴 Kaptan"
            text += "\n"

    text += "\n📢 <b>Kaptan olmak için:</b>\n"
    text += "/ckaptan mavi — Mavi takım kaptanı ol\n"
    text += "/ckaptan kirmizi — Kırmızı takım kaptanı ol\n"
    text += "\n⚠️ <b>Kaptanlar:</b> 'PM'ye Git' butonu ile botu özelden başlatın!"

    return text


def build_team_selection_text(game: GameRoom) -> str:
    """Oyuncu seçimi aşaması mesajı."""
    text = "🔄 <b>OYUNCU SEÇİMİ</b>\n\n"

    text += "🔵 <b>Mavi Takım</b>\n"
    text += f"Kaptan: {game.get_mention(game.blue_captain)}\n"
    for i, uid in enumerate(game.blue_players, 1):
        text += f"  {i}. {game.get_mention(uid)}\n"
    if not game.blue_players:
        text += "  (Henüz oyuncu yok)\n"

    text += "\n🔴 <b>Kırmızı Takım</b>\n"
    text += f"Kaptan: {game.get_mention(game.red_captain)}\n"
    for i, uid in enumerate(game.red_players, 1):
        text += f"  {i}. {game.get_mention(uid)}\n"
    if not game.red_players:
        text += "  (Henüz oyuncu yok)\n"

    text += "\n⏳ <b>Kalan oyuncular:</b>\n"
    remaining = [p for p in game.players.values() if p.team is None]
    if remaining:
        for p in remaining:
            text += f"  • {p.first_name}\n"
    else:
        text += "  Tüm oyuncular seçildi!\n"

    if game.current_turn == TeamColor.BLUE:
        text += f"\n🔵 Sıra Mavi Takımda — Kaptan {game.get_mention(game.blue_captain)} /csec ile seçim yapsın."
    elif game.current_turn == TeamColor.RED:
        text += f"\n🔴 Sıra Kırmızı Takımda — Kaptan {game.get_mention(game.red_captain)} /csec ile seçim yapsın."

    return text


def build_game_start_text(game: GameRoom) -> str:
    """Oyun başlangıç özeti."""
    text = "🎭 <b>CODENAMES — OYUN BAŞLIYOR!</b>\n\n"

    text += "🔵 <b>Mavi Takım</b>\n"
    text += f"  Kaptan: {game.get_mention(game.blue_captain)}\n"
    text += f"  Sözcü: {game.get_mention(game.blue_spokesperson)}\n"
    text += "  Oyuncular:\n"
    for i, uid in enumerate(game.blue_players, 1):
        text += f"    {i}. {game.get_mention(uid)}\n"

    text += "\n🔴 <b>Kırmızı Takım</b>\n"
    text += f"  Kaptan: {game.get_mention(game.red_captain)}\n"
    text += f"  Sözcü: {game.get_mention(game.red_spokesperson)}\n"
    text += "  Oyuncular:\n"
    for i, uid in enumerate(game.red_players, 1):
        text += f"    {i}. {game.get_mention(uid)}\n"

    text += "\n⚠️ Kaptanlar, özel mesajlarınızı kontrol edin!"
    return text


def build_clue_announcement(game: GameRoom) -> str:
    """İpucu duyuru mesajı."""
    team_emoji = "🔵" if game.current_turn == TeamColor.BLUE else "🔴"
    return f"{team_emoji} <b>İPUCU:</b> {game.clue_word.upper()} — <b>{game.clue_number}</b>"


def build_guess_info(game: GameRoom) -> str:
    """Tahmin aşaması bilgilendirme."""
    team = game.current_turn.value if game.current_turn else ""
    spokes = game.blue_spokesperson if game.current_turn == TeamColor.BLUE else game.red_spokesperson
    return (
        f"🤔 <b>{team.upper()} TAKIM — TAHMİN ZAMANI</b>\n"
        f"İpucu: <b>{game.clue_word.upper()}</b> ({game.clue_number})\n"
        f"Kalan tahmin hakkı: <b>{game.guesses_remaining}</b>\n\n"
        f"🎤 Sözcü {game.get_mention(spokes)} /ctahmin kelime ile tahmin yapsın."
    )


async def update_lobby_message(game: GameRoom, context):
    """Lobi mesajını günceller (eski mesajı düzenler)."""
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
            pass  # Mesaj silinmiş veya değişmemiş olabilir

# games/vampir/game_flow.py - Ana oyun akışı
import asyncio
import logging
from telegram.ext import ContextTypes
from games.vampir.config import ROLES, IMAGES, GamePhase
from games.vampir.state import get_game
from games.vampir.roles import assign_roles
from games.vampir.utils import safe_send_message, safe_send_photo, safe_send_pm, send_mention

logger = logging.getLogger(__name__)
_app = None

def set_app(app):
    global _app
    _app = app
    from games.vampir.night import set_app as night_set_app
    night_set_app(app)

async def start_game(context: ContextTypes.DEFAULT_TYPE, game):
    if len(game.players) < 5:
        await safe_send_message(context, game.group_id, "❌ Yeterli oyuncu yok!")
        game.reset()
        return

    # Sabit mesajı kaldır
    if game.join_message_id:
        try:
            await context.bot.unpin_chat_message(
                chat_id=game.group_id, message_id=game.join_message_id
            )
        except:
            pass
        game.join_message_id = None

    await safe_send_photo(context, game.group_id, IMAGES["START"],
        "🎬 *Oyun Başladı!*\n🌙 Roller dağıtılıyor...")

    assign_roles(game)
    game.phase = GamePhase.PLAYING

    # Rolleri özelden bildir
    failed = []
    for player in game.players.values():
        role_msg = f"🎭 *Rolün: {player.role}*\n\n"

        if player.lakap:
            role_msg += f"🏷️ Lakap: {player.lakap}\n\n"

        if "Vampir" in player.role:
            teammates = [p for p in game.players.values()
                        if "Vampir" in p.role and p.user_id != player.user_id]
            role_msg += f"🧛 Takım Arkadaşların: {', '.join([p.username for p in teammates]) if teammates else 'Tek vampir sensin!'}"
        elif "Doktor" in player.role:
            role_msg += "🩺 Köylü takımındasın. Birini koruyabilirsin."
        elif "Kurt" in player.role:
            role_msg += "🐺 Köylü takımındasın. Sadece vampirleri avlayabilirsin."
        elif player.role == ROLES["IBLIS"]:
            role_msg += "👹 Kötü takımdasın. Linç edilirsen kötüler kazanır!"
        elif player.role == ROLES["GOZCU"]:
            role_msg += "👁️ Köylü takımındasın. Birinin rolünü öğrenebilirsin."
        elif player.role == ROLES["SASKIN"]:
            role_msg += "🤪 Köylü takımındasın. Oyun rastgele kayar!"
        elif player.role == ROLES["SAPIK"]:
            role_msg += "😈 Köylü takımındasın. Birini ziyaret edebilirsin."
        elif player.role == ROLES["YARAMAZ_KIZ"]:
            role_msg += "🔥 Köylü takımındasın. Birine sürpriz yapabilirsin."
        else:
            role_msg += "👨‍🌾 Köylüsün. Vampirleri bul!"

        if not await safe_send_pm(_app, player.user_id, role_msg):
            failed.append(player.username)

    if failed:
        await safe_send_message(context, game.group_id,
            f"⚠️ Şu kişilere ulaşılamadı: {', '.join(failed)}")

    await asyncio.sleep(3)
    from games.vampir.night import start_night
    await start_night(context, game)


async def join_countdown(context: ContextTypes.DEFAULT_TYPE, game):
    group_id = game.group_id

    while game.join_time_left > 0 and game.phase == GamePhase.LOBBY:
        await asyncio.sleep(1)
        game.join_time_left -= 1

        if game.join_time_left == 30:
            await safe_send_message(context, group_id, "⚠️ 30 saniye kaldı!")
        elif game.join_time_left == 10:
            await safe_send_message(context, group_id, "🚨 10 saniye!")

    if len(game.players) >= 5 and game.phase == GamePhase.LOBBY:
        await start_game(context, game)
    else:
        await safe_send_message(context, group_id, "❌ Yeterli oyuncu yok! Oyun iptal.")
        game.reset()


def check_win_condition(game) -> bool:
    alive = game.get_alive_players()
    alive_vampires = [p for p in alive if "Vampir" in p.role]
    alive_evil = [p for p in alive if "Vampir" in p.role or p.role == ROLES["IBLIS"]]
    alive_villagers = [p for p in alive if p not in alive_evil]

    if alive_vampires and len(alive_vampires) >= len(alive_villagers):
        return True
    if not alive_vampires:
        return True
    return False


async def end_game(context: ContextTypes.DEFAULT_TYPE, game, winner: str = None):
    group_id = game.group_id
    game.set_active(False)

    alive = game.get_alive_players()
    alive_vampires = [p for p in alive if "Vampir" in p.role]

    # Kazanan belirleme
    if winner == "evil":
        winner_text = "👹 Kötü Takım"
        image = IMAGES["IBLIS_WIN"]
    elif alive_vampires:
        winner_text = "🧛‍♂️ Vampirler"
        image = IMAGES["VAMPIR_WIN"]
    else:
        winner_text = "👨‍🌾 Köylüler"
        image = IMAGES["KOYLU_WIN"]

    # Sonuç mesajı
    results = f"🏆 *{winner_text} KAZANDI!*\n\n📊 *Son Durum:*\n"
    for p in game.players.values():
        emoji = "❤️" if p.alive else "💀"
        results += f"{emoji} {p.username} - {p.role}\n"

    try:
        await safe_send_photo(context, group_id, image, results)
    except:
        await safe_send_message(context, group_id, results)

    logger.info(f"Grup {group_id}: Oyun bitti - {winner_text}")

    await asyncio.sleep(5)
    game.reset()
    await safe_send_message(context, group_id, "🔄 Oyun bitti! /wstart ile yeni oyun.")

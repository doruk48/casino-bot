# games/vampir/day.py - Gündüz aşaması mantığı
import asyncio
import logging
import random
from telegram.ext import ContextTypes
from games.vampir.config import ROLES, IMAGES, GamePhase
from games.vampir.state import get_game
from games.vampir.utils import (
    safe_send_message, safe_send_photo, send_mention, build_player_buttons
)

logger = logging.getLogger(__name__)

async def start_day(context: ContextTypes.DEFAULT_TYPE, game):
    group_id = game.group_id

    if game.phase != GamePhase.PLAYING:
        return

    game.phase = GamePhase.DAY
    game.votes = {}
    game.expected_voters = {p.user_id for p in game.get_alive_players()}

    await safe_send_message(context, group_id,
        "☀️ *GÜNDÜZ BAŞLADI!*\n\n"
        "😱 Köylüler uyandı!\n"
        "💀 Gece kurbanları var mı?\n"
        "🧛‍♂️ Tartışın ve oylayın!\n\n"
        "⏰ *Tartışma: 90 saniye*")

    if game._timer_task and not game._timer_task.done():
        game._timer_task.cancel()
    game._timer_task = asyncio.create_task(discussion_timer(context, game))


async def discussion_timer(context: ContextTypes.DEFAULT_TYPE, game):
    group_id = game.group_id

    notifications = {
        60: "⏳ 60 saniye kaldı!",
        30: "⚠️ 30 saniye kaldı!",
        10: "🚨 SON 10 SANİYE!",
    }

    for remaining in range(90, 0, -1):
        if game.phase != GamePhase.DAY:
            return
        await asyncio.sleep(1)
        if remaining in notifications:
            await safe_send_message(context, group_id, notifications[remaining])

    await safe_send_message(context, group_id, "⏰ Tartışma bitti! Oylama başlıyor...")
    await start_voting(context, game)


async def start_voting(context: ContextTypes.DEFAULT_TYPE, game):
    group_id = game.group_id

    if not game.expected_voters:
        await safe_send_message(context, group_id, "❌ Oy verecek canlı oyuncu yok!")
        await end_day(context, game)
        return

    markup = build_player_buttons(game, only_alive=True, group_id=group_id, phase="day")
    if not markup:
        await safe_send_message(context, group_id, "❌ Oy verecek kimse yok!")
        await end_day(context, game)
        return

    msg = await context.bot.send_message(
        chat_id=group_id,
        text="🗳️ *OYLAMA BAŞLADI!*\n⏰ 30 saniye",
        reply_markup=markup,
        parse_mode="Markdown",
    )
    game.vote_message_id = msg.message_id

    if game._timer_task and not game._timer_task.done():
        game._timer_task.cancel()
    game._timer_task = asyncio.create_task(voting_timer(context, game))


async def voting_timer(context: ContextTypes.DEFAULT_TYPE, game):
    group_id = game.group_id

    await asyncio.sleep(15)
    if game.phase == GamePhase.DAY:
        await safe_send_message(context, group_id,
            f"⚠️ 15 saniye kaldı! {len(game.votes)}/{len(game.expected_voters)} oy")

    await asyncio.sleep(15)
    if game.phase == GamePhase.DAY:
        await safe_send_message(context, group_id, "⏰ Oylama bitti!")
        await end_day(context, game)


async def end_day(context: ContextTypes.DEFAULT_TYPE, game):
    from games.vampir.game_flow import check_win_condition, end_game

    group_id = game.group_id

    # Butonları kapat
    if game.vote_message_id:
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=group_id, message_id=game.vote_message_id, reply_markup=None
            )
        except:
            pass
        game.vote_message_id = None

    if game.phase != GamePhase.DAY:
        return

    total = len(game.expected_voters)
    voted = len(game.votes)

    if not game.votes:
        await safe_send_message(context, group_id, "❌ Kimse oy kullanmadı!")
        game.phase = GamePhase.PLAYING
        await asyncio.sleep(3)
        from games.vampir.night import start_night
        await start_night(context, game)
        return

    # Oy sayımı
    vote_counts = {}
    for voter_id, target_id in game.votes.items():
        vote_counts[target_id] = vote_counts.get(target_id, 0) + 1

    max_votes = max(vote_counts.values())
    candidates = [uid for uid, count in vote_counts.items() if count == max_votes]

    if len(candidates) > 1:
        names = [game.players[c].username for c in candidates]
        await safe_send_message(context, group_id,
            f"⚖️ *Beraberlik!* Kimse ölmedi.\n{', '.join(names)}")
    else:
        target_id = candidates[0]
        target = game.players.get(target_id)

        if target and target.role == ROLES["IBLIS"]:
            # İblis linç edildi -> kötüler kazanır
            try:
                await safe_send_photo(context, group_id, IMAGES["IBLIS_WIN"],
                    f"👹 *İBLİS LİNÇ EDİLDİ!*\n🔥 Kötü takım kazandı!")
            except:
                await safe_send_message(context, group_id,
                    f"👹 *İBLİS LİNÇ EDİLDİ!*\n🔥 Kötü takım kazandı!")
            await end_game(context, game, winner="evil")
            return

        game.kill_player(target_id)
        await safe_send_message(context, group_id,
            f"⚰️ *Linç:* {target.username} ({target.role})\n📊 {max_votes} oy")
        await send_mention(context, group_id, target_id, "linç edildi! 💀")

    if check_win_condition(game):
        await end_game(context, game)
        return

    game.phase = GamePhase.PLAYING
    await asyncio.sleep(3)
    await safe_send_message(context, group_id, "🌙 *Yeni gece başlıyor...*")
    await asyncio.sleep(3)

    from games.vampir.night import start_night
    await start_night(context, game)


async def handle_day_vote(query, user_id, target_id, context, game):
    group_id = game.group_id
    player = game.players[user_id]
    target_player = game.players[target_id]

    if user_id in game.votes:
        await query.answer("⚠️ Zaten oy kullandın!", show_alert=True)
        return

    actual_target = target_id

    # Şaşkın özelliği
    if player.role == ROLES["SASKIN"]:
        alive = [p for p in game.get_alive_players() if p.user_id != user_id]
        if alive and random.random() < 0.5:
            actual_target = random.choice(alive).user_id
            actual_player = game.players[actual_target]
            await query.answer(f"🤪 Şaşkınsın! Oyun {actual_player.username}'e kaydı!")

    game.votes[user_id] = actual_target
    await query.answer(f"🗳️ {target_player.username} için oy verdin!")

    await safe_send_message(context, group_id,
        f"🗳️ [{player.username}](tg://user?id={user_id}) → "
        f"[{target_player.username}](tg://user?id={target_id})")

    if len(game.votes) >= len(game.expected_voters):
        if game._timer_task and not game._timer_task.done():
            game._timer_task.cancel()
        await end_day(context, game)

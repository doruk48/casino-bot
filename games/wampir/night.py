# games/vampir/night.py - Gece aşaması mantığı
import asyncio
import logging
from telegram.ext import ContextTypes
from games.vampir.config import ROLES, IMAGES
from games.vampir.state import get_game
from games.vampir.utils import (
    safe_send_message, safe_send_photo, safe_send_pm,
    send_mention, build_player_buttons
)

logger = logging.getLogger(__name__)
_app = None  # main.py'den set edilecek

def set_app(app):
    global _app
    _app = app

async def start_night(context: ContextTypes.DEFAULT_TYPE, game):
    from games.vampir.game_flow import check_win_condition, end_game

    group_id = game.group_id
    logger.info(f"Grup {group_id}: Gece başlıyor")

    await clear_night_buttons(game)

    if game.phase != game.config.GamePhase.PLAYING if hasattr(game.config, 'GamePhase') else False:
        return

    from games.vampir.config import GamePhase
    game.phase = GamePhase.NIGHT
    game.night_actions = {
        "vampire": {}, "doctor": {}, "kurt": None,
        "sapik": None, "yaramaz_kiz": None, "gozcu": None,
    }

    alive = game.get_alive_players()
    vampires = [p for p in alive if "Vampir" in p.role]
    doctors = [p for p in alive if "Doktor" in p.role]
    kurt = next((p for p in alive if "Kurt" in p.role), None)
    sapik = next((p for p in alive if p.role == ROLES["SAPIK"]), None)
    yaramaz_kiz = next((p for p in alive if p.role == ROLES["YARAMAZ_KIZ"]), None)
    gozcu = next((p for p in alive if p.role == ROLES["GOZCU"]), None)

    game.expected_voters = {
        p.user_id for p in (
            vampires + doctors +
            ([kurt] if kurt else []) +
            ([sapik] if sapik else []) +
            ([yaramaz_kiz] if yaramaz_kiz else []) +
            ([gozcu] if gozcu else [])
        )
    }

    # Her rol için özel buton gönder
    for player in alive:
        role = player.role
        if not any([
            "Vampir" in role, "Doktor" in role, "Kurt" in role,
            role == ROLES["SAPIK"], role == ROLES["YARAMAZ_KIZ"],
            role == ROLES["GOZCU"]
        ]):
            continue

        role_texts = {
            "VAMPIR": "🌑 *GECE - VAMPİR SIRA*\n\n🩸 Kimi ısıracaksın?\n⏰ 60 saniye\n⚠️ Takım arkadaşını seçemezsin!",
            "DOKTOR": "💉 *GECE - DOKTOR SIRA*\n\n⛑️ Kimi koruyacaksın?\n⏰ 60 saniye",
            "KURT": "🐺 *GECE - ALFA KURT SIRA*\n\n⚔️ Kimi avlayacaksın?\n🎯 Sadece vampirleri!\n⏰ 60 saniye",
            "SAPIK": "😈 *GECE - SAPIK SIRA*\n\n🌙 Kimin koynuna gireceksin?\n⏰ 60 saniye",
            "YARAMAZ_KIZ": "🔥 *GECE - YARAMAZ KIZ SIRA*\n\n🌙 Kime sürpriz yapacaksın?\n⏰ 60 saniye",
            "GOZCU": "👁️ *GECE - GÖZCÜ SIRA*\n\n🔍 Kimi gözlemleyeceksin?\n⏰ 60 saniye",
        }

        role_key = "VAMPIR" if "Vampir" in role else (
            "DOKTOR" if "Doktor" in role else (
                "KURT" if "Kurt" in role else role.split()[-1] if " " in role else role
            )
        )
        # Düzelt: role ROLES values'undan geliyor, emojiyi temizle
        for key, val in ROLES.items():
            if val == role:
                role_key = key
                break

        text = role_texts.get(role_key, f"🌙 *GECE*\n\nRolün: {role}\n⏰ 60 saniye")

        try:
            msg = await _app.bot.send_message(
                chat_id=player.user_id,
                text=text,
                reply_markup=build_player_buttons(game, group_id=group_id, phase="night"),
                parse_mode="Markdown",
            )
            game.night_button_messages[player.user_id] = msg.message_id
        except Exception as e:
            logger.error(f"Gece buton hatası {player.username}: {e}")

    # Grup mesajı
    extras = []
    if kurt: extras.append("🐺 Alfa Kurt avlanıyor")
    if sapik: extras.append("😈 Sapık hazırlanıyor")
    if yaramaz_kiz: extras.append("🔥 Yaramaz Kız hazırlanıyor")
    if gozcu: extras.append("👁️ Gözcü gözlemliyor")

    await safe_send_message(
        context, group_id,
        f"🌙 *GECE BAŞLADI!*\n\n"
        f"🧛‍♂️ Vampirler avlanıyor...\n"
        f"🩺 Doktor hazırlık yapıyor...\n"
        + "\n".join(extras) +
        f"\n👻 Köylüler uyuyor...\n\n"
        f"⏰ *Karar süresi: 60 saniye*"
    )

    if game._timer_task and not game._timer_task.done():
        game._timer_task.cancel()
    game._timer_task = asyncio.create_task(night_timer_60s(context, game))


async def night_timer_60s(context: ContextTypes.DEFAULT_TYPE, game):
    from games.vampir.config import GamePhase
    group_id = game.group_id

    for remaining in range(60, 0, -1):
        if game.phase != GamePhase.NIGHT:
            return
        await asyncio.sleep(1)

        if remaining == 30:
            await safe_send_message(context, group_id, "⚠️ *30 saniye kaldı!*")
        elif remaining == 10:
            await safe_send_message(context, group_id, "🚨 *SON 10 SANİYE!*")

    if game.phase != GamePhase.NIGHT:
        return

    total = (
        len(game.night_actions["vampire"]) +
        len(game.night_actions.get("doctor", {})) +
        (1 if game.night_actions["kurt"] else 0) +
        (1 if game.night_actions["gozcu"] else 0)
    )
    await safe_send_message(context, group_id,
        f"🌅 *GECE SÜRESİ DOLDU!*\n📊 {total}/{len(game.expected_voters)} oy kullanıldı")

    await end_night(context, game)


async def end_night(context: ContextTypes.DEFAULT_TYPE, game):
    from games.vampir.game_flow import check_win_condition, end_game
    from games.vampir.config import GamePhase

    group_id = game.group_id
    logger.info(f"Grup {group_id}: Gece sonu işleniyor")

    if game.phase != GamePhase.NIGHT:
        return

    await clear_night_buttons(game)

    # Gece özeti
    vamp_act = len(game.night_actions["vampire"])
    doc_act = len(game.night_actions.get("doctor", {}))
    kurt_act = bool(game.night_actions["kurt"])
    sapik_act = bool(game.night_actions["sapik"])
    yar_act = bool(game.night_actions["yaramaz_kiz"])
    goz_act = bool(game.night_actions["gozcu"])

    await safe_send_message(context, group_id,
        f"🌅 *Gece Bitti*\n\n"
        f"🧛‍♂️ Vampirler: {'ısırdı' if vamp_act > 0 else 'avlanmadı'}\n"
        f"🩺 Doktor: {doc_act} koruma\n"
        f"🐺 Kurt: {'avlandı' if kurt_act else 'avlanmadı'}\n"
        f"😈 Sapık: {'ziyaret' if sapik_act else 'ziyaret yok'}\n"
        f"🔥 Yar. Kız: {'sürpriz' if yar_act else 'sürpriz yok'}\n"
        f"👁️ Gözcü: {'gözlem' if goz_act else 'gözlem yok'}"
    )

    # Sapık bildirimi
    sapik = next((p for p in game.get_alive_players() if p.role == ROLES["SAPIK"]), None)
    sapik_target = game.night_actions.get("sapik")
    if sapik and sapik_target and sapik_target in game.players:
        target = game.players[sapik_target]
        if target.alive:
            try:
                await safe_send_photo(context, target.user_id, IMAGES["ROMANTIC"],
                    f"🔥 *Gece Ziyaretçin!*\n😈 {sapik.username} odana girdi...")
            except:
                await safe_send_message(context, target.user_id,
                    f"🔥 *Gece Ziyaretçin!*\n😈 {sapik.username} odana girdi...")

    # Yaramaz Kız bildirimi
    yk = next((p for p in game.get_alive_players() if p.role == ROLES["YARAMAZ_KIZ"]), None)
    yk_target = game.night_actions.get("yaramaz_kiz")
    if yk and yk_target and yk_target in game.players:
        target = game.players[yk_target]
        if target.alive:
            try:
                await safe_send_photo(context, target.user_id, IMAGES["YARAMAZ_KIZ"],
                    f"💃 *Sürpriz Ziyaret!*\n🔥 {yk.username} kapını çaldı...")
            except:
                await safe_send_message(context, target.user_id,
                    f"💃 *Sürpriz Ziyaret!*\n🔥 {yk.username} kapını çaldı...")

    # Doktor korumalarını topla
    protected = set()
    for doc_id, target_id in game.night_actions.get("doctor", {}).items():
        if target_id in game.players and game.players[target_id].alive:
            protected.add(target_id)

    # Kurt hedefi
    deaths = set()
    kurt_target = game.night_actions["kurt"]
    if kurt_target and kurt_target in game.players and game.players[kurt_target].alive:
        kurt_player = game.players[kurt_target]
        if "Vampir" in kurt_player.role and kurt_target not in protected:
            deaths.add(kurt_target)

    # Vampir saldırıları
    victims = set()
    for vamp_id, target_id in game.night_actions["vampire"].items():
        if target_id in game.players and game.players[target_id].alive:
            victims.add(target_id)

    for victim_id in victims:
        if victim_id not in protected and victim_id not in deaths:
            deaths.add(victim_id)

    # Ölümleri uygula
    if deaths:
        death_msg = "💀 *Gece Kurbanları:*\n"
        for death_id in deaths:
            game.kill_player(death_id)
            player_name = game.players[death_id].username
            death_msg += f"• {player_name} ({game.players[death_id].role})\n"
            await send_mention(context, group_id, death_id, "gece öldürüldü! 💀")
        await safe_send_message(context, group_id, death_msg)
    else:
        await safe_send_message(context, group_id, "🌙 Gece sakin geçti...")

    # Koruma bildirimi
    successful = [pid for pid in protected if pid in victims]
    if successful:
        await safe_send_message(context, group_id,
            "🛡️ *Doktorlar birini vampir saldırısından kurtardı!*")

    if check_win_condition(game):
        await end_game(context, game)
        return

    game.phase = GamePhase.PLAYING
    await asyncio.sleep(3)

    from games.vampir.day import start_day
    await start_day(context, game)


async def handle_night_action(query, user_id, target_id, context, game):
    group_id = game.group_id
    player = game.players[user_id]
    target_player = game.players[target_id]

    # Takım arkadaşı kontrolü
    if player.role == target_player.role and player.role != ROLES["KOYLU"] and "Doktor" not in player.role:
        await query.answer("⚠️ Takım arkadaşına aksiyon uygulayamazsın!", show_alert=True)
        return

    action_msg = ""
    role_key = None
    for key, val in ROLES.items():
        if val == player.role:
            role_key = key
            break

    if role_key == "GOZCU":
        if game.night_actions.get("gozcu"):
            await query.answer("⚠️ Zaten gözlemledin!", show_alert=True)
            return
        game.night_actions["gozcu"] = target_id
        await safe_send_pm(_app, user_id,
            f"👁️ *Gözlem:* {target_player.username}\n🎭 Rolü: {target_player.role}")
        action_msg = f"👁️ {target_player.username} gözlemlendi!"

    elif role_key == "VAMPIR":
        if user_id in game.night_actions["vampire"]:
            await query.answer("⚠️ Zaten oy kullandın!", show_alert=True)
            return
        game.night_actions["vampire"][user_id] = target_id
        action_msg = f"🩸 {target_player.username} ısırıldı!"

    elif role_key == "DOKTOR":
        if user_id in game.night_actions.get("doctor", {}):
            await query.answer("⚠️ Zaten koruma seçtin!", show_alert=True)
            return
        game.night_actions["doctor"][user_id] = target_id
        action_msg = f"⛑️ {target_player.username} korundu!"

    elif role_key == "KURT":
        if game.night_actions["kurt"]:
            await query.answer("⚠️ Zaten av seçtin!", show_alert=True)
            return
        game.night_actions["kurt"] = target_id
        action_msg = f"🐺 {target_player.username} avlandı!"

    elif role_key == "SAPIK":
        if game.night_actions["sapik"]:
            await query.answer("⚠️ Zaten seçtin!", show_alert=True)
            return
        game.night_actions["sapik"] = target_id
        action_msg = f"😈 {target_player.username}'e girildi!"

    elif role_key == "YARAMAZ_KIZ":
        if game.night_actions["yaramaz_kiz"]:
            await query.answer("⚠️ Zaten seçtin!", show_alert=True)
            return
        game.night_actions["yaramaz_kiz"] = target_id
        action_msg = f"🔥 {target_player.username}'e sürpriz!"

    else:
        await query.answer("❌ Bu aşamada oy kullanamazsın!", show_alert=True)
        return

    await safe_send_pm(_app, user_id, f"🎯 *Kararın:* {target_player.username}")
    await query.answer(action_msg)


async def clear_night_buttons(game):
    for player in game.get_alive_players():
        if player.user_id in game.night_button_messages:
            try:
                await safe_send_pm(_app, player.user_id,
                    "🔒 *Gece oylaması kapandı!*\n🌅 Gündüz başlıyor...")
            except:
                pass
    game.night_button_messages.clear()

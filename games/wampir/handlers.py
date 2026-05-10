# games/vampir/handlers.py - Komut ve callback handler'ları
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes

from games.vampir.config import GamePhase
from games.vampir.state import games, state_lock, get_game
from games.vampir.utils import (
    safe_send_message, safe_send_pm, send_mention,
    build_join_button, build_player_buttons
)
from games.vampir.game_flow import start_game, join_countdown, set_app as flow_set_app

logger = logging.getLogger(__name__)
_app = None

def set_app(app):
    global _app
    _app = app
    flow_set_app(app)


# ═══════════════════════════════════════════════════════════════
# KOMUT HANDLER'LARI
# ═══════════════════════════════════════════════════════════════

async def cmd_wstart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with state_lock:
        chat = update.effective_chat
        group_id = chat.id

        if chat.type not in ["group", "supergroup"]:
            await update.message.reply_text("❌ Sadece grupta kullanılabilir!")
            return

        game = get_game(group_id)
        if game.is_active():
            await update.message.reply_text("❌ Zaten bir oyun devam ediyor!")
            return

        game.reset()
        game.group_id = group_id
        game.started_by = update.effective_user.id
        game.set_active(True)
        game.phase = GamePhase.LOBBY

        # Katılma mesajı gönder ve sabitle
        join_text = (
            "🧛‍♂️ *Vampir Köylü Oyunu Başladı!*\n\n"
            "👥 Butona tıklayarak katılın!\n"
            "⚡ En az 5 kişi gerekiyor.\n"
            "⏰ 5. oyuncudan sonra 60 saniye"
        )
        msg = await context.bot.send_message(
            chat_id=group_id,
            text=join_text,
            reply_markup=build_join_button(),
            parse_mode="Markdown",
        )
        try:
            await context.bot.pin_chat_message(chat_id=group_id, message_id=msg.message_id)
        except:
            pass
        game.join_message_id = msg.message_id
        logger.info(f"🎮 Grup {group_id}: Oyun başlatıldı")


async def cmd_wjoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    group_id = chat.id

    if group_id not in games:
        await update.message.reply_text("❌ Aktif oyun yok! /wstart")
        return

    game = games[group_id]
    if not game.is_active() or game.phase != GamePhase.LOBBY:
        await update.message.reply_text("❌ Oyuna katılamazsın!")
        return

    if user.id in game.players:
        await update.message.reply_text("❌ Zaten oyundasın!")
        return

    try:
        test_msg = await context.bot.send_message(chat_id=user.id, text="🔍 Kontrol...")
        await context.bot.delete_message(chat_id=user.id, message_id=test_msg.message_id)

        game.add_player(user.id, user.first_name or user.username or "Bilinmeyen")
        await update.message.reply_text(f"✅ {user.first_name} katıldı!")
        await update_join_message(context, game)

        if len(game.players) == 5:
            if game._join_timer_task and not game._join_timer_task.done():
                game._join_timer_task.cancel()
            game.join_time_left = 60
            game._join_timer_task = asyncio.create_task(join_countdown(context, game))
            await safe_send_message(context, group_id, "🎉 5 kişi! 60 saniye...")

    except Exception as e:
        logger.error(f"PM hatası: {e}")
        await update.message.reply_text(
            f"🤖 Önce bota özelden /start yaz:\n"
            f"https://t.me/Wwampir_bot",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🤖 Bota Git", url="https://t.me/Wwampir_bot")
            ]])
        )


async def cmd_wbaslat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    group_id = update.effective_chat.id

    if group_id not in games:
        await update.message.reply_text("❌ Aktif oyun yok!")
        return

    game = games[group_id]
    if game.started_by != user_id:
        await update.message.reply_text("❌ Sadece başlatan kişi!")
        return
    if game.phase != GamePhase.LOBBY:
        await update.message.reply_text("❌ Oyun zaten başladı!")
        return
    if len(game.players) < 5:
        await update.message.reply_text("❌ En az 5 oyuncu gerek!")
        return

    if game._join_timer_task and not game._join_timer_task.done():
        game._join_timer_task.cancel()

    await update.message.reply_text("🚀 Oyun hemen başlatılıyor!")
    await start_game(context, game)


async def cmd_wson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    group_id = update.effective_chat.id

    game = get_game(group_id)
    if game.started_by != user_id:
        await update.message.reply_text("❌ Sadece başlatan iptal edebilir!")
        return

    game.reset()
    await update.message.reply_text("🛑 Oyun iptal edildi!")


async def cmd_wextend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    group_id = update.effective_chat.id

    if group_id not in games:
        await update.message.reply_text("❌ Aktif oyun yok!")
        return

    game = games[group_id]
    if not context.args:
        await update.message.reply_text("❌ /wextend <dakika>")
        return

    try:
        minutes = int(context.args[0])
        if minutes < 1 or minutes > 10:
            await update.message.reply_text("❌ 1-10 dakika")
            return

        if game.total_extra_time + minutes > 10:
            await update.message.reply_text(f"❌ Max 10 dakika! Kalan: {10 - game.total_extra_time}")
            return

        game.join_time_left += minutes * 60
        game.total_extra_time += minutes

        if game._join_timer_task and not game._join_timer_task.done():
            game._join_timer_task.cancel()

        if len(game.players) >= 5:
            game._join_timer_task = asyncio.create_task(join_countdown(context, game))

        await update.message.reply_text(
            f"⏰ +{minutes} dakika!\n"
            f"Toplam: {game.total_extra_time}/10\n"
            f"Süre: {game.join_time_left}s"
        )
    except ValueError:
        await update.message.reply_text("❌ Geçersiz sayı!")


async def cmd_whelp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧛‍♂️ *Vampir Köylü Komutları*\n\n"
        "🎮 /wstart - Oyun başlat\n"
        "👤 /wjoin - Oyuna katıl\n"
        "🚀 /wbaslat - Hemen başlat\n"
        "🛑 /wson - İptal et\n"
        "⏰ /wextend <dk> - Süre ekle\n"
        "📢 /wtag <mesaj> - Etiketle\n"
        "📖 /wnasiloynanir - Kurallar",
        parse_mode="Markdown"
    )


async def cmd_wnasiloynanir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧛‍♂️ *Vampir Köylü - Kurallar*\n\n"
        "👥 En az 5 oyuncu\n"
        "🌙 Gece: Vampirler ısırır, Doktor korur, Kurt avlar\n"
        "☀️ Gündüz: Tartışma + oylama\n"
        "🏆 Vampirler: Köylü sayısını geç\n"
        "🏆 Köylüler: Tüm vampirleri öldür\n"
        "👹 İblis linç edilirse kötüler kazanır!",
        parse_mode="Markdown"
    )


async def cmd_wtag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_id = update.effective_chat.id
    if group_id not in games:
        await update.message.reply_text("❌ Aktif oyun yok!")
        return

    game = games[group_id]
    mentions = []
    for p in list(game.players.values())[:15]:
        mentions.append(f"[{p.username}](tg://user?id={p.user_id})")

    if not mentions:
        await update.message.reply_text("❌ Etiketlenecek oyuncu yok!")
        return

    msg = "📢 *Oyuna katılanlar:*\n" + " ".join(mentions)
    await update.message.reply_text(msg, parse_mode="Markdown")


async def update_join_message(context, game):
    if not game.join_message_id:
        return

    try:
        text = "🎮 *Katılan Oyuncular:*\n"
        for i, p in enumerate(game.players.values(), 1):
            text += f"{i}. {p.username}\n"
        text += f"\n📊 {len(game.players)}/5 kişi"

        await context.bot.edit_message_text(
            chat_id=game.group_id,
            message_id=game.join_message_id,
            text=text,
            reply_markup=build_join_button(),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Join mesaj güncelleme hatası: {e}")


# ═══════════════════════════════════════════════════════════════
# CALLBACK HANDLER
# ═══════════════════════════════════════════════════════════════

async def vampir_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user

    # --- KATILMA BUTONLARI ---
    if data == "vampir_join":
        group_id = query.message.chat_id
        if group_id not in games:
            await query.answer("❌ Oyun aktif değil!", show_alert=True)
            return
        game = games[group_id]

        if not game.is_active() or game.phase != GamePhase.LOBBY:
            await query.answer("❌ Oyun aktif değil!", show_alert=True)
            return
        if user.id in game.players:
            await query.answer("❌ Zaten oyundasınız!", show_alert=True)
            return

        try:
            test_msg = await context.bot.send_message(chat_id=user.id, text="🔍 Kontrol...")
            await context.bot.delete_message(chat_id=user.id, message_id=test_msg.message_id)

            game.add_player(user.id, user.first_name or user.username or "Bilinmeyen")
            await query.answer("🎉 Katıldınız!")
            await update_join_message(context, game)

            if len(game.players) == 5:
                if game._join_timer_task and not game._join_timer_task.done():
                    game._join_timer_task.cancel()
                game.join_time_left = 60
                game._join_timer_task = asyncio.create_task(join_countdown(context, game))

        except:
            await query.answer("🤖 Önce bota /start yazın!", show_alert=True)
        return

    # --- PM JOIN ---
    if data.startswith("vampir_pm_join_"):
        parts = data.split("_")
        try:
            group_id = int(parts[3])
        except:
            await query.answer("❌ Geçersiz!", show_alert=True)
            return

        if group_id not in games:
            await query.answer("❌ Oyun aktif değil!", show_alert=True)
            return

        game = games[group_id]
        if user.id in game.players:
            await query.answer("❌ Zaten oyundasınız!", show_alert=True)
            return

        game.add_player(user.id, user.first_name or user.username or "Bilinmeyen")
        await query.answer("🎉 Katıldınız!")
        await update_join_message(context, game)
        return

    # --- TARGET BUTONLARI ---
    if data.startswith("vampir_target_"):
        parts = data.split("_")
        try:
            group_id = int(parts[2])
            target_id = int(parts[3])
            phase = parts[4]
        except:
            await query.answer("❌ Geçersiz!", show_alert=True)
            return

        if group_id not in games:
            await query.answer("❌ Oyun yok!", show_alert=True)
            return

        game = games[group_id]
        user_id = user.id

        if not game.is_active():
            await query.answer("❌ Oyun yok!", show_alert=True)
            return
        if user_id not in game.players:
            await query.answer("❌ Oyunda değilsiniz!", show_alert=True)
            return

        player = game.players[user_id]
        if not player.alive:
            await query.answer("💀 Ölüsünüz!", show_alert=True)
            return

        target = game.players.get(target_id)
        if not target or not target.alive:
            await query.answer("❌ Ölüye oy veremezsiniz!", show_alert=True)
            return

        current_phase = "night" if game.phase == GamePhase.NIGHT else (
            "day" if game.phase == GamePhase.DAY else "other"
        )
        if phase != current_phase:
            await query.answer("⏰ Süre doldu!", show_alert=True)
            return

        if game.phase == GamePhase.NIGHT:
            from games.vampir.night import handle_night_action
            await handle_night_action(query, user_id, target_id, context, game)
        elif game.phase == GamePhase.DAY:
            from games.vampir.day import handle_day_vote
            await handle_day_vote(query, user_id, target_id, context, game)


# ═══════════════════════════════════════════════════════════════
# REGISTER
# ═══════════════════════════════════════════════════════════════

def register_handlers(app):
    global _app
    _app = app
    set_app(app)

    app.add_handler(CommandHandler("wstart", cmd_wstart))
    app.add_handler(CommandHandler("wjoin", cmd_wjoin))
    app.add_handler(CommandHandler("wbaslat", cmd_wbaslat))
    app.add_handler(CommandHandler("wson", cmd_wson))
    app.add_handler(CommandHandler("wextend", cmd_wextend))
    app.add_handler(CommandHandler("whelp", cmd_whelp))
    app.add_handler(CommandHandler("wnasiloynanir", cmd_wnasiloynanir))
    app.add_handler(CommandHandler("wtag", cmd_wtag))
    app.add_handler(CallbackQueryHandler(vampir_callback, pattern=r"^vampir_"))
    logger.info("🧛 Vampir Köylü handler'ları kaydedildi!")

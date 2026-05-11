# games/vampir/handlers.py - Para sistemi ve /wstart <miktar> desteği
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes

from games.vampir.engine import (
    games, state_lock, get_game, GamePhase, IMAGES,
    send_msg, send_pm, join_btn, update_join_msg,
    start_game, join_countdown, handle_night_act, handle_day_vote,
)
from games.vampir.economy import format_money

logger = logging.getLogger(__name__)
_app = None

# ═══════════════════════════════════════════════════════════════
# KOMUTLAR
# ═══════════════════════════════════════════════════════════════

async def cmd_wstart(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ["group", "supergroup"]:
        return await update.message.reply_text("❌ Bu komut sadece grupta kullanılabilir!")

    async with state_lock:
        gid = chat.id
        game = get_game(gid)
        if game.is_active():
            return await update.message.reply_text("❌ Bu grupta zaten bir oyun devam ediyor!")

        # 🆕 Giriş ücreti kontrolü
        buy_in = 0  # Ücretsiz
        if ctx.args:
            arg = ctx.args[0].lower()
            if arg == "allin":
                # allin - oyuncular tüm bakiyeleriyle girer (sonra uygulanacak)
                buy_in = 0  # Şimdilik ücretsiz
            else:
                try:
                    buy_in = int(arg)
                    if buy_in < 0:
                        return await update.message.reply_text("❌ Geçersiz miktar!")
                    if buy_in > 0 and buy_in < 1000:
                        return await update.message.reply_text("❌ Minimum giriş: 1,000 🪙BTK")
                except ValueError:
                    return await update.message.reply_text("❌ Geçerli bir sayı girin!\nÖrnek: /wstart 1000000")

        game.reset()
        game.group_id = gid
        game.started_by = update.effective_user.id
        game.set_active(True)
        game.buy_in = buy_in  # 🆕

        # Mesajı hazırla
        if buy_in > 0:
            start_msg = (
                "🧛‍♂️ *Vampir Köylü Oyunu Başladı!*\n\n"
                f"💰 *Giriş Ücreti:* {format_money(buy_in)}\n"
                "👥 Aşağıdaki butona tıklayarak oyuna katılın!\n"
                "⚡ En az 5 kişi gerekiyor.\n"
                "⏰ 5. oyuncudan sonra 60 saniye bekleme süresi başlar.\n\n"
                "🎮 *Katılan Oyuncular:*\n"
                "Henüz kimse katılmadı..."
            )
        else:
            start_msg = (
                "🧛‍♂️ *Vampir Köylü Oyunu Başladı!*\n\n"
                "🎮 *Ücretsiz Oyun*\n"
                "👥 Aşağıdaki butona tıklayarak oyuna katılın!\n"
                "⚡ En az 5 kişi gerekiyor.\n"
                "⏰ 5. oyuncudan sonra 60 saniye bekleme süresi başlar.\n\n"
                "🎮 *Katılan Oyuncular:*\n"
                "Henüz kimse katılmadı..."
            )

        msg = await ctx.bot.send_message(
            chat_id=gid,
            text=start_msg,
            reply_markup=join_btn(),
            parse_mode="Markdown"
        )
        try:
            await ctx.bot.pin_chat_message(chat_id=gid, message_id=msg.message_id)
        except:
            pass
        game.join_message_id = msg.message_id
        logger.info(f"🎮 Grup {gid}: Oyun başlatıldı | Giriş: {buy_in:,} BTK")


async def cmd_wjoin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    chat = update.effective_chat
    gid = chat.id

    if gid not in games:
        return await update.message.reply_text("❌ Aktif oyun yok! /wstart ile başlatın.")

    game = games[gid]
    if not game.is_active() or game.phase != GamePhase.LOBBY:
        return await update.message.reply_text("❌ Şu anda oyuna katılamazsınız!")

    if u.id in game.players:
        return await update.message.reply_text("❌ Zaten oyundasınız!")

    # 🆕 Paralı oyunda bakiye kontrolü
    if game.buy_in > 0:
        try:
            from core.economy import get_balance, remove_balance
            from core.users import get_or_create_user

            await get_or_create_user(u.id, u.username, u.full_name)
            bal = await get_balance(u.id)

            if bal < game.buy_in:
                return await update.message.reply_text(
                    f"❌ Yetersiz bakiye!\n"
                    f"💰 Giriş: {format_money(game.buy_in)}\n"
                    f"💳 Bakiyen: {format_money(bal)}"
                )
        except Exception as e:
            logger.error(f"Bakiye kontrol hatası: {e}")
            return await update.message.reply_text("❌ Bakiye kontrolü yapılamadı!")

    # PM kontrolü
    try:
        test = await ctx.bot.send_message(u.id, "🔍 Kontrol ediliyor...")
        await ctx.bot.delete_message(chat_id=u.id, message_id=test.message_id)

        # 🆕 Giriş ücretini tahsil et
        if game.buy_in > 0:
            try:
                await remove_balance(u.id, game.buy_in, "vampir_giris", f"Vampir Köylü giriş")
            except:
                return await update.message.reply_text("❌ Giriş ücreti alınamadı!")

        game.add_player(u.id, u.first_name or u.username or "Bilinmeyen")
        await update.message.reply_text(f"✅ *{u.first_name}* oyuna katıldı! 🎉", parse_mode="Markdown")
        await update_join_msg(ctx, game)

        if len(game.players) == 5:
            if game._join_timer_task and not game._join_timer_task.done():
                game._join_timer_task.cancel()
            game.join_time_left = 60
            game._join_timer_task = asyncio.create_task(join_countdown(ctx, game, _app))
            await send_msg(ctx, gid, "🎉 5 kişi tamamlandı!\n⏳ 60 saniye içinde oyun başlayacak.")

    except Exception as e:
        logger.error(f"PM hatası: {e}")
        await update.message.reply_text(
            f"🤖 *{u.first_name}*, önce botu başlatmalısın!\n\n"
            f"👇 Butona tıkla ve Start yap:\n"
            f"1. Butona tıkla\n2. 'Başlat' de\n3. /start yaz\n4. Buraya dön ve tekrar /wjoin yaz!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🤖 BOTU AÇ", url="https://t.me/Wwampir_bot")
            ]]),
            parse_mode="Markdown"
        )

        # 🆕 Giriş ücreti iadesi
        if game.buy_in > 0 and u.id in game.players:
            try:
                from core.economy import add_balance
                await add_balance(u.id, game.buy_in, "vampir_iade", "Vampir Köylü giriş iadesi")
                del game.players[u.id]
            except:
                pass


async def cmd_wbaslat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if gid not in games:
        return await update.message.reply_text("❌ Aktif oyun yok!")

    game = games[gid]
    if update.effective_user.id != game.started_by:
        return await update.message.reply_text("❌ Sadece oyunu başlatan kişi hemen başlatabilir!")
    if game.phase != GamePhase.LOBBY:
        return await update.message.reply_text("❌ Oyun zaten başladı!")
    if len(game.players) < 5:
        return await update.message.reply_text("❌ En az 5 oyuncu gerekli!")

    if game._join_timer_task and not game._join_timer_task.done():
        game._join_timer_task.cancel()

    await update.message.reply_text("🚀 *Oyun Hemen Başlatılıyor!*", parse_mode="Markdown")
    await start_game(ctx, game, _app)


async def cmd_wson(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    game = get_game(gid)
    if update.effective_user.id != game.started_by:
        return await update.message.reply_text("❌ Sadece oyunu başlatan iptal edebilir!")

    # 🆕 Ücret iadesi
    if game.buy_in > 0 and game.phase == GamePhase.LOBBY:
        try:
            from core.economy import add_balance
            for uid in game.players:
                await add_balance(uid, game.buy_in, "vampir_iade", "Vampir Köylü iptal iadesi")
        except Exception as e:
            logger.error(f"İade hatası: {e}")

    game.reset()
    await update.message.reply_text("🛑 Oyun iptal edildi! Giriş ücretleri iade edildi.")


async def cmd_wextend(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if gid not in games:
        return await update.message.reply_text("❌ Aktif oyun yok!")

    game = games[gid]
    if update.effective_user.id != game.started_by:
        return await update.message.reply_text("❌ Sadece oyunu başlatan süre ekleyebilir!")
    if game.phase != GamePhase.LOBBY:
        return await update.message.reply_text("❌ Sadece lobi aşamasında süre eklenebilir!")

    if not ctx.args:
        return await update.message.reply_text("❌ Kullanım: /wextend <dakika>")

    try:
        m = int(ctx.args[0])
        if m < 1 or m > 10:
            return await update.message.reply_text("❌ 1-10 dakika arası girebilirsiniz!")
        if game.total_extra_time + m > 10:
            return await update.message.reply_text(f"❌ Toplam en fazla 10 dakika! Kalan: {10 - game.total_extra_time}")

        game.join_time_left += m * 60
        game.total_extra_time += m

        if game._join_timer_task and not game._join_timer_task.done():
            game._join_timer_task.cancel()
        if len(game.players) >= 5:
            game._join_timer_task = asyncio.create_task(join_countdown(ctx, game, _app))

        await update.message.reply_text(
            f"⏰ *+{m} DAKİKA EKLENDİ!*\n"
            f"🕒 Yeni süre: {game.join_time_left} saniye\n"
            f"📊 Toplam eklenen: {game.total_extra_time}/10 dakika",
            parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("❌ Geçerli bir sayı girin!")


async def cmd_whelp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧛‍♂️ *Vampir Köylü - Komutlar*\n\n"
        "🎮 *Oyun Yönetimi:*\n"
        "• /wstart - Ücretsiz oyun başlat\n"
        "• /wstart <miktar> - Paralı oyun başlat\n"
        "• /wjoin - Oyuna katıl\n"
        "• /wbaslat - Oyunu hemen başlat\n"
        "• /wson - Oyunu iptal et\n"
        "• /wextend <dk> - Süre ekle\n\n"
        "📋 *Bilgi:*\n"
        "• /wnasiloynanir - Oyun kuralları\n"
        "• /whelp - Bu menü\n"
        "• /wtag - Oyuncuları etiketle",
        parse_mode="Markdown"
    )


async def cmd_wnasiloynanir(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧛‍♂️ *Vampir Köylü - Nasıl Oynanır?*\n\n"
        "👥 En az 5 oyuncu ile oynanır.\n\n"
        "🎮 *Ücretsiz Oyun:* /wstart\n"
        "💰 *Paralı Oyun:* /wstart <miktar>\n\n"
        "🌙 *Gece:* Vampirler ısırır, Doktor korur, "
        "Kurt avlar, Hırsız çalar, Bekçi korur...\n\n"
        "☀️ *Gündüz:* 90 saniye tartışma, 30 saniye oylama.\n\n"
        "🏆 *Kazanma:* Vampirler köylü sayısını geçerse kazanır.\n"
        "👹 İblis linç edilirse kötü takım kazanır!",
        parse_mode="Markdown"
    )


async def cmd_wtag(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if gid not in games:
        return await update.message.reply_text("❌ Aktif oyun yok!")

    game = games[gid]
    if not game.players:
        return await update.message.reply_text("❌ Henüz oyuncu yok!")

    tags = "📢 *Oyuncular:*\n"
    for p in list(game.players.values())[:20]:
        tags += f"• [{p.username}](tg://user?id={p.user_id})\n"

    await update.message.reply_text(tags, parse_mode="Markdown")


# ═══════════════════════════════════════════════════════════════
# CALLBACK
# ═══════════════════════════════════════════════════════════════

async def vampir_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    u = q.from_user

    # === JOIN ===
    if d == "vampir_join":
        gid = q.message.chat.id
        if gid not in games:
            return await q.answer("❌ Oyun aktif değil!", show_alert=True)

        game = games[gid]
        if not game.is_active() or game.phase != GamePhase.LOBBY:
            return await q.answer("❌ Oyun aktif değil!", show_alert=True)
        if u.id in game.players:
            return await q.answer("❌ Zaten oyundasınız!", show_alert=True)

        # 🆕 Paralı oyunda bakiye kontrolü
        if game.buy_in > 0:
            try:
                from core.economy import get_balance, remove_balance
                from core.users import get_or_create_user

                await get_or_create_user(u.id, u.username, u.full_name)
                bal = await get_balance(u.id)

                if bal < game.buy_in:
                    return await q.answer(
                        f"❌ Yetersiz bakiye! Giriş: {format_money(game.buy_in)} | Bakiyen: {format_money(bal)}",
                        show_alert=True
                    )
            except:
                return await q.answer("❌ Bakiye kontrolü yapılamadı!", show_alert=True)

        # PM kontrolü
        try:
            test = await ctx.bot.send_message(u.id, "🔍 Kontrol...")
            await ctx.bot.delete_message(chat_id=u.id, message_id=test.message_id)
        except:
            return await q.answer("🤖 Önce bota /start yazın!", show_alert=True)

        # 🆕 Giriş ücretini tahsil et
        if game.buy_in > 0:
            try:
                await remove_balance(u.id, game.buy_in, "vampir_giris", "Vampir Köylü giriş")
            except:
                return await q.answer("❌ Giriş ücreti alınamadı!", show_alert=True)

        game.add_player(u.id, u.first_name or u.username or "?")
        await q.answer("🎉 Katıldınız!")
        await update_join_msg(ctx, game)

        if len(game.players) == 5:
            if game._join_timer_task and not game._join_timer_task.done():
                game._join_timer_task.cancel()
            game.join_time_left = 60
            game._join_timer_task = asyncio.create_task(join_countdown(ctx, game, _app))
        return

    # === PM JOIN ===
    if d.startswith("vampir_pm_"):
        parts = d.split("_")
        try:
            gid = int(parts[2])
        except:
            return
        if gid not in games:
            return
        game = games[gid]
        game.add_player(u.id, u.first_name or "?")
        await q.answer("🎉 Katıldınız!")
        await update_join_msg(ctx, game)
        return

    # === TARGET ===
    if d.startswith("vampir_t_"):
        parts = d.split("_")
        try:
            gid = int(parts[2])
            tid = int(parts[3])
            phase = parts[4]
        except:
            return await q.answer("❌ Geçersiz buton!", show_alert=True)

        if gid not in games:
            return await q.answer("❌ Oyun yok!", show_alert=True)

        game = games[gid]
        uid = u.id

        if not game.is_active():
            return await q.answer("❌ Oyun aktif değil!", show_alert=True)
        if uid not in game.players:
            return await q.answer("❌ Oyunda değilsiniz!", show_alert=True)
        if not game.players[uid].alive:
            return await q.answer("💀 Ölüler oy kullanamaz!", show_alert=True)
        if tid not in game.players or not game.players[tid].alive:
            return await q.answer("❌ Ölüye oy veremezsiniz!", show_alert=True)

        now = "night" if game.phase == GamePhase.NIGHT else ("day" if game.phase == GamePhase.DAY else "other")
        if phase != now:
            return await q.answer("⏰ Bu butonun süresi doldu!", show_alert=True)

        if game.phase == GamePhase.NIGHT:
            await handle_night_act(q, uid, tid, ctx, game, _app)
        else:
            await handle_day_vote(q, uid, tid, ctx, game, _app)


# ═══════════════════════════════════════════════════════════════
# REGISTER
# ═══════════════════════════════════════════════════════════════
def register_handlers(app):
    global _app
    _app = app

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

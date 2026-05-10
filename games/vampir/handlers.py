# games/vampir/handlers.py - Komut ve callback handler'ları
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes

from games.vampir.engine import (
    games, state_lock, get_game, GamePhase, IMAGES,
    send_msg, send_pm, join_btn, start_game, join_countdown
)
from config import BOT_TOKEN

logger = logging.getLogger(__name__)
_app = None

# ═══════════════════════════════════════════════════════════════
# KOMUTLAR
# ═══════════════════════════════════════════════════════════════
async def cmd_wstart(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    async with state_lock:
        chat = update.effective_chat
        if chat.type not in ["group", "supergroup"]:
            return await update.message.reply_text("❌ Sadece grupta!")

        gid = chat.id
        game = get_game(gid)
        if game.is_active():
            return await update.message.reply_text("❌ Oyun zaten var!")

        game.reset()
        game.group_id = gid
        game.started_by = update.effective_user.id
        game.set_active(True)

        msg = await ctx.bot.send_message(
            chat_id=gid,
            text="🧛‍♂️ *Vampir Köylü*\n👥 Katılmak için butona bas!\n⚡ En az 5 kişi",
            reply_markup=join_btn(),
            parse_mode="Markdown"
        )
        try: await ctx.bot.pin_chat_message(chat_id=gid, message_id=msg.message_id)
        except: pass
        game.join_message_id = msg.message_id

async def cmd_wjoin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    gid = update.effective_chat.id
    if gid not in games: return await update.message.reply_text("❌ Oyun yok!")

    game = games[gid]
    if not game.is_active() or game.phase != GamePhase.LOBBY:
        return await update.message.reply_text("❌ Katılamazsın!")

    if not game.add_player(u.id, u.first_name or u.username or "?"):
        return await update.message.reply_text("❌ Zaten oyundasın!")

    try:
        await ctx.bot.send_message(u.id, "✅ Katıldın!")
    except:
        return await update.message.reply_text("❌ Önce bota /start yaz!")

    await update.message.reply_text(f"✅ {u.first_name} katıldı!")
    await update_join(ctx, game)

    if len(game.players) == 5:
        if game._join_timer_task and not game._join_timer_task.done(): game._join_timer_task.cancel()
        game.join_time_left = 60
        game._join_timer_task = asyncio.create_task(join_countdown(ctx, game, _app))

async def cmd_wbaslat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if gid not in games: return await update.message.reply_text("❌ Oyun yok!")
    game = games[gid]
    if update.effective_user.id != game.started_by: return await update.message.reply_text("❌ Sadece başlatan!")
    if len(game.players) < 5: return await update.message.reply_text("❌ En az 5 kişi!")
    if game._join_timer_task and not game._join_timer_task.done(): game._join_timer_task.cancel()
    await update.message.reply_text("🚀 Başlatılıyor!")
    await start_game(ctx, game, _app)

async def cmd_wson(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    game = get_game(update.effective_chat.id)
    if update.effective_user.id != game.started_by: return await update.message.reply_text("❌ Sadece başlatan!")
    game.reset()
    await update.message.reply_text("🛑 İptal edildi!")

async def cmd_whelp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧛 /wstart /wjoin /wbaslat /wson /wextend /whelp /wnasiloynanir /wtag", parse_mode="Markdown")

async def cmd_wnasiloynanir(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧛‍♂️ Vampir Köylü kuralları... /whelp ile komutları gör.", parse_mode="Markdown")

async def cmd_wextend(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if gid not in games: return await update.message.reply_text("❌ Oyun yok!")
    game = games[gid]
    if not ctx.args: return await update.message.reply_text("❌ /wextend <dakika>")
    try:
        m = int(ctx.args[0])
        game.join_time_left += m * 60
        game.total_extra_time += m
        await update.message.reply_text(f"⏰ +{m} dakika!")
    except:
        await update.message.reply_text("❌ Sayı gir!")

async def cmd_wtag(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if gid not in games: return await update.message.reply_text("❌ Oyun yok!")
    game = games[gid]
    tags = " ".join([f"[{p.username}](tg://user?id={p.user_id})" for p in list(game.players.values())[:15]])
    await update.message.reply_text(f"📢 {tags}", parse_mode="Markdown")

# ═══════════════════════════════════════════════════════════════
# YARDIMCI
# ═══════════════════════════════════════════════════════════════
async def update_join(ctx, game):
    if not game.join_message_id: return
    try:
        txt = "🎮 *Katılanlar:*\n" + "\n".join(f"{i}. {p.username}" for i, p in enumerate(game.players.values(), 1))
        txt += f"\n📊 {len(game.players)}/5"
        await ctx.bot.edit_message_text(chat_id=game.group_id, message_id=game.join_message_id, text=txt, reply_markup=join_btn(), parse_mode="Markdown")
    except: pass

# ═══════════════════════════════════════════════════════════════
# CALLBACK
# ═══════════════════════════════════════════════════════════════
async def vampir_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    u = q.from_user

    # JOIN
    if d == "vampir_join":
        gid = q.message.chat.id
        if gid not in games: return await q.answer("❌ Oyun yok!", show_alert=True)
        game = games[gid]
        if not game.is_active() or game.phase != GamePhase.LOBBY: return await q.answer("❌ Aktif değil!", show_alert=True)
        if u.id in game.players: return await q.answer("❌ Zaten oyundasın!", show_alert=True)

        try:
            await ctx.bot.send_message(u.id, "✅ Katıldın!")
        except:
            return await q.answer("❌ Önce bota /start yaz!", show_alert=True)

        game.add_player(u.id, u.first_name or u.username or "?")
        await q.answer("✅ Katıldın!")
        await update_join(ctx, game)

        if len(game.players) == 5:
            if game._join_timer_task and not game._join_timer_task.done(): game._join_timer_task.cancel()
            game.join_time_left = 60
            game._join_timer_task = asyncio.create_task(join_countdown(ctx, game, _app))
        return

    # PM JOIN
    if d.startswith("vampir_pm_"):
        parts = d.split("_")
        try:
            gid = int(parts[2])
        except: return
        if gid not in games: return
        game = games[gid]
        game.add_player(u.id, u.first_name or "?")
        await q.answer("✅ Katıldın!")
        await update_join(ctx, game)
        return

    # TARGET
    if d.startswith("vampir_t_"):
        parts = d.split("_")
        try:
            gid = int(parts[2])
            tid = int(parts[3])
            phase = parts[4]
        except: return await q.answer("❌ Hata!", show_alert=True)

        if gid not in games: return await q.answer("❌ Oyun yok!", show_alert=True)
        game = games[gid]
        uid = u.id

        if not game.is_active(): return await q.answer("❌ Oyun yok!", show_alert=True)
        if uid not in game.players: return await q.answer("❌ Oyunda değilsin!", show_alert=True)
        if not game.players[uid].alive: return await q.answer("💀 Ölüsün!", show_alert=True)
        if tid not in game.players or not game.players[tid].alive: return await q.answer("❌ Geçersiz hedef!", show_alert=True)

        now = "night" if game.phase == GamePhase.NIGHT else ("day" if game.phase == GamePhase.DAY else "other")
        if phase != now: return await q.answer("⏰ Süre doldu!", show_alert=True)

        if game.phase == GamePhase.NIGHT:
            from games.vampir.engine import handle_night_act
            await handle_night_act(q, uid, tid, ctx, game, _app)
        else:
            from games.vampir.engine import handle_day_vote
            await handle_day_vote(q, uid, tid, ctx, game)

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

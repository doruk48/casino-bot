# modules/music/commands.py - GELİŞMİŞ MÜZİK KOMUTLARI
import asyncio
import os
import logging
from typing import Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes
from modules.music.player import MusicPlayer
from modules.music.downloads import download_audio

logger = logging.getLogger(__name__)

player = None
queues: Dict[int, List[dict]] = {}  # {chat_id: [{title, url, requested_by}]}

def get_player():
    return player

async def init_player(app):
    global player
    from pyrogram import Client
    
    API_ID = int(os.getenv("API_ID", "0"))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    
    if not API_ID or not API_HASH:
        logger.warning("⚠️ API_ID ayarlanmamış")
        return
    
    pyro_app = Client("music", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)
    await pyro_app.start()
    player = MusicPlayer(pyro_app)
    await player.start()
    logger.info("🎵 Müzik modülü hazır!")


def music_controls(chat_id: int) -> InlineKeyboardMarkup:
    """Müzik kontrol butonlarını oluştur"""
    queue_len = len(queues.get(chat_id, []))
    vol = player.volumes.get(chat_id, 80) if player else 80
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏸️ Duraklat", callback_data=f"music_pause_{chat_id}"),
            InlineKeyboardButton("⏭️ Atla", callback_data=f"music_skip_{chat_id}"),
            InlineKeyboardButton("⏹️ Durdur", callback_data=f"music_stop_{chat_id}"),
        ],
        [
            InlineKeyboardButton(f"📋 Sıra ({queue_len})", callback_data=f"music_queue_{chat_id}"),
            InlineKeyboardButton(f"🔊 Ses {vol}", callback_data=f"music_vol_{chat_id}"),
        ]
    ])


# ═══════════════════════════════ KOMUTLAR ═══════════════════════════════

async def cmd_play(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not player:
        return await update.message.reply_text("❌ Müzik modülü aktif değil!")
    
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    if not ctx.args:
        return await update.message.reply_text(
            "🎵 *Müzik Kullanımı:*\n\n"
            "/play <şarkı adı> - Müzik başlat\n"
            "/play <YouTube linki> - Linkten çal\n\n"
            "📋 Komutlar: /skip /queue /volume /stop",
            parse_mode="Markdown"
        )
    
    query = " ".join(ctx.args)
    status = await update.message.reply_text(f"🔍 *Aranıyor:* {query}...", parse_mode="Markdown")
    
    try:
        audio = await download_audio(query)
        
        if player.is_playing(chat_id):
            # Sıraya ekle
            if chat_id not in queues:
                queues[chat_id] = []
            queues[chat_id].append({
                'title': audio['title'],
                'file': audio['file'],
                'duration': audio['duration'],
                'requested_by': user.full_name,
                'temp_dir': audio['temp_dir']
            })
            pos = len(queues[chat_id])
            await status.edit_text(
                f"📋 *Sıraya eklendi (#{pos}):*\n"
                f"🎧 {audio['title']}\n"
                f"👤 İsteyen: {user.full_name}",
                parse_mode="Markdown"
            )
        else:
            # Hemen çal
            success = await player.play(chat_id, audio['file'], audio['title'])
            if not success:
                return await status.edit_text("❌ Başlatılamadı. Sesli sohbet aktif mi?")
            
            player.current_info[chat_id] = {
                'title': audio['title'],
                'file': audio['file'],
                'duration': audio['duration'],
                'requested_by': user.full_name,
                'temp_dir': audio['temp_dir'],
                'started': asyncio.get_event_loop().time()
            }
            
            await status.edit_text(
                f"🎵 *ŞİMDİ ÇALIYOR*\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"🎧 {audio['title']}\n"
                f"⏱️ {audio['duration']//60}:{audio['duration']%60:02d}\n"
                f"👤 İsteyen: {user.full_name}",
                reply_markup=music_controls(chat_id),
                parse_mode="Markdown"
            )
            
            # Şarkı bitince sıradakini çal
            asyncio.create_task(auto_play_next(ctx, chat_id))
            
    except Exception as e:
        await status.edit_text(f"❌ Hata: {str(e)[:100]}")


async def auto_play_next(ctx, chat_id):
    """Şarkı bitince sıradakini otomatik çal"""
    if chat_id not in player.current_info:
        return
    
    info = player.current_info[chat_id]
    await asyncio.sleep(info['duration'] + 2)
    
    # Geçici dosyaları sil
    try:
        temp_dir = info.get('temp_dir')
        if temp_dir and os.path.exists(temp_dir):
            for f in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, f))
            os.rmdir(temp_dir)
    except:
        pass
    
    if player.is_playing(chat_id):
        await player.stop_chat(chat_id)
    
    # Sıradakini çal
    if chat_id in queues and queues[chat_id]:
        next_song = queues[chat_id].pop(0)
        await player.play(chat_id, next_song['file'], next_song['title'])
        player.current_info[chat_id] = next_song
        
        await ctx.bot.send_message(
            chat_id,
            f"🎵 *ŞİMDİ ÇALIYOR*\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🎧 {next_song['title']}\n"
            f"👤 İsteyen: {next_song['requested_by']}",
            reply_markup=music_controls(chat_id),
            parse_mode="Markdown"
        )
        
        asyncio.create_task(auto_play_next(ctx, chat_id))
    else:
        await ctx.bot.send_message(chat_id, "✅ *Sıra bitti!* Yeni şarkı için /play", parse_mode="Markdown")
        if chat_id in player.current_info:
            del player.current_info[chat_id]


async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not player: return await update.message.reply_text("❌ Müzik modülü aktif değil!")
    
    chat_id = update.effective_chat.id
    if not player.is_playing(chat_id):
        return await update.message.reply_text("❌ Müzik çalmıyor!")
    
    info = player.current_info.get(chat_id, {})
    user = update.effective_user
    
    await player.stop_chat(chat_id)
    if chat_id in queues:
        queues[chat_id].clear()
    if chat_id in player.current_info:
        del player.current_info[chat_id]
    
    await update.message.reply_text(
        f"⏹️ *MÜZİK DURDURULDU*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🎧 Son çalan: {info.get('title', 'Bilinmeyen')}\n"
        f"👤 {user.full_name} tarafından durduruldu",
        parse_mode="Markdown"
    )


async def cmd_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not player: return await update.message.reply_text("❌ Müzik modülü aktif değil!")
    
    chat_id = update.effective_chat.id
    if not player.is_playing(chat_id):
        return await update.message.reply_text("❌ Müzik çalmıyor!")
    
    info = player.current_info.get(chat_id, {})
    old_title = info.get('title', 'Bilinmeyen')
    
    await player.stop_chat(chat_id)
    
    if chat_id in queues and queues[chat_id]:
        next_song = queues[chat_id].pop(0)
        await player.play(chat_id, next_song['file'], next_song['title'])
        player.current_info[chat_id] = next_song
        
        await update.message.reply_text(
            f"⏭️ *Atlandı:* {old_title}\n"
            f"🎵 *Şimdi:* {next_song['title']}\n"
            f"👤 İsteyen: {next_song['requested_by']}",
            reply_markup=music_controls(chat_id),
            parse_mode="Markdown"
        )
        asyncio.create_task(auto_play_next(ctx, chat_id))
    else:
        await update.message.reply_text(
            f"⏭️ *Atlandı:* {old_title}\n"
            f"✅ Sıra boş! /play ile yeni şarkı ekleyin",
            parse_mode="Markdown"
        )


async def cmd_queue(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not player: return await update.message.reply_text("❌ Müzik modülü aktif değil!")
    
    chat_id = update.effective_chat.id
    q = queues.get(chat_id, [])
    current = player.current_info.get(chat_id, {})
    
    text = "📋 *ŞARKI SIRASI*\n━━━━━━━━━━━━━━━━━\n\n"
    
    if current:
        text += f"🎧 *Çalıyor:* {current.get('title', '?')}\n"
        text += f"👤 {current.get('requested_by', '?')}\n"
        text += "────────────────────\n"
    
    if not q:
        text += "Sıra boş. /play ile ekleyin."
    else:
        for i, song in enumerate(q, 1):
            text += f"{i}. 🎧 {song['title']}\n"
            text += f"   👤 {song['requested_by']}\n"
            if i < len(q):
                text += "────────────────────\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_volume(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not player: return await update.message.reply_text("❌ Müzik modülü aktif değil!")
    
    chat_id = update.effective_chat.id
    
    if not ctx.args:
        current = player.volumes.get(chat_id, 80)
        await update.message.reply_text(f"🔊 Ses seviyesi: {current}/100\n/volume <10-100>")
        return
    
    try:
        vol = int(ctx.args[0])
        if vol < 10 or vol > 100:
            return await update.message.reply_text("❌ 10-100 arası girin!")
        
        player.volumes[chat_id] = vol
        bars = "█" * (vol // 10) + "░" * (10 - vol // 10)
        await update.message.reply_text(f"🔊 Ses: {bars} {vol}/100")
    except ValueError:
        await update.message.reply_text("❌ Geçerli sayı girin!")


async def cmd_current(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not player: return await update.message.reply_text("❌ Müzik modülü aktif değil!")
    
    chat_id = update.effective_chat.id
    info = player.current_info.get(chat_id)
    
    if not info:
        return await update.message.reply_text("❌ Müzik çalmıyor!")
    
    elapsed = asyncio.get_event_loop().time() - info['started']
    await update.message.reply_text(
        f"🎵 *Şu an çalıyor:* {info['title']}\n"
        f"⏱️ {int(elapsed//60)}:{int(elapsed%60):02d} / {info['duration']//60}:{info['duration']%60:02d}\n"
        f"👤 İsteyen: {info['requested_by']}",
        reply_markup=music_controls(chat_id),
        parse_mode="Markdown"
    )


# ═══════════════════════════════ CALLBACK ═══════════════════════════════

async def music_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    chat_id = q.message.chat.id
    
    if data.startswith("music_pause_"):
        await q.message.reply_text("⏸️ Duraklatıldı (yakında)")
    
    elif data.startswith("music_skip_"):
        await cmd_skip(update, ctx)
    
    elif data.startswith("music_stop_"):
        await cmd_stop(update, ctx)
    
    elif data.startswith("music_queue_"):
        await cmd_queue(update, ctx)
    
    elif data.startswith("music_vol_"):
        await q.message.reply_text("🔊 Ses ayarı için /volume <10-100>")


# ═══════════════════════════════ REGISTER ═══════════════════════════════

def register_handlers(app):
    app.add_handler(CommandHandler("play", cmd_play))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("skip", cmd_skip))
    app.add_handler(CommandHandler("queue", cmd_queue))
    app.add_handler(CommandHandler("volume", cmd_volume))
    app.add_handler(CommandHandler("current", cmd_current))
    app.add_handler(CallbackQueryHandler(music_callback, pattern=r"^music_"))
    logger.info("🎵 Müzik komutları kaydedildi!")

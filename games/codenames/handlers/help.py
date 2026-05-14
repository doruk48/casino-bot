"""
Yardım komutu: /chelp
"""
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode


async def chelp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Codenames komut listesini gösterir."""
    text = (
        "🕵️ <b>CODENAMES KOMUTLARI</b>\n\n"
        "<b>🎭 Lobi:</b>\n"
        "/cstart — Yeni oyun başlat\n"
        "/cjoin — Oyuna katıl\n"
        "/ciptal — Lobiyi iptal et (sadece sahibi)\n\n"
        "<b>👥 Takım Kurulum:</b>\n"
        "/ckaptan mavi|kirmizi — Kaptan ol ve takım seç\n"
        "/csec — Reply ile oyuncu seç (sadece kaptan)\n"
        "/csozcu — Takım sözcüsü ol\n"
        "/cistifa — Sözcülükten ayrıl\n\n"
        "<b>🎯 Oyun İçi:</b>\n"
        "/cipucu kelime sayı — <i>Sadece DM'den</i> ipucu ver (kaptan)\n"
        "/ctahmin kelime — Tahmin yap (sadece sözcü)\n"
        "/cpas — Pas ver (sadece sözcü)\n"
        "/cdurum — Oyun durumunu göster\n"
        "/cson — Oyunu erken bitir (kaptan/sahip)\n\n"
        "<b>⏱️ Süreler:</b>\n"
        "• İpucu verme: 2 dakika\n"
        "• Tahmin yapma: 1 dakika\n"
        "• Max tahmin hakkı: 3\n\n"
        "<b>📋 Kurallar:</b>\n"
        "• 9 mavi, 8 kırmızı, 7 boş, 1 suikastçı\n"
        "• Suikastçıyı açan takım kaybeder\n"
        "• Tüm kelimelerini açan takım kazanır\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

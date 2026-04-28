# features/shop.py - Bota Destek Ol (Bağış Sistemi)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ContextTypes

from utils.format import format_amount

# Destek paketleri (sadece Stars, karşılıksız)
DONATE_OPTIONS = [
    (10, "🌟", "Minik Destek", "Küçük bir teşekkür"),
    (25, "⭐", "Güzel Destek", "Çay ısmarlamak gibi"),
    (50, "💫", "Süper Destek", "Kahve ısmarlamak gibi"),
    (100, "🔥", "Harika Destek", "Yemek ısmarlamak gibi"),
    (250, "💎", "Efsane Destek", "Botun gelişimine büyük katkı"),
    (500, "👑", "Kral Destek", "Sen olmasan olmazdı!"),
    (1000, "🏆", "Efsanevi Destek", "Botun ikinci sahibi sensin!"),
]

async def cmd_donate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Bota destek olma menüsü"""
    keyboard = []
    for stars, emoji, title, desc in DONATE_OPTIONS:
        keyboard.append([
            InlineKeyboardButton(
                f"{emoji} {stars} ⭐ | {title}",
                callback_data=f"donate_{stars}"
            )
        ])
    
    await update.message.reply_text(
        f"💝 <b>BOTA DESTEK OL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎰 Casinobot'u seviyor ve destek olmak mı istiyorsun?\n\n"
        f"✨ Bu bir <b>bağıştır</b>, hiçbir oyun içi avantaj sağlamaz.\n"
        f"💰 Token veya bonus <b>verilmez</b>.\n"
        f"❤️ Sadece botun gelişimine katkıda bulunursun.\n\n"
        f"👇 Destek miktarını seç:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def donate_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Destek miktarı seçildiğinde ödeme başlat"""
    query = update.callback_query
    await query.answer()
    
    stars = int(query.data.split("_")[1])
    
    # Seçilen paketi bul
    selected = None
    for s, emoji, title, desc in DONATE_OPTIONS:
        if s == stars:
            selected = (emoji, title, desc)
            break
    
    if not selected:
        return
    
    emoji, title, desc = selected
    
    await ctx.bot.send_invoice(
        chat_id=query.from_user.id,
        title=f"💝 {title}",
        description=f"{emoji} Bota {stars} ⭐ destek ol\n"
                    f"💬 {desc}\n\n"
                    f"⚠️ Bu bir bağıştır, karşılığında hiçbir şey almazsınız.",
        payload=f"donate_{stars}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{stars} ⭐ Destek", amount=stars)],
        start_parameter="bot_donate",
        need_name=False,
        need_phone_number=False,
        need_email=False
    )

async def pre_checkout_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Ödeme onayı"""
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Başarılı bağış - TEŞEKKÜR MESAJI (Token YOK!)"""
    user = update.effective_user
    payload = update.message.successful_payment.invoice_payload
    stars = int(payload.split("_")[1])
    
    # Seçilen paketi bul
    emoji = "💝"
    title = "Destek"
    for s, e, t, d in DONATE_OPTIONS:
        if s == stars:
            emoji, title = e, t
            break
    
    await update.message.reply_text(
        f"{emoji} <b>DESTEĞİN İÇİN TEŞEKKÜRLER!</b> {emoji}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"❤️ <b>{user.full_name}</b>, sen harikasın!\n\n"
        f"🌟 {stars} ⭐ destek oldun.\n"
        f"💬 <b>{title}</b>\n\n"
        f"🎰 Casinobot senin sayende gelişmeye devam edecek!\n"
        f"🍀 Bol şans ve keyifli oyunlar dileriz!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💝 <b>DESTEKÇİ</b> rozeti profiline eklendi!",
        parse_mode="HTML"
    )

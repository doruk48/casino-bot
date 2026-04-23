# features/shop.py - VIP Kasa (Stars ile Satın Alma)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ContextTypes

from config import STARS_CONFIG
from core.economy import add_balance, get_balance
from utils.format import format_amount

async def cmd_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for stars, config in STARS_CONFIG.items():
        keyboard.append([
            InlineKeyboardButton(
                f"🌟 {stars} Stars → {config['label']} {format_amount(config['coin'])}",
                callback_data=f"buy_{stars}"
            )
        ])
    
    await update.message.reply_text(
        "🌟 <b>VIP KASA - Telegram Stars ile Satın Al</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Aşağıdaki paketlerden birini seçin:\n\n"
        "💡 Telegram Stars satın almak için: @PremiumBot\n"
        "⚠️ Bu sanal oyun parasıdır, gerçek para değeri yoktur.\n"
        "✅ Satın alınca coinler anında hesabınıza eklenir!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def buy_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    stars = int(query.data.split("_")[1])
    config = STARS_CONFIG[stars]
    coin_amount = config["coin"]
    user = query.from_user
    
    await ctx.bot.send_invoice(
        chat_id=user.id,
        title=config['label'],
        description=f"{format_amount(coin_amount)} oyun parası",
        payload=f"stars_{stars}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{stars} Yıldız", amount=stars)],
        start_parameter="vip_kasa",
        need_name=False,
        need_phone_number=False,
        need_email=False
    )

async def pre_checkout_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    payload = update.message.successful_payment.invoice_payload
    stars = int(payload.split("_")[1])
    
    coin_amount = STARS_CONFIG[stars]["coin"]
    label = STARS_CONFIG[stars]["label"]
    
    await add_balance(user.id, coin_amount, "stars_purchase", f"{stars} Stars ile {label}")
    new_balance = await get_balance(user.id)
    
    await update.message.reply_text(
        f"✅ <b>SATIN ALMA BAŞARILI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌟 {stars} Stars → {label}\n"
        f"💰 Hesabınıza eklenen: {format_amount(coin_amount)}\n"
        f"💳 Yeni bakiyeniz: {format_amount(new_balance)}\n\n"
        f"🎉 İyi eğlenceler!",
        parse_mode="HTML"
    )

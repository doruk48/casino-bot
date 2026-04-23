# features/help.py - Yardım ve Başlangıç Komutları
from telegram import Update
from telegram.ext import ContextTypes

from config import STARTING_BALANCE
from core.users import get_or_create_user
from core.economy import get_balance
from utils.format import format_amount
from utils.helpers import get_level

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = await get_or_create_user(user.id, user.username, user.full_name)
    lvl, emoji = get_level(u["balance"])
    
    await update.message.reply_text(
        f"🎰 <b>CasiniBot'a Hoş Geldiniz!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{user.full_name}</b> [{lvl}] {emoji}\n"
        f"💳 Başlangıç bakiyeniz: {format_amount(u['balance'])}\n\n"
        f"🍀 Bol şans!\n"
        f"📌 Komutlar için /help\n"
        f"🎮 Oyunlar için /menu",
        parse_mode="HTML"
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🎰 <b>CASİNİBOT KOMUTLAR</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👤 <b>HESAP</b>\n"
        "/start — Kayıt / Hoş geldin\n"
        "/balance — Bakiyeni göster\n"
        "/daily — Günlük bonus\n"
        "/moneys — Para gönder\n"
        "/leaderboard — Liderlik tablosu\n\n"
        "🎡 <b>RULET</b>\n"
        "/rulet — Rulet başlat\n"
        "/red /black /green /number\n\n"
        "🃏 <b>BLACKJACK</b>\n"
        "/blackjack — Başlat\n"
        "/bj — Bahis yap\n\n"
        "🎲 <b>ZAR (PvP)</b>\n"
        "/dicebet — Başlat\n"
        "/dice — Katıl\n\n"
        "🎡 <b>ÇARKIFELEK</b>\n"
        "/wheelbet — Başlat\n"
        "/wheel — Bahis\n\n"
        "🎟 <b>KAZI KAZAN</b>\n"
        "/kazisolo — Tek kişilik\n"
        "/kazibet — Turnuva\n\n"
        "💰 <b>SATIN AL</b>\n"
        "/buy — Stars ile satın al\n\n"
        "🎰 <b>JACKPOT</b>\n"
        "/jackpot — Havuzları gör"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")

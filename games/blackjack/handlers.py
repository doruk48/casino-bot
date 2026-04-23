# games/blackjack/handlers.py - Blackjack Komutları
import asyncio
from telegram import Update
from telegram.ext import ContextTypes

from config import BET_WINDOW
from core.state import can_open_game, create_game, is_rate_limited, _state_lock, _active_games
from core.users import get_or_create_user
from core.economy import get_balance, remove_balance
from utils.format import format_amount, parse_amount
from games.blackjack.engine import _bj, _bj_bet_timer

async def cmd_blackjack(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if is_rate_limited(user.id):
        return
    
    ok, err = await can_open_game(chat_id, "blackjack")
    if not ok:
        await update.message.reply_text(f"❌ {err}")
        return
    
    game = await create_game(chat_id, "blackjack", 0)
    gid = game["game_id"]
    
    msg = await update.message.reply_text(
        f"🃏 <b>BLACKJACK BAŞLADI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 GAME ID: {gid}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>{BET_WINDOW} saniye</b> içinde bahis yapın!\n\n"
        f"📌 /bj &lt;miktar&gt;\n"
        f"• 21'i geç → kaybedersin\n"
        f"• Kurpiyer 17'de durur\n"
        f"• Kazanırsan 2x alırsın",
        parse_mode="HTML"
    )
    
    async with _state_lock:
        if chat_id in _active_games and gid in _active_games[chat_id]:
            _active_games[chat_id][gid]["message_id"] = msg.message_id
    
    _bj[chat_id] = {
        "game_id": gid,
        "state": "BETTING",
        "players": {},
        "order": [],
        "dealer": [],
        "deck": [],
        "current": 0
    }
    asyncio.create_task(_bj_bet_timer(ctx, chat_id, gid))

async def cmd_bj(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    bj = _bj.get(chat_id)
    if not bj or bj["state"] != "BETTING":
        await update.message.reply_text("❌ Açık blackjack yok veya bahis süresi doldu.")
        return
    
    if not ctx.args:
        await update.message.reply_text("❌ Kullanım: /bj <miktar>")
        return
    
    await get_or_create_user(user.id, user.username, user.full_name)
    bal = await get_balance(user.id)
    amount, err = parse_amount(ctx.args[0], bal)
    if err:
        await update.message.reply_text(f"❌ {err}")
        return
    
    ok = await remove_balance(user.id, amount, "bet", f"BJ game:{bj['game_id']}")
    if not ok:
        await update.message.reply_text("❌ Yetersiz bakiye.")
        return
    
    if user.id in bj["players"]:
        bj["players"][user.id]["bet"] += amount
        await update.message.reply_text(
            f"🕹 <b>{user.full_name}</b> 🃏 +{format_amount(amount)} "
            f"(Toplam: {format_amount(bj['players'][user.id]['bet'])})",
            parse_mode="HTML"
        )
    else:
        bj["players"][user.id] = {
            "bet": amount,
            "hand": [],
            "state": "WAITING",
            "name": user.full_name
        }
        bj["order"].append(user.id)
        await update.message.reply_text(
            f"🕹 <b>{user.full_name}</b> 🃏 {format_amount(amount)} bahis yaptı",
            parse_mode="HTML"
        )

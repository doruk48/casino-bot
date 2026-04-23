# games/wheel/engine.py - Çarkıfelek Oyun Mantığı
import asyncio
import random
import secrets
from telegram import Update
from telegram.ext import ContextTypes

from config import BET_WINDOW, WHEEL_SEGMENTS
from core.state import get_active_game, finish_game, cleanup, add_participant, get_participants
from core.economy import add_balance
from core.stats import update_stats, update_win_rate
from utils.format import format_amount, logger

async def _wheel_timer(ctx, chat_id, game_id):
    await asyncio.sleep(BET_WINDOW)
    
    game = await get_active_game(chat_id, "wheel")
    if not game or game["game_id"] != game_id:
        return
    
    game["state"] = "CALCULATING"
    
    shuffled_segments = random.sample(WHEEL_SEGMENTS, len(WHEEL_SEGMENTS))
    label, mult = secrets.choice(shuffled_segments)
    logger.info(f"🎡 Çark sonucu: label='{label}', mult={mult}")
    
    parts = await get_participants(chat_id, game_id)
    
    lines = [
        f"🆔 GAME ID: {game_id}\n",
        f"🎡 <b>ÇARK DÖNDÜ!</b>",
        f"━━━━━━━━━━━━━━━━━━━━━",
        f"🎯 Sonuç: <b>{label}</b>",
        ""
    ]
    
    total_payout = 0
    
    if not parts:
        lines.append("😴 Kimse bahis yapmadı.")
    elif mult == 0:
        lines.append("💀 <b>PASS!</b> Herkes kaybetti.")
        for uid, data in parts.items():
            for bet_wrapper in data.get("bets", []):
                await update_stats(uid, 0)
                await update_win_rate(uid, "wheel", False)
                lines.append(f"  ❌ {bet_wrapper['bet_data']['name']}: -{format_amount(bet_wrapper['bet'])}")
    elif mult == 1:
        lines.append("🔄 <b>İADE!</b> Bahisler geri ödendi.")
        for uid, data in parts.items():
            for bet_wrapper in data.get("bets", []):
                await add_balance(uid, bet_wrapper["bet"], "refund", f"Çark iade game:{game_id}")
                await update_stats(uid, 0)
                await update_win_rate(uid, "wheel", True)
                lines.append(f"  🔄 {bet_wrapper['bet_data']['name']}: +0 (iade)")
    elif mult == -1:
        lines.append("🎰 <b>JACKPOT!</b> 🎉")
        lines.append("💰 Havuz dağıtılıyor...")
        for uid, data in parts.items():
            for bet_wrapper in data.get("bets", []):
                lines.append(f"  ✅ {bet_wrapper['bet_data']['name']}: JACKPOT kazandı!")
    elif mult > 1:
        lines.append(f"🏆 <b>{label} ({mult}x)</b>")
        for uid, data in parts.items():
            for bet_wrapper in data.get("bets", []):
                payout = bet_wrapper["bet"] * mult
                await add_balance(uid, payout, "win", f"Çark game:{game_id}")
                await update_stats(uid, payout)
                await update_win_rate(uid, "wheel", True)
                total_payout += payout
                net = payout - bet_wrapper["bet"]
                lines.append(f"  ✅ {bet_wrapper['bet_data']['name']}: +{format_amount(net)}")
    
    if mult > 1:
        lines.append("")
        lines.append(f"💰 Toplam dağıtılan: {format_amount(total_payout)}")
    
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append("✨ Yeni oyun için /wheelbet")
    
    await ctx.bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")
    await finish_game(chat_id, game_id, label, ctx)
    await cleanup(chat_id)

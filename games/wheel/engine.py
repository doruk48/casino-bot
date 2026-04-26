# games/wheel/engine.py - Çarkıfelek Oyun Mantığı
import asyncio
import random
import secrets
from telegram import Update
from telegram.ext import ContextTypes

from config import BET_WINDOW, WHEEL_SEGMENTS, JACKPOT_MINIMUM
from core.state import get_active_game, finish_game, cleanup, add_participant, get_participants
from core.economy import add_balance
from core.stats import update_stats, update_win_rate
from core.users import get_user
from utils.format import format_amount, logger
from utils.images import create_jackpot_image
from features.jackpot import _get_jackpot_amount, _add_to_jackpot, _reset_jackpot

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
    
    elif mult == 0:  # PASS - HAVUZA EKLE
        lines.append("💀 <b>PASS!</b> Herkes kaybetti. Bahisler jackpot'a eklendi.")
        for uid, data in parts.items():
            for bet_wrapper in data.get("bets", []):
                bet = bet_wrapper["bet"]
                await _add_to_jackpot("wheel", bet)
                await update_stats(uid, 0)
                await update_win_rate(uid, "wheel", False)
                lines.append(f"  ❌ {bet_wrapper['bet_data']['name']}: -{format_amount(bet)}")
    
    elif mult == 1:  # İADE - %10 HAVUZA
        lines.append("🔄 <b>İADE!</b> Bahisler geri ödendi, %10'u jackpot'a eklendi.")
        for uid, data in parts.items():
            for bet_wrapper in data.get("bets", []):
                bet = bet_wrapper["bet"]
                commission = int(bet * 0.1)
                if commission > 0:
                    await _add_to_jackpot("wheel", commission)
                await add_balance(uid, bet, "refund", f"Çark iade game:{game_id}")
                await update_stats(uid, 0)
                await update_win_rate(uid, "wheel", True)
                lines.append(f"  🔄 {bet_wrapper['bet_data']['name']}: +0 (iade)")
    
    elif mult == -1:  # JACKPOT
        jackpot_amount = await _get_jackpot_amount("wheel")
        min_bet_for_jackpot = int(jackpot_amount * 0.15)
        
        jackpot_winners = []
        refund_only = []
        
        for uid, data in parts.items():
            for bet_wrapper in data.get("bets", []):
                bet = bet_wrapper["bet"]
                if bet >= min_bet_for_jackpot:
                    jackpot_winners.append((uid, bet, bet_wrapper['bet_data']['name']))
                else:
                    refund_only.append((uid, bet, bet_wrapper['bet_data']['name']))
        
        if jackpot_winners:
            jackpot_per_winner = jackpot_amount // len(jackpot_winners)
            
            for uid, bet, name in jackpot_winners:
                total_win = bet + jackpot_per_winner
                await add_balance(uid, total_win, "win", f"Çark JACKPOT! game:{game_id}")
                await update_stats(uid, total_win)
                await update_win_rate(uid, "wheel", True)
                
                # Görsel gönder
                user = await get_user(uid)
                player_name = user.get("display_name", str(uid)) if user else str(uid)
                jackpot_img = create_jackpot_image("wheel", player_name)
                caption = (
                    f"🎰 <b>JACKPOT KAZANDIN!</b> 🎰\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🆔 GAME ID: {game_id}\n"
                    f"🎡 Oyun: Çarkıfelek\n"
                    f"💰 Havuz: {format_amount(jackpot_amount)}\n"
                    f"🎯 Min. bahis: {format_amount(min_bet_for_jackpot)} (%15)\n"
                    f"✅ Senin bahsin: {format_amount(bet)} (yeterli)\n"
                    f"💰 Havuz Payın: {format_amount(jackpot_per_winner)}\n"
                    f"🎁 Bahis İaden: {format_amount(bet)}\n"
                    f"💳 Toplam: {format_amount(total_win)}\n\n"
                    f"🎉 <b>TEBRİKLER!</b> 🎉"
                )
                try:
                    if jackpot_img:
                        await ctx.bot.send_photo(chat_id, photo=jackpot_img, caption=caption, parse_mode="HTML")
                    else:
                        await ctx.bot.send_message(chat_id, caption, parse_mode="HTML")
                except:
                    pass
            
            await _reset_jackpot("wheel")
        
        # Bahis iadesi
        for uid, bet, name in refund_only:
            await add_balance(uid, bet, "refund", f"Çark JACKPOT iade game:{game_id}")
        
        # Genel mesaj
        lines.append("🎰 <b>JACKPOT!</b> 🎉")
        lines.append(f"💰 Havuz: {format_amount(jackpot_amount)}")
        lines.append(f"🎯 Min. bahis: {format_amount(min_bet_for_jackpot)} (%15)")
        lines.append("")
        
        if jackpot_winners:
            lines.append("🏆 <b>JACKPOT KAZANANLAR</b>")
            for uid, bet, name in jackpot_winners:
                lines.append(f"  ✅ {name}: {format_amount(bet)} → +{format_amount(jackpot_amount // len(jackpot_winners))}")
        
        if refund_only:
            lines.append("")
            lines.append("🔄 <b>SADECE BAHİS İADESİ</b>")
            lines.append("(Bahisleri havuzun %15'inden küçük)")
            for uid, bet, name in refund_only:
                lines.append(f"  🔄 {name}: {format_amount(bet)} iade")
    
    elif mult > 1:  # Kazanç
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

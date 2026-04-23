# games/scratch/engine.py - Kazı Kazan Oyun Mantığı (Solo + Turnuva)
import asyncio
import secrets
from collections import Counter
from telegram import Update
from telegram.ext import ContextTypes

from config import BET_WINDOW, SCRATCH_POOL
from core.state import get_active_game, finish_game, cleanup, _state_lock, _active_games
from core.economy import add_balance
from core.stats import update_stats, update_win_rate
from utils.format import format_amount, logger
from utils.images import create_scratch_result_image

# ═══════════════════════════════════════════════════════════════
#  TURNUVA ZAMANLAYICILARI
# ═══════════════════════════════════════════════════════════════
async def _scratch_countdown(ctx, chat_id, game_id, message_id):
    for remaining in range(BET_WINDOW, 0, -5):
        await asyncio.sleep(5)
        game = await get_active_game(chat_id, "scratch_tournament")
        if not game or game["game_id"] != game_id or game["state"] != "OPEN":
            return
        
        async with _state_lock:
            game_data = _active_games.get(chat_id, {}).get(game_id)
            if not game_data:
                return
            players_count = len(game_data.get("players_data", {}))
            pool = game_data.get("pool", 0)
        
        try:
            await ctx.bot.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=f"🎟 <b>KAZI KAZAN TURNUVASI</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🆔 GAME ID: {game_id}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"⏱ Kalan: {remaining} sn\n"
                        f"👥 Katılımcı: {players_count}\n"
                        f"💰 Havuz: {format_amount(pool)}",
                parse_mode="HTML"
            )
        except:
            pass

async def _scratch_tournament_timer(ctx, chat_id, game_id):
    await asyncio.sleep(BET_WINDOW)
    
    game = await get_active_game(chat_id, "scratch_tournament")
    if not game or game["game_id"] != game_id:
        return
    
    async with _state_lock:
        game_data = _active_games.get(chat_id, {}).get(game_id)
        if not game_data:
            return
        players = game_data.get("players_data", {}).copy()
    
    if len(players) < 2:
        for uid, d in players.items():
            await add_balance(uid, d["bet"], "refund", "Kazi Turnuva İptal")
        await ctx.bot.send_message(
            chat_id,
            f"❌ <b>KAZI KAZAN TURNUVASI İPTAL!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"En az 2 oyuncu gerekli. Bahisler iade edildi.",
            parse_mode="HTML"
        )
        await finish_game(chat_id, game_id, "iptal", ctx)
        await cleanup(chat_id)
        return
    
    board = [secrets.choice(SCRATCH_POOL) for _ in range(6)]
    counts = Counter(board)
    winner_mult = 0
    for mult, count in counts.most_common():
        if count >= 3 and mult > 0:
            winner_mult = mult
            break
    
    try:
        result_img = create_scratch_result_image(board, winner_mult)
        lines = [
            f"🆔 GAME ID: {game_id}\n",
            f"🎟 <b>KAZI KAZAN SONUCU</b>",
            f"━━━━━━━━━━━━━━━━━━━━━"
        ]
        
        if winner_mult > 0:
            lines.append(f"✅ <b>{winner_mult}x</b> eşleşmesi bulundu!")
            lines.append(f"🎉 <b>HERKES KAZANDI!</b>\n")
            total_payout = 0
            for uid, d in players.items():
                payout = d["bet"] * winner_mult
                await add_balance(uid, payout, "win", f"Kazi Turnuva {winner_mult}x")
                await update_stats(uid, payout)
                net = payout - d["bet"]
                lines.append(f"✅ {d['name']}: +{format_amount(net)}")
                total_payout += payout
                await update_win_rate(uid, "scratch", True)
            lines.append(f"\n💰 Toplam dağıtılan: {format_amount(total_payout)}")
        else:
            lines.append(f"❌ Eşleşme yok!")
            lines.append(f"😢 <b>HERKES KAYBETTİ!</b>\n")
            for uid, d in players.items():
                await update_stats(uid, 0)
                lines.append(f"❌ {d['name']}: -{format_amount(d['bet'])}")
                await update_win_rate(uid, "scratch", False)
        
        lines.append("━━━━━━━━━━━━━━━━━━━━━")
        lines.append("✨ Yeni turnuva için /kazibet")
        
        await ctx.bot.send_photo(
            chat_id,
            photo=result_img,
            caption="\n".join(lines),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Kazi turnuva görsel hatası: {e}")
        msg = f"🆔 GAME ID: {game_id}\n\n🎟 <b>KAZI KAZAN SONUCU</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
        if winner_mult > 0:
            msg += f"✅ {winner_mult}x eşleşmesi! HERKES KAZANDI!\n"
            for uid, d in players.items():
                payout = d["bet"] * winner_mult
                await add_balance(uid, payout, "win", f"Kazi Turnuva {winner_mult}x")
                await update_stats(uid, payout)
                msg += f"✅ {d['name']}: +{format_amount(payout)}\n"
        else:
            msg += f"❌ Eşleşme yok! HERKES KAYBETTİ!\n"
        await ctx.bot.send_message(chat_id, msg, parse_mode="HTML")
    
    await finish_game(chat_id, game_id, "kazikazan", ctx)
    await cleanup(chat_id)

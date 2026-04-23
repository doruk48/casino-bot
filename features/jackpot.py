# features/jackpot.py - Jackpot Sistemi
import asyncio
from datetime import datetime
from bson.decimal128 import Decimal128
from decimal import Decimal

from config import JACKPOT_MINIMUM
from core.database import get_db
from core.economy import add_balance
from core.stats import update_stats, update_win_rate
from core.users import get_user
from utils.format import format_amount, logger
from utils.images import create_jackpot_image

# ═══════════════════════════════════════════════════════════════
#  JACKPOT HAVUZ İŞLEMLERİ
# ═══════════════════════════════════════════════════════════════
async def _get_jackpot_amount(game_type: str) -> int:
    try:
        db = await get_db()
        jackpot = await db.jackpot.find_one({"_id": f"{game_type}_jackpot"})
        
        if not jackpot:
            await db.jackpot.insert_one({
                "_id": f"{game_type}_jackpot",
                "amount": Decimal128(str(JACKPOT_MINIMUM)),
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            })
            return JACKPOT_MINIMUM
        
        amount = jackpot.get("amount", JACKPOT_MINIMUM)
        if isinstance(amount, Decimal128):
            return int(amount.to_decimal())
        return int(amount)
        
    except Exception as e:
        logger.error(f"Jackpot miktarı alınamadı ({game_type}): {e}")
        return JACKPOT_MINIMUM

async def _add_to_jackpot(game_type: str, amount: int) -> int:
    if amount <= 0:
        return await _get_jackpot_amount(game_type)
    
    try:
        db = await get_db()
        result = await db.jackpot.find_one_and_update(
            {"_id": f"{game_type}_jackpot"},
            {
                "$inc": {"amount": Decimal128(str(amount))},
                "$set": {"updated_at": datetime.now()}
            },
            upsert=True,
            return_document=True
        )
        
        new_amount = result.get("amount", 0)
        if isinstance(new_amount, Decimal128):
            new_amount = int(new_amount.to_decimal())
        
        logger.info(f"🎰 Jackpot'a eklendi ({game_type}): +{format_amount(amount)} → {format_amount(new_amount)}")
        return new_amount
        
    except Exception as e:
        logger.error(f"Jackpot'a eklenemedi ({game_type}, {amount}): {e}")
        return await _get_jackpot_amount(game_type)

async def _reset_jackpot(game_type: str) -> None:
    try:
        db = await get_db()
        await db.jackpot.update_one(
            {"_id": f"{game_type}_jackpot"},
            {
                "$set": {
                    "amount": Decimal128(str(JACKPOT_MINIMUM)),
                    "updated_at": datetime.now()
                }
            },
            upsert=True
        )
        logger.info(f"🎰 Jackpot sıfırlandı ({game_type}): {format_amount(JACKPOT_MINIMUM)}")
        
    except Exception as e:
        logger.error(f"Jackpot sıfırlanamadı ({game_type}): {e}")

# ═══════════════════════════════════════════════════════════════
#  ANA JACKPOT İŞLEM FONKSİYONU
# ═══════════════════════════════════════════════════════════════
async def process_jackpot_on_game_end(game_id: str, result: str, chat_id: int, ctx=None) -> None:
    try:
        db = await get_db()
        game = await db.games.find_one({"game_id": game_id})
        
        if not game:
            logger.warning(f"⚠️ Jackpot: Oyun bulunamadı {game_id}")
            return
        
        game_type = game.get("game_type")
        
        if game_type not in ["wheel", "blackjack"]:
            return
        
        participants = await db.game_participants.find({"game_id": game_id}).to_list(None)
        if not participants:
            logger.info(f"ℹ️ Jackpot: Katılımcı yok {game_id}")
            return
        
        # ═══════════════════════════════════════════════════════
        # ÇARKIFELEK JACKPOT
        # ═══════════════════════════════════════════════════════
        if game_type == "wheel":
            
            if "PASS" in result:
                for p in participants:
                    bet = p.get("bet_amount", 0)
                    if isinstance(bet, Decimal128):
                        bet = int(bet.to_decimal())
                    else:
                        bet = int(bet) if bet else 0
                    if bet > 0:
                        await _add_to_jackpot("wheel", bet)
                logger.info(f"🎰 Çarkıfelek PASS: Bahisler havuza eklendi. Game: {game_id}")
                
            elif "İADE" in result:
                for p in participants:
                    bet = p.get("bet_amount", 0)
                    if isinstance(bet, Decimal128):
                        bet = int(bet.to_decimal())
                    else:
                        bet = int(bet) if bet else 0
                    commission = int(bet * 0.1)
                    if commission > 0:
                        await _add_to_jackpot("wheel", commission)
                logger.info(f"🎰 Çarkıfelek İADE: %10 komisyon havuza eklendi. Game: {game_id}")
                
            elif "JACKPOT" in result:
                jackpot_amount = await _get_jackpot_amount("wheel")
                total_players = len(participants)
                
                if total_players > 0 and jackpot_amount > JACKPOT_MINIMUM:
                    jackpot_per_player = jackpot_amount // total_players
                    
                    for p in participants:
                        uid = p["telegram_id"]
                        bet = p.get("bet_amount", 0)
                        if isinstance(bet, Decimal128):
                            bet = int(bet.to_decimal())
                        else:
                            bet = int(bet) if bet else 0
                        
                        user = await get_user(uid)
                        player_name = user.get("display_name", str(uid)) if user else str(uid)
                        
                        total_win = bet + jackpot_per_player
                        
                        await add_balance(uid, total_win, "win", f"Çark JACKPOT! game:{game_id}")
                        await update_stats(uid, total_win)
                        await update_win_rate(uid, "wheel", True)
                        
                        jackpot_img = create_jackpot_image("wheel", player_name)
                        caption = (
                            f"🎰 <b>JACKPOT KAZANDIN!</b> 🎰\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🆔 GAME ID: {game_id}\n"
                            f"🎡 Oyun: Çarkıfelek\n"
                            f"💰 Havuz Payın: {format_amount(jackpot_per_player)}\n"
                            f"🎁 Bahis İaden: {format_amount(bet)}\n"
                            f"💳 Toplam: {format_amount(total_win)}\n\n"
                            f"🎉 <b>TEBRİKLER!</b> 🎉"
                        )
                        
                        if ctx and ctx.bot:
                            try:
                                if jackpot_img:
                                    await ctx.bot.send_photo(chat_id, photo=jackpot_img, caption=caption, parse_mode="HTML")
                                else:
                                    await ctx.bot.send_message(chat_id, caption, parse_mode="HTML")
                            except:
                                pass
                    
                    await _reset_jackpot("wheel")
                    logger.info(f"🎰 Çarkıfelek JACKPOT dağıtıldı: {format_amount(jackpot_amount)}. Game: {game_id}")
        
        # ═══════════════════════════════════════════════════════
        # BLACKJACK JACKPOT
        # ═══════════════════════════════════════════════════════
        elif game_type == "blackjack":
            logger.info(f"🃏 Blackjack oyunu bitti. Game: {game_id}")
            
    except Exception as e:
        logger.error(f"❌ process_jackpot_on_game_end kritik hata: {e}", exc_info=True)

# ═══════════════════════════════════════════════════════════════
#  /jackpot KOMUTU
# ═══════════════════════════════════════════════════════════════
async def cmd_jackpot(update, ctx):
    try:
        wheel_amount = await _get_jackpot_amount("wheel")
        blackjack_amount = await _get_jackpot_amount("blackjack")
        
        text = (
            f"🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥\n"
            f"   👑 <b>KRALLIK JACKPOT HAVUZLARI</b> 👑\n"
            f"🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥\n\n"
            f"✅ <b>🎡 ÇARKIFELEK KRALLIĞI</b> ✅\n"
            f"═══════════════════════════════════\n"
            f"🔘 <b>HAVUZ:</b> <code>{format_amount(wheel_amount)}</code> 🪙BTK 💵💵\n"
            f"🔘 <b>JACKPOT ŞANSI:</b> %5\n"
            f"🔘 PASS → HAVUZA EKLENİR\n\n"
            f"✅ <b>🃏 BLACKJACK KRALLIĞI</b> ✅\n"
            f"═══════════════════════════════════\n"
            f"🔘 <b>HAVUZ:</b> <code>{format_amount(blackjack_amount)}</code> 🪙BTK 💵💵\n"
            f"🔘 21 YAPANA → JACKPOT\n"
            f"🔘 BUST → HAVUZA EKLENİR\n\n"
            f"   👑💰 <b>TAHT SENİ BEKLİYOR!</b> 💰👑"
        )
        
        await update.message.reply_text(text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"❌ cmd_jackpot hatası: {e}")
        await update.message.reply_text("❌ Jackpot bilgileri alınırken hata oluştu.")

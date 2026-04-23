# core/stats.py - İstatistikler
from bson.decimal128 import Decimal128
from core.database import get_db
from core.economy import _get_lock

async def update_stats(uid: int, won: int):
    db = await get_db()
    async with await _get_lock(uid):
        try:
            dec_won = Decimal128(str(int(won)))
        except:
            dec_won = Decimal128("0")
        
        await db.users.update_one(
            {"telegram_id": uid},
            {"$inc": {"total_won": dec_won, "games_played": 1},
             "$set": {"updated_at": datetime.now()}}
        )

async def update_win_rate(uid: int, game_type: str, won: bool):
    try:
        db = await get_db()
        
        stats = await db.user_stats.find_one({"telegram_id": uid})
        
        if not stats:
            stats = {
                "telegram_id": uid,
                "roulette_total": 0, "roulette_wins": 0, "roulette_win_rate": 0,
                "blackjack_total": 0, "blackjack_wins": 0, "blackjack_win_rate": 0,
                "dice_total": 0, "dice_wins": 0, "dice_win_rate": 0,
                "wheel_total": 0, "wheel_wins": 0, "wheel_win_rate": 0,
                "scratch_total": 0, "scratch_wins": 0, "scratch_win_rate": 0,
                "total_win_rate": 0
            }
        
        total_field = f"{game_type}_total"
        wins_field = f"{game_type}_wins"
        
        stats[total_field] = stats.get(total_field, 0) + 1
        if won:
            stats[wins_field] = stats.get(wins_field, 0) + 1
        
        if stats[total_field] > 0:
            stats[f"{game_type}_win_rate"] = round((stats[wins_field] / stats[total_field]) * 100, 1)
        
        all_total = (stats.get("roulette_total", 0) + stats.get("blackjack_total", 0) +
                     stats.get("dice_total", 0) + stats.get("wheel_total", 0) + stats.get("scratch_total", 0))
        all_wins = (stats.get("roulette_wins", 0) + stats.get("blackjack_wins", 0) +
                    stats.get("dice_wins", 0) + stats.get("wheel_wins", 0) + stats.get("scratch_wins", 0))
        
        if all_total > 0:
            stats["total_win_rate"] = round((all_wins / all_total) * 100, 1)
        
        await db.user_stats.update_one(
            {"telegram_id": uid},
            {"$set": stats},
            upsert=True
        )
        
    except Exception as e:
        from utils.format import logger
        logger.error(f"Win rate güncellenemedi: {e}")

# datetime import
from datetime import datetime

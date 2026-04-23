# core/users.py - Kullanıcı İşlemleri
from datetime import datetime
from bson.decimal128 import Decimal128
from core.database import get_db
from core.economy import _get_lock
from config import STARTING_BALANCE

async def get_user(uid: int) -> dict | None:
    db = await get_db()
    user = await db.users.find_one({"telegram_id": uid})
    return dict(user) if user else None

async def get_or_create_user(uid: int, username, name: str) -> dict:
    db = await get_db()
    
    async with await _get_lock(uid):
        user = await db.users.find_one({"telegram_id": uid})
        
        if user is None:
            user_data = {
                "telegram_id": uid,
                "username": username,
                "display_name": name,
                "balance": Decimal128(str(STARTING_BALANCE)),
                "total_wagered": Decimal128("0"),
                "total_won": Decimal128("0"),
                "games_played": 0,
                "last_daily": None,
                "daily_streak": 0,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            await db.users.insert_one(user_data)
            
            await db.transactions.insert_one({
                "to_id": uid,
                "amount": Decimal128(str(STARTING_BALANCE)),
                "type": "bonus",
                "description": "Başlangıç",
                "created_at": datetime.now()
            })
            
            user = await db.users.find_one({"telegram_id": uid})
        else:
            if username != user.get("username") or name != user.get("display_name"):
                await db.users.update_one(
                    {"telegram_id": uid},
                    {"$set": {"username": username, "display_name": name, "updated_at": datetime.now()}}
                )
                user = await db.users.find_one({"telegram_id": uid})
    
    return dict(user)

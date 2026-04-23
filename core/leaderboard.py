# core/leaderboard.py - Liderlik Tablosu
from bson.decimal128 import Decimal128
from decimal import Decimal
from core.database import get_db

async def get_leaderboard(limit=15) -> list[dict]:
    db = await get_db()
    cursor = db.users.find().sort("balance", -1).limit(limit)
    users = await cursor.to_list(length=limit)
    
    for user in users:
        balance = user.get("balance", 0)
        if isinstance(balance, Decimal128):
            user["balance"] = int(balance.to_decimal())
        elif isinstance(balance, Decimal):
            user["balance"] = int(balance)
        else:
            try:
                user["balance"] = int(balance) if balance else 0
            except:
                user["balance"] = 0
    
    users.sort(key=lambda x: x.get("balance", 0), reverse=True)
    return users[:limit]

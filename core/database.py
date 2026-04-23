# core/database.py - MongoDB Bağlantısı
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, DATABASE_NAME

_mongo_client = None
_db = None

async def get_db():
    global _mongo_client, _db
    if _db is None:
        _mongo_client = AsyncIOMotorClient(
            MONGO_URI,
            serverSelectionTimeoutMS=30000,
            connectTimeoutMS=30000,
            socketTimeoutMS=60000,
            maxPoolSize=50,
            retryWrites=True,
            retryReads=True
        )
        _db = _mongo_client[DATABASE_NAME]
    return _db

async def init_db():
    db = await get_db()
    await db.users.create_index("telegram_id", unique=True)
    await db.transactions.create_index("from_id")
    await db.transactions.create_index("to_id")
    await db.games.create_index([("chat_id", 1), ("state", 1)])
    await db.game_participants.create_index("game_id")
    await db.user_stats.create_index("telegram_id", unique=True)
    await db.groups.create_index("chat_id", unique=True)

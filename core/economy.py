# core/economy.py - Bakiye İşlemleri
import asyncio
from datetime import datetime
from bson.decimal128 import Decimal128
from decimal import Decimal
from core.database import get_db

# Kullanıcı kilitleri (aynı anda aynı kişiye işlem yapılmasın)
_user_locks: dict[int, asyncio.Lock] = {}
_locks_meta = asyncio.Lock()

async def _get_lock(uid: int) -> asyncio.Lock:
    async with _locks_meta:
        if uid not in _user_locks:
            _user_locks[uid] = asyncio.Lock()
        return _user_locks[uid]

async def get_balance(uid: int) -> int:
    from core.users import get_user
    u = await get_user(uid)
    if not u:
        return 0
    balance = u.get("balance", 0)
    if isinstance(balance, Decimal128):
        return int(balance.to_decimal())
    elif isinstance(balance, Decimal):
        return int(balance)
    return int(balance) if balance else 0

async def add_balance(uid: int, amount: int, tx_type="win", desc="") -> bool:
    if amount <= 0:
        return False
    
    db = await get_db()
    lock = await _get_lock(uid)
    
    async with lock:
        try:
            dec_amount = Decimal128(str(amount))
            result = await db.users.update_one(
                {"telegram_id": uid},
                {"$inc": {"balance": dec_amount}, "$set": {"updated_at": datetime.now()}}
            )
            
            if result.modified_count > 0:
                await db.transactions.insert_one({
                    "to_id": uid,
                    "amount": dec_amount,
                    "type": tx_type,
                    "description": str(desc)[:200],
                    "created_at": datetime.now()
                })
                return True
        except Exception as e:
            from utils.format import logger
            logger.error(f"Bakiye eklenirken hata: {e}")
            return False
    
    return False

async def remove_balance(uid: int, amount: int, tx_type="bet", desc="") -> bool:
    if amount <= 0:
        return False
    
    db = await get_db()
    lock = await _get_lock(uid)
    
    async with lock:
        user = await db.users.find_one({"telegram_id": uid})
        if not user:
            return False
        
        # Mevcut bakiyeyi güvenli şekilde int'e çevir
        try:
            current_balance = user.get("balance", 0)
            if isinstance(current_balance, Decimal128):
                current_balance = int(current_balance.to_decimal())
            elif isinstance(current_balance, Decimal):
                current_balance = int(current_balance)
            else:
                current_balance = int(current_balance)
        except:
            from utils.format import logger
            logger.error(f"Bakiye dönüşüm hatası: {current_balance}")
            return False
        
        # Bakiye kontrolü
        if current_balance < amount:
            return False
        
        # Decimal128 dönüşümü ve veritabanı güncelleme
        try:
            amount_str = str(amount)
            dec_amount = Decimal128(amount_str)
            dec_negative = Decimal128("-" + amount_str)
            
            result = await db.users.update_one(
                {"telegram_id": uid},
                {"$inc": {"balance": dec_negative, "total_wagered": dec_amount},
                 "$set": {"updated_at": datetime.now()}}
            )
            
            if result.modified_count > 0:
                await db.transactions.insert_one({
                    "from_id": uid,
                    "amount": dec_amount,
                    "type": tx_type,
                    "description": str(desc)[:200],
                    "created_at": datetime.now()
                })
                return True
            else:
                return False
                
        except Exception as e:
            from utils.format import logger
            logger.error(f"Bakiye düşülürken hata: {e}")
            return False
    
    return False

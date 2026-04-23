# core/state.py - Oyun Durum Yönetimi
import asyncio
import uuid
import time
from datetime import datetime
from core.database import get_db
from config import MAX_OPEN_GAMES, RATE_LIMIT_SECONDS

# Aktif oyunlar (RAM'de tutulur)
_active_games: dict[int, dict[str, dict]] = {}
_state_lock = asyncio.Lock()

# ═══════════════════════════════════════════════════════════════
#  OYUN AÇMA / KAPAMA
# ═══════════════════════════════════════════════════════════════
async def can_open_game(chat_id: int, game_type: str) -> tuple[bool, str]:
    async with _state_lock:
        games = _active_games.get(chat_id, {})
        active = [g for g in games.values() if g["state"] != "FINISHED"]
        if len(active) >= MAX_OPEN_GAMES:
            return False, f"Bu grupta zaten {MAX_OPEN_GAMES} aktif oyun var."
        if any(g["game_type"] == game_type for g in active):
            return False, f"Bu grupta zaten açık bir {game_type} oyunu var."
        return True, ""

async def create_game(chat_id: int, game_type: str, message_id: int = 0) -> dict:
    game_id = str(uuid.uuid4())[:8].upper()
    game = {
        "game_id": game_id,
        "chat_id": chat_id,
        "game_type": game_type,
        "state": "OPEN",
        "message_id": message_id,
        "participants": {},
        "result": None,
        "task": None,
    }
    
    async with _state_lock:
        _active_games.setdefault(chat_id, {})[game_id] = game
    
    db = await get_db()
    await db.games.insert_one({
        "game_id": game_id,
        "chat_id": chat_id,
        "game_type": game_type,
        "state": "OPEN",
        "message_id": message_id,
        "result": None,
        "created_at": datetime.now(),
        "finished_at": None
    })
    
    return game

async def get_active_game(chat_id: int, game_type: str) -> dict | None:
    async with _state_lock:
        for g in _active_games.get(chat_id, {}).values():
            if g["game_type"] == game_type and g["state"] != "FINISHED":
                return g
    return None

async def finish_game(chat_id: int, game_id: str, result: str = "", ctx=None):
    async with _state_lock:
        if game_id in _active_games.get(chat_id, {}):
            _active_games[chat_id][game_id]["state"] = "FINISHED"
    
    db = await get_db()
    await db.games.update_one(
        {"game_id": game_id},
        {"$set": {"state": "FINISHED", "result": result, "finished_at": datetime.now()}}
    )
    
    # Jackpot dinleyici (ileride eklenecek)
    # from features.jackpot import process_jackpot_on_game_end
    # asyncio.create_task(process_jackpot_on_game_end(game_id, result, chat_id, ctx))

async def cleanup(chat_id: int):
    async with _state_lock:
        if chat_id in _active_games:
            _active_games[chat_id] = {
                gid: g for gid, g in _active_games[chat_id].items()
                if g["state"] != "FINISHED"
            }

# ═══════════════════════════════════════════════════════════════
#  KATILIMCI İŞLEMLERİ
# ═══════════════════════════════════════════════════════════════
async def add_participant(chat_id: int, game_id: str, uid: int, bet: int, bet_data: dict):
    async with _state_lock:
        game = _active_games.get(chat_id, {}).get(game_id)
        if not game:
            return

        if uid not in game["participants"]:
            game["participants"][uid] = {"bets": []}

        user_bets = game["participants"][uid]["bets"]
        merged = False
        
        bet_type = bet_data.get("type")
        if not bet_type:
            bet_type = game.get("game_type", "unknown")
            bet_data["type"] = bet_type

        for existing_bet in user_bets:
            existing_bd = existing_bet["bet_data"]
            existing_type = existing_bd.get("type")
            
            if bet_type == "color" and existing_type == "color":
                if bet_data.get("color") == existing_bd.get("color"):
                    existing_bet["bet"] += bet
                    merged = True
                    break
            
            elif bet_type == "number" and existing_type == "number":
                if set(bet_data.get("numbers", [])) == set(existing_bd.get("numbers", [])):
                    existing_bet["bet"] += bet
                    merged = True
                    break
            
            elif bet_type == existing_type and bet_type in ["dice", "wheel", "scratch_tournament"]:
                existing_bet["bet"] += bet
                merged = True
                break

        if not merged:
            user_bets.append({"bet": bet, "bet_data": bet_data})

    db = await get_db()
    
    all_bets = []
    total_bet = 0
    for b in user_bets:
        all_bets.append({"bet": b["bet"], "bet_data": b["bet_data"]})
        total_bet += b["bet"]
    
    await db.game_participants.update_one(
        {"game_id": game_id, "telegram_id": uid},
        {"$set": {"bets": all_bets, "bet_amount": total_bet, "updated_at": datetime.now()}},
        upsert=True
    )

async def get_participants(chat_id: int, game_id: str) -> dict:
    async with _state_lock:
        game = _active_games.get(chat_id, {}).get(game_id)
        if not game:
            return {}
        
        participants = {}
        for uid, data in game.get("participants", {}).items():
            participants[uid] = {
                "bets": [{"bet": b["bet"], "bet_data": b["bet_data"].copy()} for b in data.get("bets", [])]
            }
        return participants

# ═══════════════════════════════════════════════════════════════
#  RATE LIMITER
# ═══════════════════════════════════════════════════════════════
_last_cmd: dict[int, float] = {}

def is_rate_limited(uid: int) -> bool:
    now = time.monotonic()
    if now - _last_cmd.get(uid, 0) < RATE_LIMIT_SECONDS:
        return True
    _last_cmd[uid] = now
    return False

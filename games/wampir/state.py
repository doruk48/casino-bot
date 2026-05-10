# games/vampir/state.py - Oyun durumu ve global state yönetimi
import asyncio
import logging
from typing import Dict, Set, Optional, Any
from dataclasses import dataclass
from games.vampir.config import GamePhase

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# VERİ MODELLERİ
# ═══════════════════════════════════════════════════════════════
@dataclass
class Player:
    user_id: int
    username: str
    role: str = ""
    alive: bool = True
    lakap: str = ""

@dataclass
class GameConfig:
    group_id: Optional[int] = None
    started_by: Optional[int] = None

# ═══════════════════════════════════════════════════════════════
# GAMESTATE SINIFI
# ═══════════════════════════════════════════════════════════════
class GameState:
    def __init__(self):
        self.phase: GamePhase = GamePhase.LOBBY
        self.players: Dict[int, Player] = {}
        self.config = GameConfig()
        self.dead: Set[int] = set()
        self.night_actions: Dict[str, Any] = {
            "vampire": {},
            "doctor": {},
            "kurt": None,
            "sapik": None,
            "yaramaz_kiz": None,
            "gozcu": None,
        }
        self.votes: Dict[int, int] = {}
        self.expected_voters: Set[int] = set()
        self._timer_task: Optional[asyncio.Task] = None
        self._join_timer_task: Optional[asyncio.Task] = None
        self.join_time_left: int = 60
        self.vote_message_id: Optional[int] = None
        self._game_active: bool = False
        self.join_message_id: Optional[int] = None
        self.night_button_messages: Dict[int, int] = {}
        self.total_extra_time: int = 0

    @property
    def group_id(self) -> Optional[int]:
        return self.config.group_id

    @group_id.setter
    def group_id(self, value: int):
        self.config.group_id = value

    @property
    def started_by(self) -> Optional[int]:
        return self.config.started_by

    @started_by.setter
    def started_by(self, value: int):
        self.config.started_by = value

    def is_active(self) -> bool:
        return self._game_active

    def set_active(self, active: bool):
        self._game_active = active

    def add_player(self, user_id: int, username: str) -> bool:
        if user_id in self.players:
            return False
        self.players[user_id] = Player(user_id, username)
        return True

    def get_alive_players(self) -> list:
        return [p for p in self.players.values() if p.alive]

    def kill_player(self, user_id: int):
        if user_id in self.players:
            self.players[user_id].alive = False
            self.dead.add(user_id)

    def reset(self):
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        if self._join_timer_task and not self._join_timer_task.done():
            self._join_timer_task.cancel()
        self.__init__()
        logger.info("🛑 Oyun tamamen resetlendi!")

# ═══════════════════════════════════════════════════════════════
# GLOBAL STATE
# ═══════════════════════════════════════════════════════════════
games: Dict[int, GameState] = {}
state_lock = asyncio.Lock()

def get_game(group_id: int) -> GameState:
    if group_id not in games:
        games[group_id] = GameState()
        logger.info(f"🎮 Yeni oyun instance'ı oluşturuldu: {group_id}")
    return games[group_id]

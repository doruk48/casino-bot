import random
import asyncio
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

class GameState(Enum):
    LOBBY = "lobby"
    TEAM_SELECTION = "team_selection"
    PLAYER_DRAFT = "player_draft"
    DRAFT_FINISHED = "draft_finished"
    BLUE_CLUE = "blue_clue"
    RED_CLUE = "red_clue"
    BLUE_GUESS = "blue_guess"
    RED_GUESS = "red_guess"
    GAME_OVER = "game_over"

class TeamColor(Enum):
    BLUE = "mavi"
    RED = "kirmizi"

@dataclass
class Player:
    user_id: int
    first_name: str
    username: Optional[str] = None
    team: Optional[TeamColor] = None
    is_captain: bool = False
    is_spokesperson: bool = False

@dataclass
class GameRoom:
    game_id: str
    chat_id: int
    host_id: int
    state: GameState = GameState.LOBBY
    
    players: dict = field(default_factory=dict)
    blue_captain: Optional[int] = None
    red_captain: Optional[int] = None
    blue_spokesperson: Optional[int] = None
    red_spokesperson: Optional[int] = None
    blue_players: list = field(default_factory=list)
    red_players: list = field(default_factory=list)
    
    board_cells: list = field(default_factory=list)
    board_roles: list = field(default_factory=list)
    revealed_mask: list = field(default_factory=list)
    
    current_turn: Optional[TeamColor] = None
    clue_word: Optional[str] = None
    clue_number: Optional[int] = None
    guesses_remaining: int = 0
    max_guesses: int = 3
    
    lobby_msg_id: Optional[int] = None
    board_msg_id: Optional[int] = None
    info_msg_id: Optional[int] = None
    
    timer_task = None

    def get_player(self, user_id: int) -> Optional[Player]:
        return self.players.get(user_id)

    def add_player(self, user_id: int, first_name: str, username: Optional[str] = None):
        if user_id not in self.players:
            self.players[user_id] = Player(user_id=user_id, first_name=first_name, username=username)

    def get_mention(self, user_id: int) -> str:
        p = self.players.get(user_id)
        if p:
            return f"@{p.username}" if p.username else p.first_name
        return "Bilinmeyen"

    def setup_board(self, word_pool: list):
        selected = random.sample(word_pool, 25)
        roles = ["blue"] * 9 + ["red"] * 8 + ["civilian"] * 7 + ["assassin"]
        random.shuffle(roles)
        self.board_cells = selected
        self.board_roles = roles
        self.revealed_mask = [False] * 25

    def get_cell(self, word: str):
        try:
            idx = self.board_cells.index(word)
            return idx, self.board_roles[idx]
        except ValueError:
            return None, None

    def reveal(self, idx: int):
        self.revealed_mask[idx] = True
        return self.board_roles[idx]

    @property
    def blue_remaining(self):
        return sum(1 for i,r in enumerate(self.board_roles) if r=="blue" and not self.revealed_mask[i])
    @property
    def red_remaining(self):
        return sum(1 for i,r in enumerate(self.board_roles) if r=="red" and not self.revealed_mask[i])
    @property
    def is_assassin_revealed(self):
        return any(r=="assassin" and self.revealed_mask[i] for i,r in enumerate(self.board_roles))

# Aktif oyunları tutan sözlük ve kilit
_active_games = {}
_game_lock = asyncio.Lock()

async def get_game(chat_id: int) -> Optional[GameRoom]:
    async with _game_lock:
        return _active_games.get(chat_id)

async def set_game(chat_id: int, game: GameRoom):
    async with _game_lock:
        _active_games[chat_id] = game

async def remove_game(chat_id: int):
    async with _game_lock:
        _active_games.pop(chat_id, None)

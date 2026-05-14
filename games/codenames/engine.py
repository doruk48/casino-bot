import random
import asyncio
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


# ═══════════════════════════════════════════════════════════════
#  ENUM SINIFLARI
# ═══════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════
#  VERİ MODELLERİ
# ═══════════════════════════════════════════════════════════════

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

    # Oyuncu kayıtları
    players: dict = field(default_factory=dict)          # user_id -> Player
    blue_captain: Optional[int] = None
    red_captain: Optional[int] = None
    blue_spokesperson: Optional[int] = None
    red_spokesperson: Optional[int] = None
    blue_players: list = field(default_factory=list)     # user_id listesi
    red_players: list = field(default_factory=list)      # user_id listesi

    # Tahta
    board_cells: list = field(default_factory=list)      # 25 kelime
    board_roles: list = field(default_factory=list)      # 25 rol ("blue","red","civilian","assassin")
    revealed_mask: list = field(default_factory=list)    # 25 bool

    # Sıra yönetimi
    current_turn: Optional[TeamColor] = None
    clue_word: Optional[str] = None
    clue_number: Optional[int] = None
    guesses_remaining: int = 0
    max_guesses: int = 3

    # Mesaj ID'leri (güncelleme için)
    lobby_msg_id: Optional[int] = None
    board_msg_id: Optional[int] = None
    info_msg_id: Optional[int] = None

    # Zamanlayıcı
    timer_task = None

    # ═══════════════════════════════════════════════════════
    #  OYUNCU İŞLEMLERİ
    # ═══════════════════════════════════════════════════════

    def get_player(self, user_id: int) -> Optional[Player]:
        """ID'ye göre oyuncuyu döndür."""
        return self.players.get(user_id)

    def add_player(self, user_id: int, first_name: str, username: Optional[str] = None):
        """Yeni oyuncu ekle (zaten varsa dokunma)."""
        if user_id not in self.players:
            self.players[user_id] = Player(
                user_id=user_id,
                first_name=first_name,
                username=username
            )

    def get_mention(self, user_id: int) -> str:
        """Kullanıcıyı etiketlemek için mention string'i üret."""
        p = self.players.get(user_id)
        if p:
            return f"@{p.username}" if p.username else p.first_name
        return "Bilinmeyen"

    # ═══════════════════════════════════════════════════════
    #  TAHTA İŞLEMLERİ
    # ═══════════════════════════════════════════════════════

    def setup_board(self):
        """Kelime havuzundan 25 kelime seç, rolleri dağıt."""
        word_pool = load_word_pool()
        selected = random.sample(word_pool, min(25, len(word_pool)))
        roles = (
            ["blue"] * 9 +
            ["red"] * 8 +
            ["civilian"] * 7 +
            ["assassin"]
        )
        random.shuffle(roles)
        self.board_cells = selected
        self.board_roles = roles
        self.revealed_mask = [False] * 25

    def get_cell(self, word: str):
        """Kelimenin indeksini ve rolünü döndür. Bulamazsa (None, None)."""
        try:
            idx = self.board_cells.index(word)
            return idx, self.board_roles[idx]
        except ValueError:
            return None, None

    def reveal(self, idx: int):
        """Bir hücreyi açar ve rolünü döndürür."""
        self.revealed_mask[idx] = True
        return self.board_roles[idx]

    # ═══════════════════════════════════════════════════════
    #  DURUM BİLGİLERİ (property)
    # ═══════════════════════════════════════════════════════

    @property
    def blue_remaining(self):
        """Açılmamış mavi kelime sayısı."""
        return sum(1 for i, r in enumerate(self.board_roles)
                   if r == "blue" and not self.revealed_mask[i])

    @property
    def red_remaining(self):
        """Açılmamış kırmızı kelime sayısı."""
        return sum(1 for i, r in enumerate(self.board_roles)
                   if r == "red" and not self.revealed_mask[i])

    @property
    def is_assassin_revealed(self):
        """Suikastçı açıldı mı?"""
        return any(r == "assassin" and self.revealed_mask[i]
                   for i, r in enumerate(self.board_roles))


# ═══════════════════════════════════════════════════════════════
#  KELİME HAVUZU
# ═══════════════════════════════════════════════════════════════

def load_word_pool() -> list:
    """Kelime havuzunu dosyadan yükle. Dosya yoksa yedek liste döndür."""
    word_file = Path(__file__).parent / "words_tr.txt"

    if word_file.exists():
        with open(word_file, "r", encoding="utf-8") as f:
            words = [line.strip() for line in f if line.strip()]
        if len(words) >= 25:
            return words

    # Yedek kelime listesi (dosya yoksa veya yetersizse)
    return [
        "araba", "kalem", "okul", "tahta", "kitap", "masa", "sınav",
        "elma", "yol", "su", "ağaç", "telefon", "fare", "lamba",
        "güneş", "bulut", "saat", "müzik", "balık", "yıldız",
        "ev", "kapı", "köpek", "kedi", "deniz", "ateş", "dünya",
        "para", "altın", "gümüş", "demir", "çelik", "cam", "kağıt",
        "kalp", "beyin", "göz", "kulak", "dil", "diş", "parmak",
        "uyku", "rüya", "hayal", "ışık", "ayna", "pencere", "duvar"
    ]


# ═══════════════════════════════════════════════════════════════
#  AKTİF OYUN YÖNETİMİ (Thread-safe)
# ═══════════════════════════════════════════════════════════════

_active_games: dict[int, GameRoom] = {}
_game_lock = asyncio.Lock()


async def get_game(chat_id: int) -> Optional[GameRoom]:
    """chat_id'ye göre aktif oyunu getir."""
    async with _game_lock:
        return _active_games.get(chat_id)


async def set_game(chat_id: int, game: GameRoom):
    """Oyunu kaydet (yeni veya güncellenmiş)."""
    async with _game_lock:
        _active_games[chat_id] = game


async def remove_game(chat_id: int):
    """Oyunu sil."""
    async with _game_lock:
        _active_games.pop(chat_id, None)

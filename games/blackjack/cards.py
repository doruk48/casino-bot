# games/blackjack/cards.py - Kart İşlemleri ve Görseller
import io
import os
import random
from typing import List, Tuple
from PIL import Image

from config import BASE_DIR, CARD_WIDTH, CARD_HEIGHT, RANKS, SUITS

# ═══════════════════════════════════════════════════════════════
#  KART GÖRSELLERİ
# ═══════════════════════════════════════════════════════════════
def get_card_image(card: tuple) -> Image.Image:
    rank, suit = card
    rank_map = {"A": "ace", "2": "2", "3": "3", "4": "4", "5": "5", "6": "6",
                "7": "7", "8": "8", "9": "9", "10": "10", "J": "jack", "Q": "queen", "K": "king"}
    suit_map = {"♠️": "spades", "♥️": "hearts", "♦️": "diamonds", "♣️": "clubs"}
    filename = f"{rank_map.get(rank, rank)}_of_{suit_map.get(suit, 'spades')}.png"
    img_path = os.path.join(BASE_DIR, filename)
    
    if os.path.exists(img_path):
        img = Image.open(img_path)
        img = img.resize((CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS)
        return img
    return Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), color='#2c2c2c')

def get_face_down_card() -> Image.Image:
    back_path = os.path.join(BASE_DIR, "back.png")
    if os.path.exists(back_path):
        img = Image.open(back_path)
        img = img.resize((CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS)
        return img
    return Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), color='#2c2c2c')

def combine_cards(cards: list) -> io.BytesIO:
    if not cards:
        return None
    total_width = len(cards) * CARD_WIDTH
    combined = Image.new('RGB', (total_width, CARD_HEIGHT), color='#1a1a2e')
    for i, card in enumerate(cards):
        combined.paste(get_card_image(card), (i * CARD_WIDTH, 0))
    bio = io.BytesIO()
    combined.save(bio, format='PNG')
    bio.seek(0)
    return bio

def combine_cards_with_hidden(cards: list) -> io.BytesIO:
    if not cards:
        return None
    total_width = len(cards) * CARD_WIDTH
    combined = Image.new('RGB', (total_width, CARD_HEIGHT), color='#1a1a2e')
    combined.paste(get_face_down_card(), (0, 0))
    for i, card in enumerate(cards[1:], 1):
        combined.paste(get_card_image(card), (i * CARD_WIDTH, 0))
    bio = io.BytesIO()
    combined.save(bio, format='PNG')
    bio.seek(0)
    return bio

# ═══════════════════════════════════════════════════════════════
#  DESTE YÖNETİMİ
# ═══════════════════════════════════════════════════════════════
def _new_deck() -> List[Tuple[str, str]]:
    deck = [(r, s) for r in RANKS for s in SUITS]
    random.shuffle(deck)
    return deck

# ═══════════════════════════════════════════════════════════════
#  EL HESAPLAMA
# ═══════════════════════════════════════════════════════════════
def _card_val(rank: str) -> int:
    if rank in ("J", "Q", "K"):
        return 10
    if rank == "A":
        return 11
    return int(rank)

def _hand_val(hand: List[Tuple[str, str]]) -> int:
    total = sum(_card_val(r) for r, s in hand)
    aces = sum(1 for r, s in hand if r == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

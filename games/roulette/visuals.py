# games/roulette/visuals.py - Rulet Görselleri
import os
from config import BASE_DIR

def format_number_with_emoji(number: int) -> str:
    emoji_digits = {
        '0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
        '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'
    }
    return ''.join(emoji_digits[d] for d in str(number))

def get_rank_emoji(rank: int) -> str:
    if rank == 1:
        return "🥇"
    elif rank == 2:
        return "🥈"
    elif rank == 3:
        return "🥉"
    else:
        return "📍"

def get_roulette_image(number: int) -> str:
    if number == 0:
        img_path = os.path.join(BASE_DIR, "0.jpg")
    else:
        img_path = os.path.join(BASE_DIR, f"{number}.jpg")
    
    if not os.path.exists(img_path):
        spin_path = os.path.join(BASE_DIR, "spin.jpg")
        if os.path.exists(spin_path):
            img_path = spin_path
    return img_path

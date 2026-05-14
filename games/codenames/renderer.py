"""
Codenames tahta görseli oluşturucu.
Mevcut projenin font ve görsel altyapısını kullanır.
"""
import io
from pathlib import Path
from PIL import Image, ImageDraw
from config import BASE_DIR
from utils.fonts import get_font

# Ana klasördeki tahta şablonu
TEMPLATE_PATH = Path(BASE_DIR) / "board_template.png"

# Renk paleti
COLORS = {
    "hidden": "#000000",      # siyah (kapalı)
    "blue": "#0077FF",        # mavi takım
    "red": "#FF3B30",         # kırmızı takım
    "civilian": "#999999",    # boş sivil
    "assassin": "#000000",    # suikastçı
}

# 5x5 hücre merkez koordinatları
CELL_CENTERS = [
    (155, 155), (335, 155), (512, 155), (689, 155), (869, 155),   # 1. satır
    (155, 335), (335, 335), (512, 335), (689, 335), (869, 335),   # 2. satır
    (155, 512), (335, 512), (512, 512), (689, 512), (869, 512),   # 3. satır
    (155, 689), (335, 689), (512, 689), (689, 689), (869, 689),   # 4. satır
    (155, 869), (335, 869), (512, 869), (689, 869), (869, 869)    # 5. satır
]


def create_board_image(board_cells: list[str], revealed_mask: list[bool], roles: list[str]) -> io.BytesIO:
    """
    Codenames oyun tahtası görseli oluşturur.
    
    Args:
        board_cells: 25 kelimelik liste
        revealed_mask: 25 booleans, True = açılmış hücre
        roles: 25 roller ("blue", "red", "civilian", "assassin")
    
    Returns:
        io.BytesIO: PNG formatında görsel buffer'ı
    """
    # Şablonu aç
    if TEMPLATE_PATH.exists():
        img = Image.open(TEMPLATE_PATH).copy()
    else:
        # Şablon yoksa yedek düz görsel oluştur
        img = Image.new('RGB', (1024, 1024), color='#1a1a2e')
    
    draw = ImageDraw.Draw(img)
    font = get_font(22)  # Sabit 22 punto - senin font sisteminle

    for i, (cx, cy) in enumerate(CELL_CENTERS):
        word = board_cells[i]
        is_revealed = revealed_mask[i]
        role = roles[i] if is_revealed else "hidden"

        color = COLORS.get(role, COLORS["hidden"])
        
        if is_revealed:
            # Açılan kelimenin başına renkli kutu sembolü
            display_text = f"■ {word}"
        else:
            # Kapalı kelime: sadece metin, siyah renkte
            display_text = word

        # Metni hücre merkezine ortala (anchor="mm")
        draw.text((cx, cy), display_text, fill=color, font=font, anchor="mm")

    # BytesIO'ya kaydet
    bio = io.BytesIO()
    img.save(bio, format='PNG', quality=95)
    bio.seek(0)
    return bio

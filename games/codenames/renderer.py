from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import os

# Ana klasördeki şablon
TEMPLATE_PATH = Path(__file__).parent.parent.parent / "board_template.png"

# Font yolu - mevcut botundaki fonts klasörünü kullan
FONTS_DIR = Path(__file__).parent.parent.parent / "fonts"

# Renk paleti
COLORS = {
    "hidden": "#000000",      # siyah (kapalı)
    "blue": "#0077FF",        # mavi takım
    "red": "#FF3B30",         # kırmızı takım
    "civilian": "#999999",    # boş sivil
    "assassin": "#000000",    # suikastçı (siyah kalın)
}

# 5x5 hücre merkez koordinatları
CELL_CENTERS = [
    (155, 155), (335, 155), (512, 155), (689, 155), (869, 155),   # 1. satır
    (155, 335), (335, 335), (512, 335), (689, 335), (869, 335),   # 2. satır
    (155, 512), (335, 512), (512, 512), (689, 512), (869, 512),   # 3. satır
    (155, 689), (335, 689), (512, 689), (689, 689), (869, 689),   # 4. satır
    (155, 869), (335, 869), (512, 869), (689, 869), (869, 869)    # 5. satır
]

def get_font(size=22):
    """Mevcut projedeki fontu yükle. Bulamazsa default kullan."""
    for font_name in ["DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "arial.ttf"]:
        font_path = FONTS_DIR / font_name
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size)
    return ImageFont.load_default()


def create_board_image(board_cells, revealed_mask, roles):
    """
    Tahta görselini oluştur.
    
    Args:
        board_cells: list[str] 25 kelime
        revealed_mask: list[bool] 25 adet, True = açık
        roles: list[str] 25 adet, "blue"/"red"/"civilian"/"assassin"
    
    Returns:
        PIL.Image
    """
    img = Image.open(TEMPLATE_PATH).copy()
    draw = ImageDraw.Draw(img)
    font = get_font()

    for i, (cx, cy) in enumerate(CELL_CENTERS):
        word = board_cells[i]
        is_revealed = revealed_mask[i]
        role = roles[i]

        if is_revealed:
            color = COLORS.get(role, COLORS["hidden"])
            # Açılan kelimenin başına renkli kutu sembolü
            display_text = f"■ {word}"
        else:
            color = COLORS["hidden"]
            display_text = word  # Kapalı: sadece kelime, başında sembol yok

        # Metni hücrenin merkezine ortala
        draw.text((cx, cy), display_text, fill=color, font=font, anchor="mm")

    return img

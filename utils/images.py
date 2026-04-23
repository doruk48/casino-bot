# utils/images.py - Görsel İşlemleri
import io
import os
import re
from PIL import Image, ImageDraw
from config import BASE_DIR, CURRENCY_SYMBOL
from utils.fonts import get_font
from utils.format import format_amount

# ═══════════════════════════════════════════════════════════════
#  GÖRSEL ÖNBELLEĞİ
# ═══════════════════════════════════════════════════════════════
_image_cache = {}

def get_cached_image(path: str) -> io.BytesIO | None:
    if path not in _image_cache:
        if os.path.exists(path):
            with open(path, "rb") as f:
                _image_cache[path] = f.read()
        else:
            return None
    bio = io.BytesIO(_image_cache[path])
    bio.seek(0)
    return bio

# ═══════════════════════════════════════════════════════════════
#  TRANSFER GÖRSELİ
# ═══════════════════════════════════════════════════════════════
def create_transfer_image(sender: str, receiver: str, amount: int) -> io.BytesIO:
    transfer_template = os.path.join(BASE_DIR, "transfer.png")
    
    if not os.path.exists(transfer_template):
        img = Image.new('RGB', (800, 600), color='#1a1a2e')
    else:
        img = Image.open(transfer_template).convert('RGBA')
    
    img.thumbnail((800, 600), Image.Resampling.LANCZOS)
    
    width, height = img.size
    txt_layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)
    
    font_isim = get_font(int(height * 0.10))
    font_miktar = get_font(int(height * 0.13))
    font_token = get_font(int(height * 0.067))
    
    gold_color = "#B8860B"
    shadow_color = "#4a3a1a"
    
    draw.text((width * 0.57, height * 0.19), sender, fill="#F5F5F5", font=font_isim, anchor="mm")
    draw.text((width * 0.57, height * 0.53), receiver, fill="#F5F5F5", font=font_isim, anchor="mm")
    
    amount_text = format_amount(amount).replace(CURRENCY_SYMBOL, "").strip()
    draw.text((width * 0.47 + 3, height * 0.86 + 3), amount_text, fill=shadow_color, font=font_miktar, anchor="lm")
    draw.text((width * 0.47, height * 0.86), amount_text, fill=gold_color, font=font_miktar, anchor="lm")
    
    try:
        text_w = draw.textlength(amount_text, font=font_miktar)
        draw.text((width * 0.47 + text_w + 20 + 3, height * 0.87 + 3), "Token", fill=shadow_color, font=font_token, anchor="lm")
        draw.text((width * 0.47 + text_w + 20, height * 0.87), "Token", fill=gold_color, font=font_token, anchor="lm")
    except:
        pass
    
    img = Image.alpha_composite(img, txt_layer).convert('RGB')
    bio = io.BytesIO()
    img.save(bio, format='PNG', quality=95)
    bio.seek(0)
    return bio

# ═══════════════════════════════════════════════════════════════
#  ZAR GÖRSELLERİ
# ═══════════════════════════════════════════════════════════════
def create_dice_image(number: int) -> io.BytesIO:
    size = 80
    img = Image.new('RGB', (size, size), color='#5C2E0B')
    draw = ImageDraw.Draw(img)
    
    draw.rounded_rectangle([3, 3, size-4, size-4], radius=10, outline='#FFD700', width=3)
    draw.rounded_rectangle([7, 7, size-8, size-8], radius=7, outline='#DAA520', width=1)
    
    margin = size // 5
    center = size // 2
    
    dot_positions = {
        1: [(center, center)],
        2: [(margin, margin), (size-margin, size-margin)],
        3: [(margin, margin), (center, center), (size-margin, size-margin)],
        4: [(margin, margin), (size-margin, margin), (margin, size-margin), (size-margin, size-margin)],
        5: [(margin, margin), (size-margin, margin), (center, center), (margin, size-margin), (size-margin, size-margin)],
        6: [(margin, margin), (size-margin, margin), (margin, center), (size-margin, center), (margin, size-margin), (size-margin, size-margin)]
    }
    
    dot_radius = size // 11
    
    for x, y in dot_positions.get(number, []):
        draw.ellipse([x-dot_radius+1, y-dot_radius+1, x+dot_radius+1, y+dot_radius+1], fill='#000000')
        draw.ellipse([x-dot_radius, y-dot_radius, x+dot_radius, y+dot_radius], fill='#1a1a1a')
        highlight_radius = dot_radius // 2
        draw.ellipse([x-highlight_radius, y-highlight_radius, x, y], fill='#555555')
    
    bio = io.BytesIO()
    img.save(bio, format='PNG', quality=95)
    bio.seek(0)
    return bio

def create_total_card(total: int) -> io.BytesIO:
    size = 80
    img = Image.new('RGB', (size, size), color='#1B5E20')
    draw = ImageDraw.Draw(img)
    
    draw.rounded_rectangle([3, 3, size-4, size-4], radius=10, outline='#FFD700', width=3)
    draw.rounded_rectangle([7, 7, size-8, size-8], radius=7, outline='#DAA520', width=1)
    
    try:
        font = get_font(42)
        bbox = draw.textbbox((0, 0), str(total), font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((size//2 - tw//2 + 2, size//2 - th//2 + 2), str(total), fill='#0D3B0F', font=font)
        draw.text((size//2 - tw//2, size//2 - th//2), str(total), fill='#FFD700', font=font)
    except:
        draw.text((size//2, size//2), str(total), fill='#FFD700', anchor="mm")
    
    bio = io.BytesIO()
    img.save(bio, format='PNG', quality=95)
    bio.seek(0)
    return bio

def combine_dice_with_total(dice1: int, dice2: int) -> io.BytesIO:
    size = 80
    spacing = 8
    total_width = size * 3 + spacing * 2
    total_height = size
    
    combined = Image.new('RGB', (total_width, total_height), color='#1a1a2e')
    
    img1 = Image.open(create_dice_image(dice1))
    img2 = Image.open(create_dice_image(dice2))
    img_total = Image.open(create_total_card(dice1 + dice2))
    
    combined.paste(img1, (0, 0))
    combined.paste(img2, (size + spacing, 0))
    combined.paste(img_total, (size * 2 + spacing * 2, 0))
    
    bio = io.BytesIO()
    combined.save(bio, format='PNG', quality=95)
    bio.seek(0)
    return bio

# ═══════════════════════════════════════════════════════════════
#  JACKPOT GÖRSELİ
# ═══════════════════════════════════════════════════════════════
def create_jackpot_image(game_type: str, winner_name: str) -> io.BytesIO | None:
    try:
        if game_type == "wheel":
            img_path = os.path.join(BASE_DIR, "jackpot_wheel.jpg")
        elif game_type == "blackjack":
            img_path = os.path.join(BASE_DIR, "jackpot_blackjack.jpg")
        else:
            return None
        
        if not os.path.exists(img_path):
            return None
        
        img = Image.open(img_path).convert('RGBA')
        img.thumbnail((800, 600), Image.Resampling.LANCZOS)
        
        width, height = img.size
        txt_layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)
        
        font_isim = get_font(int(height * 0.10))
        gold_color = "#FFFFFF"
        shadow_color = "#1a1a1a"
        
        name_x = int(width * 0.60)
        name_y = int(height * 0.25)
        
        clean_name = re.sub(r'[^a-zA-Z0-9ğüşıöçĞÜŞİÖÇ\s]', '', winner_name)
        if not clean_name:
            clean_name = winner_name
        if len(clean_name) > 10:
            clean_name = clean_name[:10] + "..."
        
        draw.text((name_x + 3, name_y + 3), clean_name, fill=shadow_color, font=font_isim, anchor="lm")
        draw.text((name_x, name_y), clean_name, fill=gold_color, font=font_isim, anchor="lm")
        
        img = Image.alpha_composite(img, txt_layer).convert('RGB')
        bio = io.BytesIO()
        img.save(bio, format='PNG', quality=95)
        bio.seek(0)
        return bio
        
    except Exception as e:
        from utils.format import logger
        logger.error(f"Jackpot görseli oluşturulamadı: {e}")
        return None

# ═══════════════════════════════════════════════════════════════
#  KAZI KAZAN GÖRSELİ
# ═══════════════════════════════════════════════════════════════
def create_scratch_result_image(board: list, winner_mult: int) -> io.BytesIO:
    acik_kart = os.path.join(BASE_DIR, "acik.jpg")
    
    if not os.path.exists(acik_kart):
        img = Image.new('RGB', (800, 600), color='#1a1a2e')
    else:
        img = Image.open(acik_kart)
    
    img.thumbnail((800, 600), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(img)
    font = get_font(100)
    
    width, height = img.size
    
    boxes = [
        {"center": (width * 0.16, height * 0.25), "index": 0},
        {"center": (width * 0.51, height * 0.25), "index": 1},
        {"center": (width * 0.83, height * 0.25), "index": 2},
        {"center": (width * 0.16, height * 0.69), "index": 3},
        {"center": (width * 0.51, height * 0.69), "index": 4},
        {"center": (width * 0.83, height * 0.69), "index": 5},
    ]
    
    for box in boxes:
        center_x = int(box["center"][0])
        center_y = int(box["center"][1])
        value = board[box["index"]]
        
        if value == winner_mult and winner_mult > 0:
            text_color = (0, 255, 0)
        elif value == 0:
            text_color = (255, 0, 0)
        else:
            text_color = (255, 255, 255)
        
        text = f"{value}x"
        
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        
        draw.text((center_x - tw/2 + 3, center_y - th/2 + 3), text, fill=(0, 0, 0), font=font, stroke_width=3, stroke_fill=(0, 0, 0))
        draw.text((center_x - tw/2, center_y - th/2), text, fill=text_color, font=font)
    
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    return bio

# utils/fonts.py - Font Yönetimi (Dockerfile ile uyumlu)
import os
from PIL import ImageFont

def get_font(size: int):
    """Railway için font yükle - Dockerfile otomatik halleder"""
    
    fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    
    for font_path in fonts:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except:
                continue
    
    print(f"⚠️ Font bulunamadı!")
    return ImageFont.load_default()

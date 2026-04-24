# utils/fonts.py - Font Yönetimi (Sabit Piksel Desteği)
import os
from PIL import ImageFont

_font_cache = {}

def get_font(size: int):
    """Sistemdeki fontları dene, hiçbiri yoksa default kullan.
       Artık size parametresi olarak doğrudan piksel değeri (82, 110, 50) alır."""
    if size in _font_cache:
        return _font_cache[size]
    
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        "/system/fonts/Roboto-Bold.ttf",
    ]
    
    for path in font_paths:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _font_cache[size] = font
                return font
            except:
                continue
    
    # Hiçbiri bulunamazsa varsayılan font
    _font_cache[size] = ImageFont.load_default()
    return _font_cache[size]

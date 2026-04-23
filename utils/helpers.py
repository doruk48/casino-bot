# utils/helpers.py - Yardımcı Fonksiyonlar
import re
from config import LEVELS

def clean_name(name: str) -> str:
    """Sadece harf, rakam ve boşluk bırakır (Görselde hata vermemesi için)"""
    cleaned = re.sub(r'[^a-zA-Z0-9ğüşıöçĞÜŞİÖÇ\s]', '', name)
    return cleaned.strip()

def get_level(balance: int) -> tuple[str, str]:
    """Bakiyeye göre seviye ve emoji döndür"""
    result = (LEVELS[0][1], LEVELS[0][2])
    for min_bal, name, emoji in LEVELS:
        if balance >= min_bal:
            result = (name, emoji)
    return result

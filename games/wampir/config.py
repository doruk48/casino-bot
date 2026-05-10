# games/vampir/config.py - Sabitler ve yapılandırma
from enum import Enum

# ═══════════════════════════════════════════════════════════════
# GÖRSEL URL'leri
# ═══════════════════════════════════════════════════════════════
# games/vampir/config.py - GÖRSEL KISMI GÜNCELLENDİ

RAW_BASE = "https://raw.githubusercontent.com/doruk48/casino-bot/main"

IMAGES = {
    "START": f"{RAW_BASE}/start.jpg",
    "VAMPIR_WIN": f"{RAW_BASE}/kotu_kazandi.jpg",
    "KOYLU_WIN": f"{RAW_BASE}/koylu_kazandi.jpg",
    "IBLIS_WIN": f"{RAW_BASE}/kotu_kazandi.jpg",        # İblis de kötü takım
    "KURT": f"{RAW_BASE}/kurt_av.jpg",
    "ROMANTIC": f"{RAW_BASE}/sapik_romantik.jpg",
    "STEAMY": f"{RAW_BASE}/yaramaz_kiz.jpg",
    "YARAMAZ_KIZ": f"{RAW_BASE}/yaramaz_kiz.jpg",
}

# ═══════════════════════════════════════════════════════════════
# ROLLER
# ═══════════════════════════════════════════════════════════════
ROLES = {
    "VAMPIR": "🧛 Vampir",
    "DOKTOR": "🩺 Doktor",
    "KOYLU": "👨‍🌾 Köylü",
    "KURT": "🐺 Alfa Kurt",
    "SAPIK": "😈 Köyün Sapığı",
    "YARAMAZ_KIZ": "🔥 Köyün Yaramaz Kızı",
    "IBLIS": "👹 İblis",
    "GOZCU": "👁️ Gözcü",
    "SASKIN": "🤪 Şaşkın",
}

# ═══════════════════════════════════════════════════════════════
# KÖYLÜ LAKAPLARI
# ═══════════════════════════════════════════════════════════════
KOYLU_LAKAPLARI = [
    "👨‍🌾 Köyün Muhtarı", "👩‍🌾 Köyün Güzeli", "🧑‍🌾 Yaramaz Çocuk",
    "👨‍🌾 Bilge Çiftçi", "👩‍🌾 Dedikoducu Kadın", "🧑‍🌾 Köy Delisi",
    "👨‍🌾 Kasap Usta", "👩‍🌾 Fırıncı Kadın", "🧑‍🌾 Avcı Mehmet",
    "👨‍🌾 Balıkçı Hasan", "👩‍🌾 Öğretmen Ayşe", "🧑‍🌾 Doktor Yardımcısı",
    "👨‍🌾 Demirci Usta", "👩‍🌾 Çamaşırcı Kadın", "🧑‍🌾 Çoban Ali",
]

# ═══════════════════════════════════════════════════════════════
# OYUN FAZI
# ═══════════════════════════════════════════════════════════════
class GamePhase(Enum):
    LOBBY = "lobby"
    PLAYING = "playing"
    NIGHT = "night"
    DAY = "day"

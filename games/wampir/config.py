# games/vampir/config.py - Sabitler ve yapılandırma
from enum import Enum

# ═══════════════════════════════════════════════════════════════
# GÖRSEL URL'leri
# ═══════════════════════════════════════════════════════════════
IMAGES = {
    "START": "https://images.unsplash.com/photo-1518709268805-4e9042af2176?ixlib=rb-4.0.3&auto=format&fit=crop&w=1200&q=80",
    "VAMPIR_WIN": "https://st.depositphotos.com/1027404/3087/i/450/depositphotos_30878139-stock-photo-beautiful-vampire-and-her-victim.jpg",
    "KOYLU_WIN": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?ixlib=rb-4.0.3&auto=format&fit=crop&w=1200&q=80",
    "IBLIS_WIN": "https://st5.depositphotos.com/1001959/64677/i/450/depositphotos_646777630-stock-photo-studio-shot-five-prayers-esoteric.jpg",
    "KURT": "https://pbs.twimg.com/media/GiAgM0hWYAEFfgf.jpg",
    "ROMANTIC": "https://img-s2.onedio.com/id-546b32c7c46c6abd704a34e7/rev-0/w-1200/h-873/f-jpg/s-259ca65e27c07f0a0a0463447e878f58010b3b33.jpg",
    "STEAMY": "https://st4.depositphotos.com/1022135/21314/i/450/depositphotos_213143798-stock-photo-young-man-waiting-sexy-woman.jpg",
    "YARAMAZ_KIZ": "https://st4.depositphotos.com/1022135/21314/i/450/depositphotos_213143798-stock-photo-young-man-waiting-sexy-woman.jpg",
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

# games/vampir/engine.py - Vampir Köylü oyun motoru (TÜM HATALAR DÜZELTİLDİ)
import asyncio
import random
import logging
from typing import Dict, Set, Optional, Any
from dataclasses import dataclass
from enum import Enum

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# SABİTLER
# ═══════════════════════════════════════════════════════════════
RAW_BASE = "https://raw.githubusercontent.com/doruk48/casino-bot/main"

IMAGES = {
    "START": f"{RAW_BASE}/start.jpg",
    "VAMPIR_WIN": f"{RAW_BASE}/kotu_kazandi.jpg",
    "KOYLU_WIN": f"{RAW_BASE}/koylu_kazandi.jpg",
    "IBLIS_WIN": f"{RAW_BASE}/kotu_kazandi.jpg",
    "KURT": f"{RAW_BASE}/kurt_av.jpg",
    "ROMANTIC": f"{RAW_BASE}/sapik_romantik.jpg",
    "STEAMY": f"{RAW_BASE}/yaramaz_kiz.jpg",
    "YARAMAZ_KIZ": f"{RAW_BASE}/yaramaz_kiz.jpg",
}

ROLES = {
    "VAMPIR": "🧛 Vampir",
    "DOKTOR": "🩺 Doktor",
    "DOKTOR_YARDIMCI": "🩺 Doktor Yardımcısı",
    "KOYLU": "👨‍🌾 Köylü",
    "KURT": "🐺 Alfa Kurt",
    "SAPIK": "😈 Köyün Sapığı",
    "YARAMAZ_KIZ": "🔥 Köyün Yaramaz Kızı",
    "IBLIS": "👹 İblis",
    "GOZCU": "👁️ Gözcü",
    "SASKIN": "🤪 Şaşkın",
}

KOYLU_LAKAPLARI = [
    "👨‍🌾 Köyün Muhtarı", "👩‍🌾 Köyün Güzeli", "🧑‍🌾 Yaramaz Çocuk",
    "👨‍🌾 Bilge Çiftçi", "👩‍🌾 Dedikoducu Kadın", "🧑‍🌾 Köy Delisi",
    "👨‍🌾 Kasap Usta", "👩‍🌾 Fırıncı Kadın", "🧑‍🌾 Avcı Mehmet",
    "👨‍🌾 Balıkçı Hasan", "👩‍🌾 Öğretmen Ayşe", "🧑‍🌾 Doktor Yardımcısı",
    "👨‍🌾 Demirci Usta", "👩‍🌾 Çamaşırcı Kadın", "🧑‍🌾 Çoban Ali",
]

class GamePhase(Enum):
    LOBBY = "lobby"
    PLAYING = "playing"
    NIGHT = "night"
    DAY = "day"

# ═══════════════════════════════════════════════════════════════
# VERİ MODELLERİ
# ═══════════════════════════════════════════════════════════════
@dataclass
class Player:
    user_id: int
    username: str
    role: str = ""
    alive: bool = True
    lakap: str = ""

class GameState:
    def __init__(self):
        self.phase = GamePhase.LOBBY
        self.players: Dict[int, Player] = {}
        self.group_id: Optional[int] = None
        self.started_by: Optional[int] = None
        self.dead: Set[int] = set()
        self.night_actions: Dict[str, Any] = {
            "vampire": {}, "doctor": {}, "kurt": None,
            "sapik": None, "yaramaz_kiz": None, "gozcu": None,
        }
        self.votes: Dict[int, int] = {}
        self.expected_voters: Set[int] = set()
        self._timer_task: Optional[asyncio.Task] = None
        self._join_timer_task: Optional[asyncio.Task] = None
        self.join_time_left = 60
        self.vote_message_id: Optional[int] = None
        self._active = False
        self.join_message_id: Optional[int] = None
        self.night_buttons: Dict[int, int] = {}
        self.total_extra_time = 0

    def is_active(self): return self._active
    def set_active(self, a): self._active = a
    def add_player(self, uid, name):
        if uid in self.players: return False
        self.players[uid] = Player(uid, name)
        return True
    def get_alive(self):
        return [p for p in self.players.values() if p.alive]
    def kill(self, uid):
        if uid in self.players:
            self.players[uid].alive = False
            self.dead.add(uid)
    def reset(self):
        if self._timer_task and not self._timer_task.done(): self._timer_task.cancel()
        if self._join_timer_task and not self._join_timer_task.done(): self._join_timer_task.cancel()
        self.__init__()

# Global state
games: Dict[int, GameState] = {}
state_lock = asyncio.Lock()

def get_game(gid: int) -> GameState:
    if gid not in games:
        games[gid] = GameState()
    return games[gid]

# ═══════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════
async def send_msg(ctx, cid, text, markup=None):
    try:
        return await ctx.bot.send_message(chat_id=cid, text=text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Mesaj hatası: {e}")

async def send_photo(ctx, cid, url, caption=""):
    try:
        await ctx.bot.send_photo(chat_id=cid, photo=url, caption=caption, parse_mode="Markdown")
    except:
        await send_msg(ctx, cid, caption)

async def send_pm(app, uid, text, markup=None):
    try:
        await app.bot.send_message(chat_id=uid, text=text, reply_markup=markup, parse_mode="Markdown")
        return True
    except:
        return False

def build_buttons(game, only_alive=True, gid=None, phase="night"):
    if not game.players: return None
    players = game.get_alive() if only_alive else list(game.players.values())
    rows, row = [], []
    for p in players:
        if not only_alive and not p.alive: continue
        btn = InlineKeyboardButton(
            f"{p.username} {'💀' if not p.alive else ''}",
            callback_data=f"vampir_t_{gid}_{p.user_id}_{phase}"
        )
        row.append(btn)
        if len(row) == 2:
            rows.append(row)
            row = []
    if row: rows.append(row)
    return InlineKeyboardMarkup(rows) if rows else None

def join_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🎮 Oyuna Katıl", callback_data="vampir_join")]])

async def update_join_msg(ctx, game):
    """Katılım mesajını güncelle - handlers.py'den de çağrılır"""
    if not game.join_message_id: return
    try:
        txt = "🎮 *Katılanlar:*\n"
        for i, p in enumerate(game.players.values(), 1):
            txt += f"{i}. {p.username}\n"
        txt += f"\n📊 {len(game.players)}/5 kişi"
        await ctx.bot.edit_message_text(
            chat_id=game.group_id, message_id=game.join_message_id,
            text=txt, reply_markup=join_btn(), parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Join update hatası: {e}")

# ═══════════════════════════════════════════════════════════════
# ROL ATAMA
# ═══════════════════════════════════════════════════════════════
def assign_roles(game):
    players = list(game.players.values())
    random.shuffle(players)
    n = len(players)

    vamp_n = 1 if n <= 6 else (2 if n <= 10 else 3)
    doc_n = 2 if n >= 8 else 1
    has_special = n >= 8
    has_kurt = n >= 10
    has_new = n >= 10

    roles = []
    for _ in range(vamp_n): roles.append(ROLES["VAMPIR"])
    for i in range(doc_n):
        roles.append(ROLES["DOKTOR"] if i == 0 else ROLES["DOKTOR_YARDIMCI"])
    if has_kurt: roles.append(ROLES["KURT"])
    if has_special: roles.append(random.choice([ROLES["SAPIK"], ROLES["YARAMAZ_KIZ"]]))
    if has_new:
        new = random.sample([ROLES["GOZCU"], ROLES["SASKIN"]], random.randint(1, 2))
        roles.extend(new)
    if n >= 10 and random.random() < 0.3: roles.append(ROLES["IBLIS"])

    koylu_n = n - len(roles)
    lakap = random.sample(KOYLU_LAKAPLARI, min(koylu_n, len(KOYLU_LAKAPLARI)))
    for i in range(koylu_n):
        roles.append(lakap[i] if i < len(lakap) else ROLES["KOYLU"])

    random.shuffle(roles)
    for p, r in zip(players, roles):
        p.role = r
        if r in KOYLU_LAKAPLARI or r == ROLES["KOYLU"]:
            p.lakap = r

# ═══════════════════════════════════════════════════════════════
# GECE
# ═══════════════════════════════════════════════════════════════
async def start_night(ctx, game, app):
    game.phase = GamePhase.NIGHT
    game.night_actions = {
        "vampire": {}, "doctor": {}, "kurt": None,
        "sapik": None, "yaramaz_kiz": None, "gozcu": None,
    }

    alive = game.get_alive()
    vamps = [p for p in alive if "Vampir" in p.role]
    docs = [p for p in alive if "Doktor" in p.role]
    kurt = next((p for p in alive if "Kurt" in p.role), None)
    sapik = next((p for p in alive if p.role == ROLES["SAPIK"]), None)
    yk = next((p for p in alive if p.role == ROLES["YARAMAZ_KIZ"]), None)
    gozcu = next((p for p in alive if p.role == ROLES["GOZCU"]), None)

    game.expected_voters = {
        p.user_id for p in vamps + docs +
        ([kurt] if kurt else []) + ([sapik] if sapik else []) +
        ([yk] if yk else []) + ([gozcu] if gozcu else [])
    }

    # Rol bazlı buton metinleri - DOKTOR_YARDIMCI eklendi
    txt = {
        "VAMPIR": "🌑 *VAMPİR*\n🩸 Kimi ısıracaksın?\n⏰ 60 saniye\n⚠️ Takım arkadaşını seçemezsin!",
        "DOKTOR": "💉 *DOKTOR*\n⛑️ Kimi koruyacaksın?\n⏰ 60 saniye",
        "DOKTOR_YARDIMCI": "💉 *DOKTOR YARDIMCISI*\n⛑️ Kimi koruyacaksın?\n⏰ 60 saniye",
        "KURT": "🐺 *ALFA KURT*\n⚔️ Kimi avlayacaksın?\n🎯 Sadece vampirleri!\n⏰ 60 saniye",
        "SAPIK": "😈 *SAPIK*\n🌙 Kimin koynuna gireceksin?\n⏰ 60 saniye",
        "YARAMAZ_KIZ": "🔥 *YARAMAZ KIZ*\n🌙 Kime sürpriz yapacaksın?\n⏰ 60 saniye",
        "GOZCU": "👁️ *GÖZCÜ*\n🔍 Kimi gözlemleyeceksin?\n⏰ 60 saniye",
    }

    for p in alive:
        key = None
        for k, v in ROLES.items():
            if v == p.role:
                key = k
                break
        if key not in txt:
            continue
        try:
            msg = await app.bot.send_message(
                chat_id=p.user_id, text=txt[key],
                reply_markup=build_buttons(game, gid=game.group_id, phase="night"),
                parse_mode="Markdown"
            )
            game.night_buttons[p.user_id] = msg.message_id
        except Exception as e:
            logger.error(f"Gece buton hatası {p.username}: {e}")

    # Grup mesajı - ekstra roller
    extras = []
    if kurt: extras.append("🐺 Alfa Kurt avlanıyor")
    if sapik: extras.append("😈 Sapık hazırlanıyor")
    if yk: extras.append("🔥 Yaramaz Kız hazırlanıyor")
    if gozcu: extras.append("👁️ Gözcü gözlemliyor")

    await send_msg(ctx, game.group_id,
        f"🌙 *GECE BAŞLADI!*\n\n🧛‍♂️ Vampirler avlanıyor...\n"
        f"🩺 Doktorlar hazırlanıyor...\n" +
        "\n".join(extras) +
        f"\n\n⏰ *Karar süresi: 60 saniye*"
    )

    if game._timer_task and not game._timer_task.done():
        game._timer_task.cancel()
    game._timer_task = asyncio.create_task(night_timer(ctx, game, app))


async def night_timer(ctx, game, app):
    for remaining in range(60, 0, -1):
        if game.phase != GamePhase.NIGHT:
            return
        await asyncio.sleep(1)
        if remaining == 30:
            await send_msg(ctx, game.group_id, "⚠️ *30 saniye kaldı!*")
        elif remaining == 10:
            await send_msg(ctx, game.group_id, "🚨 *SON 10 SANİYE!*")

    await end_night(ctx, game, app)


async def end_night(ctx, game, app):
    game.phase = GamePhase.PLAYING

    # Kurt hedefi
    deaths = set()
    kt = game.night_actions.get("kurt")
    if kt and kt in game.players and game.players[kt].alive:
        if "Vampir" in game.players[kt].role:
            deaths.add(kt)

    # Korunanlar
    protected = set(game.night_actions.get("doctor", {}).values())

    # Vampir saldırıları
    for vid, tid in game.night_actions.get("vampire", {}).items():
        if tid in game.players and game.players[tid].alive and tid not in protected:
            deaths.add(tid)

    # Sapık bildirimi
    sapik = next((p for p in game.players.values() if p.role == ROLES["SAPIK"] and p.alive), None)
    st = game.night_actions.get("sapik")
    if sapik and st and st in game.players and game.players[st].alive:
        try:
            await send_photo(ctx, st, IMAGES["ROMANTIC"],
                f"🔥 *Gece Ziyaretçin!*\n😈 {sapik.username} odana girdi...")
        except:
            pass

    # Yaramaz Kız bildirimi
    yk = next((p for p in game.players.values() if p.role == ROLES["YARAMAZ_KIZ"] and p.alive), None)
    yt = game.night_actions.get("yaramaz_kiz")
    if yk and yt and yt in game.players and game.players[yt].alive:
        try:
            await send_photo(ctx, yt, IMAGES["YARAMAZ_KIZ"],
                f"💃 *Sürpriz Ziyaret!*\n🔥 {yk.username} kapını çaldı...")
        except:
            pass

    # Gözcü bildirimi (handle_night_act içinde zaten yapılıyor, burada tekrar yok)

    # Ölümleri uygula
    for did in deaths:
        game.kill(did)

    if deaths:
        msg = "💀 *Gece Kurbanları:*\n" + "\n".join(f"• {game.players[d].username} ({game.players[d].role})" for d in deaths)
    else:
        msg = "🌙 Gece sakin geçti... Kimse ölmedi."

    await send_msg(ctx, game.group_id, msg)

    # Koruma başarılı mesajı
    successful = [pid for pid in protected if pid in game.night_actions.get("vampire", {}).values()]
    if successful:
        await send_msg(ctx, game.group_id, "🛡️ *Doktorlar birini vampir saldırısından kurtardı!*")

    if check_win(game):
        await end_game(ctx, game, app)
        return

    await asyncio.sleep(3)
    await start_day(ctx, game, app)


async def handle_night_act(query, uid, tid, ctx, game, app):
    p = game.players[uid]
    target = game.players[tid]

    # Takım arkadaşı kontrolü
    if p.role == target.role and "Doktor" not in p.role and "Vampir" not in p.role:
        return await query.answer("⚠️ Takım arkadaşına aksiyon uygulayamazsın!", show_alert=True)

    key = None
    for k, v in ROLES.items():
        if v == p.role:
            key = k
            break

    if key == "VAMPIR":
        if uid in game.night_actions["vampire"]:
            return await query.answer("⚠️ Zaten seçtin!", show_alert=True)
        game.night_actions["vampire"][uid] = tid
    elif key in ("DOKTOR", "DOKTOR_YARDIMCI"):
        if uid in game.night_actions.get("doctor", {}):
            return await query.answer("⚠️ Zaten seçtin!", show_alert=True)
        game.night_actions["doctor"][uid] = tid
    elif key == "KURT":
        if game.night_actions["kurt"]:
            return await query.answer("⚠️ Zaten seçtin!", show_alert=True)
        game.night_actions["kurt"] = tid
    elif key == "SAPIK":
        if game.night_actions["sapik"]:
            return await query.answer("⚠️ Zaten seçtin!", show_alert=True)
        game.night_actions["sapik"] = tid
    elif key == "YARAMAZ_KIZ":
        if game.night_actions["yaramaz_kiz"]:
            return await query.answer("⚠️ Zaten seçtin!", show_alert=True)
        game.night_actions["yaramaz_kiz"] = tid
    elif key == "GOZCU":
        if game.night_actions["gozcu"]:
            return await query.answer("⚠️ Zaten seçtin!", show_alert=True)
        game.night_actions["gozcu"] = tid
        await send_pm(app, uid, f"👁️ *Gözlem:* {target.username}\n🎭 Rolü: {target.role}")
    else:
        return await query.answer("❌ Oy kullanamazsın!", show_alert=True)

    await query.answer(f"✅ {target.username} seçildi!")


# ═══════════════════════════════════════════════════════════════
# GÜNDÜZ
# ═══════════════════════════════════════════════════════════════
async def start_day(ctx, game, app):
    game.phase = GamePhase.DAY
    game.votes = {}
    game.expected_voters = {p.user_id for p in game.get_alive()}
    await send_msg(ctx, game.group_id,
        "☀️ *GÜNDÜZ BAŞLADI!*\n\n"
        "😱 Köylüler uyandı!\n"
        "💀 Gece kurbanları var mı?\n"
        "🧛‍♂️ Tartışın ve oylayın!\n\n"
        "⏰ *Tartışma: 90 saniye*"
    )

    if game._timer_task and not game._timer_task.done():
        game._timer_task.cancel()
    game._timer_task = asyncio.create_task(day_discussion_timer(ctx, game, app))


async def day_discussion_timer(ctx, game, app):
    for remaining in range(90, 0, -1):
        if game.phase != GamePhase.DAY:
            return
        await asyncio.sleep(1)
        if remaining == 30:
            await send_msg(ctx, game.group_id, "⚠️ *30 saniye kaldı!*")
        elif remaining == 10:
            await send_msg(ctx, game.group_id, "🚨 *SON 10 SANİYE!*")

    await send_msg(ctx, game.group_id, "⏰ Tartışma bitti! Oylama başlıyor...")
    await start_voting(ctx, game, app)


async def start_voting(ctx, game, app):
    if not game.expected_voters:
        await send_msg(ctx, game.group_id, "❌ Oy verecek canlı oyuncu yok!")
        await end_day(ctx, game, app)
        return

    markup = build_buttons(game, gid=game.group_id, phase="day")
    if not markup:
        await send_msg(ctx, game.group_id, "❌ Oy verecek kimse yok!")
        await end_day(ctx, game, app)
        return

    try:
        msg = await ctx.bot.send_message(
            chat_id=game.group_id,
            text="🗳️ *OYLAMA BAŞLADI!*\n\n⚰️ Kimi linç edeceksiniz?\n⏰ *30 saniye*",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        game.vote_message_id = msg.message_id
    except Exception as e:
        logger.error(f"Oylama mesajı hatası: {e}")
        await end_day(ctx, game, app)
        return

    if game._timer_task and not game._timer_task.done():
        game._timer_task.cancel()
    game._timer_task = asyncio.create_task(voting_timer(ctx, game, app))


async def voting_timer(ctx, game, app):
    # 15 saniye uyarı
    await asyncio.sleep(15)
    if game.phase == GamePhase.DAY:
        await send_msg(ctx, game.group_id,
            f"⚠️ *15 saniye kaldı!*\n📊 {len(game.votes)}/{len(game.expected_voters)} oy")

    await asyncio.sleep(15)
    if game.phase == GamePhase.DAY:
        await send_msg(ctx, game.group_id, "⏰ Oylama bitti! Sonuçlar açıklanıyor...")
        await end_day(ctx, game, app)


async def end_day(ctx, game, app):
    # Butonları kapat
    if game.vote_message_id:
        try:
            await ctx.bot.edit_message_reply_markup(
                chat_id=game.group_id, message_id=game.vote_message_id, reply_markup=None
            )
        except:
            pass
        game.vote_message_id = None

    if game.phase != GamePhase.DAY:
        return

    if not game.votes:
        await send_msg(ctx, game.group_id, "❌ Kimse oy kullanmadı! Kimse ölmedi.")
    else:
        # Oy sayımı
        counts = {}
        for v in game.votes.values():
            counts[v] = counts.get(v, 0) + 1

        mx = max(counts.values())
        candidates = [u for u, c in counts.items() if c == mx]

        if len(candidates) > 1:
            names = [game.players[c].username for c in candidates]
            await send_msg(ctx, game.group_id,
                f"⚖️ *Beraberlik!*\n{', '.join(names)}\nKimse ölmedi.")
        else:
            tid = candidates[0]
            target = game.players[tid]

            # İblis kontrolü
            if target.role == ROLES["IBLIS"]:
                try:
                    await send_photo(ctx, game.group_id, IMAGES["IBLIS_WIN"],
                        f"👹 *İBLİS LİNÇ EDİLDİ!*\n⚡ Kötü takım kazandı!")
                except:
                    await send_msg(ctx, game.group_id,
                        f"👹 *İBLİS LİNÇ EDİLDİ!*\n⚡ Kötü takım kazandı!")
                await end_game(ctx, game, app, winner="evil")
                return

            game.kill(tid)
            await send_msg(ctx, game.group_id,
                f"⚰️ *Linç:* {target.username}\n🎭 Rolü: {target.role}\n📊 {mx} oy")

    if check_win(game):
        await end_game(ctx, game, app)
        return

    game.phase = GamePhase.PLAYING
    await asyncio.sleep(3)
    await send_msg(ctx, game.group_id,
        "🌙 *Yeni gece başlıyor...*\n👻 Kötü rüyalar görecek olanlar var!")
    await asyncio.sleep(2)
    await start_night(ctx, game, app)


async def handle_day_vote(query, uid, tid, ctx, game, app):
    """Gündüz oylama - DÜZELTİLDİ: app parametresi doğru geçiliyor"""
    if uid in game.votes:
        return await query.answer("⚠️ Zaten oy verdin!", show_alert=True)

    actual = tid

    # Şaşkın özelliği
    if game.players[uid].role == ROLES["SASKIN"] and random.random() < 0.5:
        others = [p for p in game.get_alive() if p.user_id != uid]
        if others:
            actual = random.choice(others).user_id
            await query.answer(f"🤪 Şaşkınlık! Oyun {game.players[actual].username}'e kaydı!")

    game.votes[uid] = actual
    target_name = game.players[tid].username
    await query.answer(f"🗳️ {target_name} için oy verdin!")

    # Oy duyurusu
    await send_msg(ctx, game.group_id,
        f"🗳️ [{game.players[uid].username}](tg://user?id={uid}) → "
        f"[{target_name}](tg://user?id={tid})")

    # Herkes oy verdi mi?
    if len(game.votes) >= len(game.expected_voters):
        if game._timer_task and not game._timer_task.done():
            game._timer_task.cancel()
        await end_day(ctx, game, app)  # ✅ DÜZELTİLDİ: ctx değil app


# ═══════════════════════════════════════════════════════════════
# OYUN AKIŞI
# ═══════════════════════════════════════════════════════════════
async def start_game(ctx, game, app):
    game.phase = GamePhase.PLAYING
    assign_roles(game)

    for p in game.players.values():
        msg = f"🎭 *Rolün: {p.role}*\n\n"
        if p.lakap and p.lakap != p.role:
            msg += f"🏷️ Lakap: {p.lakap}\n\n"

        if "Vampir" in p.role:
            mates = [x.username for x in game.players.values()
                    if "Vampir" in x.role and x.user_id != p.user_id]
            msg += f"🧛 Takım Arkadaşların: {', '.join(mates) if mates else 'Tek vampir sensin!'}\n"
            msg += "🌑 Gece birini ısır!\n⚠️ Takım arkadaşını seçemezsin!"
        elif "Doktor" in p.role:
            mates = [x.username for x in game.players.values()
                    if "Doktor" in x.role and x.user_id != p.user_id]
            if mates:
                msg += f"🩺 Doktor Takımın: {', '.join(mates)}\n"
            msg += "💉 Gece birini koru!"
        elif "Kurt" in p.role:
            msg += "🐺 Köylü takımındasın.\n⚔️ Sadece vampirleri avlayabilirsin!"
        elif p.role == ROLES["IBLIS"]:
            msg += "👹 Kötü takımdasın!\n⚡ Linç edilirsen kötüler kazanır!\n🔮 Gizlen ve linç edilmeyi bekle!"
        elif p.role == ROLES["GOZCU"]:
            msg += "👁️ Köylü takımındasın.\n🔍 Birinin rolünü öğrenebilirsin!"
        elif p.role == ROLES["SASKIN"]:
            msg += "🤪 Köylü takımındasın.\n🎲 Oylaman rastgele kayabilir!"
        elif p.role == ROLES["SAPIK"]:
            msg += "😈 Köylü takımındasın.\n🌙 Birini ziyaret edebilirsin!"
        elif p.role == ROLES["YARAMAZ_KIZ"]:
            msg += "🔥 Köylü takımındasın.\n🌙 Birine sürpriz yapabilirsin!"
        else:
            msg += "👨‍🌾 Köylüsün!\n☀️ Gündüz vampirleri bul!"

        if not await send_pm(app, p.user_id, msg):
            logger.warning(f"Rol mesajı gönderilemedi: {p.username}")

    await send_photo(ctx, game.group_id, IMAGES["START"],
        "🎬 *Oyun Başladı!*\n\n🎭 Roller özelden gönderildi.\n🌙 İlk gece başlıyor...")

    await asyncio.sleep(3)
    await start_night(ctx, game, app)


def check_win(game):
    alive = game.get_alive()
    vamps = [p for p in alive if "Vampir" in p.role]
    evil = [p for p in alive if "Vampir" in p.role or p.role == ROLES["IBLIS"]]
    villagers = [p for p in alive if p not in evil]

    if vamps and len(vamps) >= len(villagers):
        return True
    if not vamps:
        return True
    return False


async def end_game(ctx, game, app, winner=None):
    game.set_active(False)
    alive = game.get_alive()
    vamps = [p for p in alive if "Vampir" in p.role]

    if winner == "evil":
        txt, img = "👹 Kötü Takım", IMAGES["IBLIS_WIN"]
    elif vamps:
        txt, img = "🧛 Vampirler", IMAGES["VAMPIR_WIN"]
    else:
        txt, img = "👨‍🌾 Köylüler", IMAGES["KOYLU_WIN"]

    result = f"🏆 *{txt} KAZANDI!*\n\n📊 *Son Durum:*\n"
    for p in game.players.values():
        emoji = "❤️" if p.alive else "💀"
        result += f"{emoji} {p.username} - {p.role}\n"

    try:
        await send_photo(ctx, game.group_id, img, result)
    except:
        await send_msg(ctx, game.group_id, result)

    logger.info(f"Grup {game.group_id}: Oyun bitti - {txt}")

    await asyncio.sleep(5)
    game.reset()
    await send_msg(ctx, game.group_id, "🔄 *Oyun bitti!*\n🎮 Yeni oyun için /wstart yazın.")


async def join_countdown(ctx, game, app):
    while game.join_time_left > 0 and game.phase == GamePhase.LOBBY:
        await asyncio.sleep(1)
        game.join_time_left -= 1
        if game.join_time_left == 30:
            await send_msg(ctx, game.group_id, "⚠️ *30 saniye kaldı!*")
        elif game.join_time_left == 10:
            await send_msg(ctx, game.group_id, "🚨 *Son 10 saniye!*")

    if len(game.players) >= 5 and game.phase == GamePhase.LOBBY:
        await start_game(ctx, game, app)
    else:
        await send_msg(ctx, game.group_id, "❌ Yeterli oyuncu katılmadı! Oyun iptal edildi.")
        game.reset()

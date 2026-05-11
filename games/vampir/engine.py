# games/vampir/engine.py - PARA SİSTEMİ ENTEGRE EDİLDİ
import asyncio
import random
import logging
from typing import Dict, Set, Optional, Any
from dataclasses import dataclass
from enum import Enum

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from games.vampir.economy import GameEconomy, format_money

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
    "HIRSIZ": "🦝 Hırsız",
    "BEKCI": "🛡️ Gece Bekçisi",
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
            "hirsiz": None, "bekci": None,
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
        self.buy_in = 0  # 🆕 0 = ücretsiz oyun
        self.economy: Optional[GameEconomy] = None  # 🆕

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
            # 🆕 Ölen oyuncunun parası kasaya
            if self.economy and self.buy_in > 0:
                self.economy.player_died(uid)
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
    if not game.join_message_id: return
    try:
        buy_in_text = f"\n💰 Giriş: {game.buy_in:,} 🪙BTK" if game.buy_in > 0 else "\n🎮 Ücretsiz oyun"
        txt = "🎮 *Katılanlar:*\n"
        for i, p in enumerate(game.players.values(), 1):
            txt += f"{i}. {p.username}\n"
        txt += f"\n📊 {len(game.players)}/5 kişi{buy_in_text}"
        await ctx.bot.edit_message_text(
            chat_id=game.group_id, message_id=game.join_message_id,
            text=txt, reply_markup=join_btn(), parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Join update hatası: {e}")

def get_role_emoji(role: str) -> str:
    """Rol emojisini döndür"""
    if "Vampir" in role: return "🧛"
    if "Doktor" in role: return "🩺"
    if "Kurt" in role: return "🐺"
    if role == ROLES["SAPIK"]: return "😈"
    if role == ROLES["YARAMAZ_KIZ"]: return "🔥"
    if role == ROLES["IBLIS"]: return "👹"
    if role == ROLES["GOZCU"]: return "👁️"
    if role == ROLES["SASKIN"]: return "🤪"
    if role == ROLES["HIRSIZ"]: return "🦝"
    if role == ROLES["BEKCI"]: return "🛡️"
    return "👨‍🌾"

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
    has_thief = n >= 8 and game.buy_in > 0  # 🆕 Sadece paralı oyunda
    has_guard = n >= 8 and game.buy_in > 0  # 🆕 Sadece paralı oyunda

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
    if has_thief: roles.append(ROLES["HIRSIZ"])
    if has_guard: roles.append(ROLES["BEKCI"])

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
        "hirsiz": None, "bekci": None,
    }

    if game.economy:
        game.economy.night_count += 1

    alive = game.get_alive()
    vamps = [p for p in alive if "Vampir" in p.role]
    docs = [p for p in alive if "Doktor" in p.role]
    kurt = next((p for p in alive if "Kurt" in p.role), None)
    sapik = next((p for p in alive if p.role == ROLES["SAPIK"]), None)
    yk = next((p for p in alive if p.role == ROLES["YARAMAZ_KIZ"]), None)
    gozcu = next((p for p in alive if p.role == ROLES["GOZCU"]), None)
    hirsiz = next((p for p in alive if p.role == ROLES["HIRSIZ"]), None)
    bekci = next((p for p in alive if p.role == ROLES["BEKCI"]), None)

    game.expected_voters = {
        p.user_id for p in vamps + docs +
        ([kurt] if kurt else []) + ([sapik] if sapik else []) +
        ([yk] if yk else []) + ([gozcu] if gozcu else []) +
        ([hirsiz] if hirsiz else []) + ([bekci] if bekci else [])
    }

    # 🆕 Ekonomi bilgisi olan rol mesajları
    txt = {
        "VAMPIR": "🌑 *VAMPİR*\n🩸 Kimi ısıracaksın?\n⏰ 60 saniye",
        "DOKTOR": f"💉 *DOKTOR*\n⛑️ Kimi koruyacaksın?\n💰 Komisyon: %{int(DOKTOR_KOMISYON_ORAN*100)}\n⏰ 60 saniye",
        "DOKTOR_YARDIMCI": f"💉 *DOKTOR YARDIMCISI*\n⛑️ Kimi koruyacaksın?\n💰 Komisyon: %{int(DOKTOR_KOMISYON_ORAN*100)}\n⏰ 60 saniye",
        "KURT": f"🐺 *ALFA KURT*\n⚔️ Kimi avlayacaksın?\n🎯 Sadece vampirleri!\n💰 Vampir avı: Köy kasasından %{int(KURT_AV_ORAN*100)}\n⏰ 60 saniye",
        "SAPIK": f"😈 *SAPIK*\n🌙 Kimi ziyaret edeceksin?\n⚠️ Ziyarette %{int(SAPIK_KAYIP_ORAN*100)} kaybedersin\n⏰ 60 saniye",
        "YARAMAZ_KIZ": f"🔥 *YARAMAZ KIZ*\n🌙 Kime sürpriz?\n💰 Ziyaretten %{int(YARAMAZ_KIZ_KAZANC_ORAN*100)} alırsın\n⏰ 60 saniye",
        "GOZCU": "👁️ *GÖZCÜ*\n🔍 Kimi gözlemleyeceksin?\n⏰ 60 saniye",
        "HIRSIZ": f"🦝 *HIRSIZ*\n💰 Kimi soyacaksın?\n🎯 Hedefin %{int(HIRSIZ_CALMA_MIN*100)}-%{int(HIRSIZ_CALMA_MAX*100)}'i\n⏰ 60 saniye",
        "BEKCI": f"🛡️ *BEKÇİ*\n🔒 Kimi hırsızdan koruyacaksın?\n💰 Hırsızı yakalarsan %{int(BEKCI_YAKALAMA_ORAN*100)} ödül\n⏰ 60 saniye",
    }

    for p in alive:
        key = None
        for k, v in ROLES.items():
            if v == p.role:
                key = k
                break
        if key not in txt:
            continue

        # 🆕 Ekonomi bilgisi ekle
        extra = ""
        if game.economy and game.buy_in > 0:
            bal = game.economy.balances.get(p.user_id, 0)
            extra = f"\n\n💳 Oyun içi bakiyen: {format_money(bal)}"

        try:
            msg = await app.bot.send_message(
                chat_id=p.user_id, text=txt[key] + extra,
                reply_markup=build_buttons(game, gid=game.group_id, phase="night"),
                parse_mode="Markdown"
            )
            game.night_buttons[p.user_id] = msg.message_id
        except Exception as e:
            logger.error(f"Gece buton hatası {p.username}: {e}")

    # Grup mesajı
    extras = []
    if kurt: extras.append("🐺 Alfa Kurt avlanıyor")
    if sapik: extras.append("😈 Sapık hazırlanıyor")
    if yk: extras.append("🔥 Yaramaz Kız hazırlanıyor")
    if gozcu: extras.append("👁️ Gözcü gözlemliyor")
    if hirsiz: extras.append("🦝 Hırsız sinsi sinsi dolaşıyor")
    if bekci: extras.append("🛡️ Bekçi nöbette")

    treasury_info = ""
    if game.economy and game.buy_in > 0:
        treasury_info = f"\n\n🏦 Köy kasası: {format_money(game.economy.good_treasury)}"
        treasury_info += f"\n👹 Kötü kasası: {format_money(game.economy.evil_treasury)}"

    await send_msg(ctx, game.group_id,
        f"🌙 *GECE {game.economy.night_count if game.economy else ''} BAŞLADI!*\n\n"
        f"🧛‍♂️ Vampirler avlanıyor...\n"
        f"🩺 Doktorlar hazırlanıyor...\n" +
        "\n".join(extras) +
        f"\n\n⏰ *Karar süresi: 60 saniye*{treasury_info}"
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

    deaths = set()
    protected = set(game.night_actions.get("doctor", {}).values())

    # === BEKÇİ vs HIRSIZ ===
    hirsiz_id = next((uid for uid, p in game.players.items() if p.role == ROLES["HIRSIZ"] and p.alive), None)
    bekci_id = next((uid for uid, p in game.players.items() if p.role == ROLES["BEKCI"] and p.alive), None)
    
    bekci_target = game.night_actions.get("bekci")
    hirsiz_target = game.night_actions.get("hirsiz")

    if hirsiz_id and hirsiz_target and game.economy and game.buy_in > 0:
        if bekci_target == hirsiz_target:
            # Bekçi yakaladı!
            await send_pm(app, hirsiz_id, "🛡️ *Bekçi seni yakaladı!*\nKaçmak zorunda kaldın, soygun başarısız!")
            await send_pm(app, bekci_id, f"🦝 *Hırsızı yakaladın!*\n💰 Ödül: {format_money(game.economy._bekci_odulu())}")
            game.economy.bekci_hirsizi_yakaladi(bekci_id)
        else:
            # Hırsız başarılı
            amount = game.economy.hirsiz_caldi(hirsiz_id, hirsiz_target)
            target_name = game.players[hirsiz_target].username
            await send_pm(app, hirsiz_id, f"🦝 *Soygun Başarılı!*\n💰 {target_name}'den {format_money(amount)} çaldın!")
            await send_pm(app, hirsiz_target, f"🦝 *Soyuldun!*\n😱 Bir hırsız {format_money(amount)} çaldı!")

    # === Kurt ===
    kt = game.night_actions.get("kurt")
    if kt and kt in game.players and game.players[kt].alive:
        if "Vampir" in game.players[kt].role:
            deaths.add(kt)
            if game.economy and game.buy_in > 0:
                kurt_id = next((uid for uid, p in game.players.items() if p.role == ROLES["KURT"] and p.alive), None)
                if kurt_id:
                    amount = game.economy.kurt_vampir_avladı(kurt_id)
                    await send_pm(app, kurt_id, f"🐺 *Vampir Avladın!*\n💰 Köy kasasından {format_money(amount)} kazandın!")

    # === Vampir ===
    for vid, tid in game.night_actions.get("vampire", {}).items():
        if tid in game.players and game.players[tid].alive and tid not in protected:
            deaths.add(tid)

    # === Ekonomi işlemleri ===
    if game.economy and game.buy_in > 0:
        # İblis gece payı
        iblis = next((p for p in game.get_alive() if p.role == ROLES["IBLIS"]), None)
        if iblis:
            amount = game.economy.iblis_gece_payi(iblis.user_id)
            if amount > 0:
                await send_pm(app, iblis.user_id, f"👹 *İblis Gece Payı*\n💰 Kötü kasasından {format_money(amount)} aldın!")

        # Doktor komisyonları
        for doc_id, target_id in game.night_actions.get("doctor", {}).items():
            if target_id in game.players and game.players[target_id].alive:
                amount = game.economy.doktor_korudu(doc_id, target_id)
                if amount > 0:
                    await send_pm(app, doc_id, f"🩺 *Doktor Komisyonu*\n💰 {game.players[target_id].username}'den {format_money(amount)} aldın!")
                    await send_pm(app, target_id, f"🩺 *Doktor Komisyonu*\n💸 {game.players[doc_id].username}'e {format_money(amount)} ödedin!")

        # Sapık
        sapik_id = next((uid for uid, p in game.players.items() if p.role == ROLES["SAPIK"] and p.alive), None)
        st = game.night_actions.get("sapik")
        if sapik_id and st and st in game.players and game.players[st].alive:
            amount = game.economy.sapik_ziyaret(sapik_id, st)
            if amount > 0:
                await send_pm(app, sapik_id, f"😈 *Ziyaret*\n💸 {game.players[st].username}'e {format_money(amount)} kaybettin!")
                await send_pm(app, st, f"😈 *Ziyaretçi*\n💰 Sapık sana {format_money(amount)} bıraktı!")
            try:
                await send_photo(ctx, st, IMAGES["ROMANTIC"],
                    f"🔥 *Gece Ziyaretçin!*\n😈 {game.players[sapik_id].username} odana girdi...")
            except:
                pass

        # Yaramaz Kız
        yk_id = next((uid for uid, p in game.players.items() if p.role == ROLES["YARAMAZ_KIZ"] and p.alive), None)
        yt = game.night_actions.get("yaramaz_kiz")
        if yk_id and yt and yt in game.players and game.players[yt].alive:
            amount = game.economy.yaramaz_kiz_ziyaret(yk_id, yt)
            if amount > 0:
                await send_pm(app, yk_id, f"🔥 *Sürpriz*\n💰 {game.players[yt].username}'den {format_money(amount)} aldın!")
                await send_pm(app, yt, f"🔥 *Sürpriz*\n💸 Yaramaz Kız'a {format_money(amount)} kaptırdın!")
            try:
                await send_photo(ctx, yt, IMAGES["YARAMAZ_KIZ"],
                    f"💃 *Sürpriz Ziyaret!*\n🔥 {game.players[yk_id].username} kapını çaldı...")
            except:
                pass

    # === Ölümleri uygula ===
    for did in deaths:
        game.kill(did)  # economy.player_died burada tetiklenir

    if deaths:
        msg = "💀 *Gece Kurbanları:*\n" + "\n".join(f"• {game.players[d].username} ({game.players[d].role})" for d in deaths)
    else:
        msg = "🌙 Gece sakin geçti... Kimse ölmedi."

    await send_msg(ctx, game.group_id, msg)

    if check_win(game):
        await end_game(ctx, game, app)
        return

    await asyncio.sleep(3)
    await start_day(ctx, game, app)


async def handle_night_act(query, uid, tid, ctx, game, app):
    p = game.players[uid]
    target = game.players[tid]

    if p.role == target.role and "Doktor" not in p.role and "Vampir" not in p.role and "BEKCI" not in p.role:
        return await query.answer("⚠️ Takım arkadaşına aksiyon uygulayamazsın!", show_alert=True)

    key = None
    for k, v in ROLES.items():
        if v == p.role:
            key = k
            break

    if key == "VAMPIR":
        if uid in game.night_actions["vampire"]: return await query.answer("⚠️ Zaten seçtin!", show_alert=True)
        game.night_actions["vampire"][uid] = tid
    elif key in ("DOKTOR", "DOKTOR_YARDIMCI"):
        if uid in game.night_actions.get("doctor", {}): return await query.answer("⚠️ Zaten seçtin!", show_alert=True)
        game.night_actions["doctor"][uid] = tid
    elif key == "KURT":
        if game.night_actions["kurt"]: return await query.answer("⚠️ Zaten seçtin!", show_alert=True)
        game.night_actions["kurt"] = tid
    elif key == "SAPIK":
        if game.night_actions["sapik"]: return await query.answer("⚠️ Zaten seçtin!", show_alert=True)
        game.night_actions["sapik"] = tid
    elif key == "YARAMAZ_KIZ":
        if game.night_actions["yaramaz_kiz"]: return await query.answer("⚠️ Zaten seçtin!", show_alert=True)
        game.night_actions["yaramaz_kiz"] = tid
    elif key == "GOZCU":
        if game.night_actions["gozcu"]: return await query.answer("⚠️ Zaten seçtin!", show_alert=True)
        game.night_actions["gozcu"] = tid
        await send_pm(app, uid, f"👁️ *Gözlem:* {target.username}\n🎭 Rolü: {target.role}")
    elif key == "HIRSIZ":
        if game.night_actions["hirsiz"]: return await query.answer("⚠️ Zaten seçtin!", show_alert=True)
        game.night_actions["hirsiz"] = tid
    elif key == "BEKCI":
        if game.night_actions["bekci"]: return await query.answer("⚠️ Zaten seçtin!", show_alert=True)
        game.night_actions["bekci"] = tid
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

    treasury_info = ""
    if game.economy and game.buy_in > 0:
        treasury_info = f"\n\n🏦 Köy kasası: {format_money(game.economy.good_treasury)}"
        treasury_info += f"\n👹 Kötü kasası: {format_money(game.economy.evil_treasury)}"

    await send_msg(ctx, game.group_id,
        f"☀️ *GÜNDÜZ BAŞLADI!*\n\n"
        f"😱 Köylüler uyandı!\n"
        f"💀 Gece kurbanları var mı?\n"
        f"🧛‍♂️ Tartışın ve oylayın!\n\n"
        f"⏰ *Tartışma: 90 saniye*{treasury_info}"
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

    msg = await ctx.bot.send_message(
        chat_id=game.group_id,
        text="🗳️ *OYLAMA BAŞLADI!*\n\n⚰️ Kimi linç edeceksiniz?\n⏰ *30 saniye*",
        reply_markup=markup, parse_mode="Markdown"
    )
    game.vote_message_id = msg.message_id

    if game._timer_task and not game._timer_task.done():
        game._timer_task.cancel()
    game._timer_task = asyncio.create_task(voting_timer(ctx, game, app))


async def voting_timer(ctx, game, app):
    await asyncio.sleep(15)
    if game.phase == GamePhase.DAY:
        await send_msg(ctx, game.group_id,
            f"⚠️ *15 saniye kaldı!*\n📊 {len(game.votes)}/{len(game.expected_voters)} oy")

    await asyncio.sleep(15)
    if game.phase == GamePhase.DAY:
        await send_msg(ctx, game.group_id, "⏰ Oylama bitti!")
        await end_day(ctx, game, app)


async def end_day(ctx, game, app):
    if game.vote_message_id:
        try:
            await ctx.bot.edit_message_reply_markup(
                chat_id=game.group_id, message_id=game.vote_message_id, reply_markup=None
            )
        except: pass
        game.vote_message_id = None

    if game.phase != GamePhase.DAY: return

    if not game.votes:
        await send_msg(ctx, game.group_id, "❌ Kimse oy kullanmadı! Kimse ölmedi.")
    else:
        counts = {}
        for v in game.votes.values(): counts[v] = counts.get(v, 0) + 1
        mx = max(counts.values())
        candidates = [u for u, c in counts.items() if c == mx]

        if len(candidates) > 1:
            names = [game.players[c].username for c in candidates]
            await send_msg(ctx, game.group_id, f"⚖️ *Beraberlik!*\n{', '.join(names)}\nKimse ölmedi.")
        else:
            tid = candidates[0]
            target = game.players[tid]

            if target.role == ROLES["IBLIS"]:
                try:
                    await send_photo(ctx, game.group_id, IMAGES["IBLIS_WIN"],
                        f"👹 *İBLİS LİNÇ EDİLDİ!*\n⚡ Kötü takım kazandı!")
                except:
                    await send_msg(ctx, game.group_id, f"👹 *İBLİS LİNÇ EDİLDİ!*\n⚡ Kötü takım kazandı!")
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
    await send_msg(ctx, game.group_id, "🌙 *Yeni gece başlıyor...*")
    await asyncio.sleep(2)
    await start_night(ctx, game, app)


async def handle_day_vote(query, uid, tid, ctx, game, app):
    if uid in game.votes: return await query.answer("⚠️ Zaten oy verdin!", show_alert=True)
    actual = tid
    if game.players[uid].role == ROLES["SASKIN"] and random.random() < 0.5:
        others = [p for p in game.get_alive() if p.user_id != uid]
        if others:
            actual = random.choice(others).user_id
            await query.answer(f"🤪 Şaşkınlık! Oyun kaydı!")

    game.votes[uid] = actual
    await query.answer(f"🗳️ {game.players[tid].username} için oy verdin!")
    await send_msg(ctx, game.group_id,
        f"🗳️ [{game.players[uid].username}](tg://user?id={uid}) → "
        f"[{game.players[tid].username}](tg://user?id={tid})")

    if len(game.votes) >= len(game.expected_voters):
        if game._timer_task and not game._timer_task.done():
            game._timer_task.cancel()
        await end_day(ctx, game, app)


# ═══════════════════════════════════════════════════════════════
# OYUN AKIŞI
# ═══════════════════════════════════════════════════════════════
async def start_game(ctx, game, app):
    game.phase = GamePhase.PLAYING
    assign_roles(game)

    # 🆕 Ekonomi başlat
    if game.buy_in > 0:
        game.economy = GameEconomy(game.buy_in, game.players)
        game.economy.set_teams(game.players)

    # Rol mesajları
    for p in game.players.values():
        msg = f"🎭 *Rolün: {p.role}*\n\n"

        if p.lakap and p.lakap != p.role:
            msg += f"🏷️ Lakap: {p.lakap}\n\n"

        if "Vampir" in p.role:
            mates = [x.username for x in game.players.values() if "Vampir" in x.role and x.user_id != p.user_id]
            msg += f"🧛 Takım Arkadaşların: {', '.join(mates) if mates else 'Tek vampir sensin!'}\n"
            msg += "🌑 Gece birini ısır!\n⚠️ Takım arkadaşını seçemezsin!"
        elif "Doktor" in p.role:
            mates = [x.username for x in game.players.values() if "Doktor" in x.role and x.user_id != p.user_id]
            if mates: msg += f"🩺 Doktor Takımın: {', '.join(mates)}\n"
            msg += "💉 Gece birini koru!"
            if game.buy_in > 0:
                msg += f"\n💰 Koruma komisyonu: %{int(DOKTOR_KOMISYON_ORAN*100)}"
        elif "Kurt" in p.role:
            msg += "🐺 Köylü takımındasın.\n⚔️ Sadece vampirleri avlayabilirsin!"
            if game.buy_in > 0:
                msg += f"\n💰 Vampir avı: Köy kasasından %{int(KURT_AV_ORAN*100)}"
        elif p.role == ROLES["IBLIS"]:
            msg += "👹 Kötü takımdasın!\n⚡ Linç edilirsen kötüler kazanır!"
            if game.buy_in > 0:
                msg += f"\n💰 Her gece kötü kasadan %{int(IBLIS_HAVUZ_ORAN*100)} alırsın!"
        elif p.role == ROLES["GOZCU"]:
            msg += "👁️ Köylü takımındasın.\n🔍 Birinin rolünü öğrenebilirsin!"
        elif p.role == ROLES["SASKIN"]:
            msg += "🤪 Köylü takımındasın.\n🎲 Oylaman rastgele kayabilir!"
        elif p.role == ROLES["SAPIK"]:
            msg += "😈 Köylü takımındasın.\n🌙 Birini ziyaret edebilirsin!"
            if game.buy_in > 0:
                msg += f"\n⚠️ Ziyarette %{int(SAPIK_KAYIP_ORAN*100)} kaybedersin!"
        elif p.role == ROLES["YARAMAZ_KIZ"]:
            msg += "🔥 Köylü takımındasın.\n🌙 Birine sürpriz yapabilirsin!"
            if game.buy_in > 0:
                msg += f"\n💰 Ziyaretten %{int(YARAMAZ_KIZ_KAZANC_ORAN*100)} alırsın!"
        elif p.role == ROLES["HIRSIZ"]:
            msg += f"🦝 Köylü takımındasın.\n💰 Gece birinin %{int(HIRSIZ_CALMA_MIN*100)}-%{int(HIRSIZ_CALMA_MAX*100)}'ini çal!"
            msg += "\n⚠️ Bekçi seni yakalayabilir!"
        elif p.role == ROLES["BEKCI"]:
            msg += "🛡️ Köylü takımındasın.\n🔒 Birini hırsızdan koru!"
            if game.buy_in > 0:
                msg += f"\n💰 Hırsızı yakalarsan %{int(BEKCI_YAKALAMA_ORAN*100)} ödül!"
        else:
            msg += "👨‍🌾 Köylüsün!\n☀️ Gündüz vampirleri bul!"

        if game.buy_in > 0:
            msg += f"\n\n💳 Oyun içi bakiyen: {format_money(game.buy_in)}"
            msg += f"\n🏦 Köy kasası: {format_money(game.economy.good_treasury)}"
            msg += f"\n👹 Kötü kasası: {format_money(game.economy.evil_treasury)}"

        if not await send_pm(app, p.user_id, msg):
            logger.warning(f"Rol mesajı gönderilemedi: {p.username}")

    start_text = "🎬 *Oyun Başladı!*\n\n🎭 Roller özelden gönderildi.\n🌙 İlk gece başlıyor..."
    if game.buy_in > 0:
        start_text += f"\n\n💰 Giriş: {format_money(game.buy_in)}"
        start_text += f"\n🏦 Toplam havuz: {format_money(game.economy.good_treasury + game.economy.evil_treasury)}"

    await send_photo(ctx, game.group_id, IMAGES["START"], start_text)
    await asyncio.sleep(3)
    await start_night(ctx, game, app)


def check_win(game):
    alive = game.get_alive()
    vamps = [p for p in alive if "Vampir" in p.role]
    evil = [p for p in alive if "Vampir" in p.role or p.role == ROLES["IBLIS"]]
    villagers = [p for p in alive if p not in evil]
    if vamps and len(vamps) >= len(villagers): return True
    if not vamps: return True
    return False


async def end_game(ctx, game, app, winner=None):
    game.set_active(False)
    alive = game.get_alive()
    vamps = [p for p in alive if "Vampir" in p.role]

    if winner == "evil":
        winner_text, winner_emoji, image = "👹 Kötü Takım", "👹", IMAGES["IBLIS_WIN"]
        winning_team = "evil"
    elif vamps:
        winner_text, winner_emoji, image = "🧛‍♂️ Vampirler", "🧛‍♂️", IMAGES["VAMPIR_WIN"]
        winning_team = "evil"
    else:
        winner_text, winner_emoji, image = "👨‍🌾 Köylüler", "👨‍🌾", IMAGES["KOYLU_WIN"]
        winning_team = "villagers"

    # 🆕 Ekonomi - oyun sonu hesaplama
rewards = {}
if game.economy and game.buy_in > 0:
    # Kazanan takım üyelerini belirle
    if winning_team == "evil":
        winning_ids = [uid for uid, p in game.players.items()
                      if "Vampir" in p.role or p.role == ROLES["IBLIS"]]
    else:
        winning_ids = [uid for uid, p in game.players.items()
                      if "Vampir" not in p.role and p.role != ROLES["IBLIS"]]
    
    rewards = game.economy.get_final_rewards(winning_ids)
        # Gerçek bakiyeye ekle
        try:
            from core.economy import add_balance
            from core.users import get_or_create_user
            for uid, amount in rewards.items():
                if amount > 0:
                    await get_or_create_user(uid, game.players[uid].username, game.players[uid].username)
                    net = amount - game.buy_in
                    desc = "Vampir Köylü kazancı" if net >= 0 else "Vampir Köylü kaybı"
                    await add_balance(uid, amount, "vampir_win", desc)
        except Exception as e:
            logger.error(f"Gerçek bakiyeye ekleme hatası: {e}")

    # Orijinal sonuç mesajı
    results_text = f"🏆 {winner_emoji} *{winner_text} KAZANDI!* {winner_emoji} 🏆\n\n"
    results_text += "📊 *OYUN SONU DURUMU:*\n\n"

    for player in game.players.values():
        status_emoji = "❤️" if player.alive else "💀"
        role_emoji = get_role_emoji(player.role)

        player_team = "evil" if ("Vampir" in player.role or player.role == ROLES["IBLIS"]) else "villagers"
        if "Kurt" in player.role: player_team = "villagers"

        results_text += f"{status_emoji} {player.username} - {role_emoji} {player.role}\n"

        # 🆕 Para satırı
        if rewards and player.user_id in rewards:
            net = rewards[player.user_id] - game.buy_in
            money_str = format_money(net)
            result_icon = "✅" if player_team == winning_team else "❌"
            results_text += f"     {money_str} {result_icon}\n"
        else:
            result_icon = "✅" if player_team == winning_team else "❌"
            results_text += f"     {result_icon}\n"
        results_text += "\n"

    total_players = len(game.players)
    alive_count = len(alive)
    dead_count = total_players - alive_count

    results_text += f"🎯 *Kazanan:* {winner_text}\n"
    results_text += f"👥 Oyuncu: {total_players} | ❤️ {alive_count} | 💀 {dead_count}\n"

    if game.economy and game.buy_in > 0:
        results_text += f"🏦 Havuz: {format_money(game.economy.good_treasury + game.economy.evil_treasury)}\n"

    if winning_team == "villagers":
        results_text += f"\n⭐ *Kazanan Köylü Takımı:*"
        results_text += f"\n• 👨‍🌾 • 🩺 • 🐺 • 😈 • 🔥 • 👁️ • 🤪"
        if game.buy_in > 0:
            results_text += f"\n• 🦝 • 🛡️"
    else:
        results_text += f"\n⭐ *Kazanan Kötü Takım:*"
        results_text += f"\n• 🧛‍♂️ Vampirler • 👹 İblis"

    try:
        await send_photo(ctx, game.group_id, image, results_text)
    except:
        await send_msg(ctx, game.group_id, results_text)

    # 🆕 Her oyuncuya özel hesap özeti
    if rewards:
        for player in game.players.values():
            if player.user_id in rewards:
                net = rewards[player.user_id] - game.buy_in
                player_team = "evil" if ("Vampir" in player.role or player.role == ROLES["IBLIS"]) else "villagers"
                won = player_team == winning_team

                summary = f"🏆 *Oyun Bitti - {winner_text} Kazandı!*\n\n"
                summary += f"🎭 Rolün: {player.role}\n"
                summary += f"💳 Giriş: {format_money(game.buy_in)}\n"
                summary += f"💰 Çıkış: {format_money(rewards[player.user_id])}\n"
                summary += f"📊 Net: {format_money(net)} {'✅' if won else '❌'}\n\n"
                summary += "💳 /balance ile gerçek bakiyeni kontrol et"

                await send_pm(app, player.user_id, summary)

    logger.info(f"Grup {game.group_id}: 🏆 Oyun bitti! Kazanan: {winner_text}")

    await asyncio.sleep(5)
    game.reset()
    await send_msg(ctx, game.group_id, "🔄 *Oyun bitti!*\n🎮 Yeni oyun için /wstart\n⭐ *Beğendiniz mi? Botu arkadaşlarınızla paylaşın!*")


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

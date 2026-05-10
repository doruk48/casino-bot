# games/vampir/roles.py - Rol atama ve takım bildirimleri
import random
import logging
from games.vampir.config import ROLES, KOYLU_LAKAPLARI
from games.vampir.utils import safe_send_pm

logger = logging.getLogger(__name__)

def assign_roles(game):
    """Rolleri dağıt ve takım arkadaşlarını bildir"""
    alive_players = list(game.players.values())
    random.shuffle(alive_players)

    player_count = len(alive_players)

    # Vampir sayısı
    if player_count <= 6:
        vampire_count = 1
    elif player_count <= 10:
        vampire_count = 2
    else:
        vampire_count = 3

    # Doktor sayısı
    doctor_count = 2 if player_count >= 8 else 1

    has_special_roles = player_count >= 8
    has_kurt = player_count >= 10
    has_new_roles = player_count >= 10

    roles_to_assign = []

    # Vampirler
    for _ in range(vampire_count):
        roles_to_assign.append(ROLES["VAMPIR"])

    # Doktorlar
    for i in range(doctor_count):
        if i == 0:
            roles_to_assign.append(ROLES["DOKTOR"])
        else:
            roles_to_assign.append("🩺 Doktor Yardımcısı")

    # Alfa Kurt
    if has_kurt:
        roles_to_assign.append(ROLES["KURT"])

    # Özel roller (Sapık/Yaramaz Kız)
    if has_special_roles:
        special_roles = [ROLES["SAPIK"], ROLES["YARAMAZ_KIZ"]]
        roles_to_assign.append(random.choice(special_roles))

    # Yeni roller (Gözcü/Şaşkın)
    if has_new_roles:
        new_roles = [ROLES["GOZCU"], ROLES["SASKIN"]]
        num_new = random.randint(1, min(2, len(new_roles)))
        roles_to_assign.extend(random.sample(new_roles, num_new))

    # İblis
    if player_count >= 10 and random.choice([True, False]):
        roles_to_assign.append(ROLES["IBLIS"])

    # Köylüler
    koylu_count = player_count - len(roles_to_assign)
    koylu_lakaplari = random.sample(KOYLU_LAKAPLARI, min(koylu_count, len(KOYLU_LAKAPLARI)))

    for i in range(koylu_count):
        if i < len(koylu_lakaplari):
            roles_to_assign.append(koylu_lakaplari[i])
        else:
            roles_to_assign.append(ROLES["KOYLU"])

    # Rolleri karıştır ve dağıt
    random.shuffle(roles_to_assign)
    for player, role in zip(alive_players, roles_to_assign):
        player.role = role
        if role in KOYLU_LAKAPLARI or role == ROLES["KOYLU"]:
            player.lakap = role

    notify_teammates(game)

def notify_teammates(game):
    """Takım arkadaşlarını özel mesajla bildir"""
    # Vampir takımı
    vampires = [p for p in game.players.values() if "Vampir" in p.role]
    for vampire in vampires:
        teammates = [p for p in vampires if p.user_id != vampire.user_id]
        if teammates:
            names = [f"@{p.username}" if p.username else p.username for p in teammates]
            try:
                safe_send_pm(
                    None,  # app globale koyulacak
                    vampire.user_id,
                    f"🧛 *Takım Arkadaşların:* {', '.join(names)}\n\n"
                    f"🌑 Birlikte avlanın, taktik yapın!\n"
                    f"⚠️ Takım arkadaşınıza saldıramazsınız.",
                )
            except:
                pass

    # Doktor takımı
    doctors = [p for p in game.players.values() if "Doktor" in p.role]
    for doctor in doctors:
        teammates = [p for p in doctors if p.user_id != doctor.user_id]
        if teammates:
            names = [f"@{p.username}" if p.username else p.username for p in teammates]
            try:
                safe_send_pm(
                    None,
                    doctor.user_id,
                    f"🩺 *Doktor Takım Arkadaşların:* {', '.join(names)}\n\n"
                    f"💉 Birlikte koruma yapabilirsiniz!\n"
                    f"👥 Hepiniz köylü takımındasınız!",
                )
            except:
                pass

    # İblis
    iblis = next((p for p in game.players.values() if p.role == ROLES["IBLIS"]), None)
    if iblis:
        try:
            safe_send_pm(
                None,
                iblis.user_id,
                f"👹 *Özel Bilgi:*\n\n"
                f"🎯 Vampirlerle aynı takımdasın!\n"
                f"⚡ Linç edilirsen kötü takım kazanır!\n"
                f"🔮 Gizlen ve linç edilmeyi bekle!",
            )
        except:
            pass

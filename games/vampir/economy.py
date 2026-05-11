# games/vampir/economy.py - Oyun İçi Ekonomi (HATASIZ)
import random
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# ORANSAL SABİTLER (giriş ücretine göre hesaplanır)
# ═══════════════════════════════════════════════════════════════
DOKTOR_KOMISYON_ORAN = 0.10
SAPIK_KAYIP_ORAN = 0.10
YARAMAZ_KIZ_KAZANC_ORAN = 0.10
IBLIS_HAVUZ_ORAN = 0.05
KURT_AV_ORAN = 0.10
HIRSIZ_CALMA_MIN = 0.10
HIRSIZ_CALMA_MAX = 0.20
BEKCI_YAKALAMA_ORAN = 0.05

# ═══════════════════════════════════════════════════════════════
# PARA FORMATLAMA
# ═══════════════════════════════════════════════════════════════
def format_money(amount: int) -> str:
    """+4.90M 🪙BTK, -150K 🪙BTK"""
    if amount == 0:
        return "0 🪙BTK"
    
    sign = "+" if amount > 0 else ""
    abs_amt = abs(amount)
    
    if abs_amt >= 1_000_000:
        return f"{sign}{abs_amt/1_000_000:.2f}M 🪙BTK"
    elif abs_amt >= 1_000:
        return f"{sign}{abs_amt/1_000:.0f}K 🪙BTK"
    else:
        return f"{sign}{abs_amt} 🪙BTK"


# ═══════════════════════════════════════════════════════════════
# ANA EKONOMİ SINIFI
# ═══════════════════════════════════════════════════════════════
class GameEconomy:
    def __init__(self, buy_in: int, players: dict):
        self.buy_in = buy_in
        self.players = players
        self.night_count = 0
        self.thief_stolen_total = 0
        
        # Her oyuncunun oyun içi cep bakiyesi
        self.balances: Dict[int, int] = {uid: buy_in for uid in players}
        
        # Oyuncu takımları (assign_roles sonrası doldurulacak)
        self.teams: Dict[int, str] = {}  # "good" veya "evil"
        
        # İKİ KASA (oyun tarafından yaratılır)
        n = len(players)
        self.good_treasury = buy_in * n   # Köy kasası
        self.evil_treasury = buy_in * n   # Kötü kasası
    
    # ═══════════════════════════════════════════════════════════
    # TAKIM YÖNETİMİ
    # ═══════════════════════════════════════════════════════════
    def set_teams(self, players_dict: dict):
        """Rollere göre takımları belirle"""
        from games.vampir.config import ROLES
        for uid, player in players_dict.items():
            if "Vampir" in player.role or player.role == ROLES.get("IBLIS", "👹 İblis"):
                self.teams[uid] = "evil"
            else:
                self.teams[uid] = "good"
    
    def get_team(self, uid: int) -> str:
        return self.teams.get(uid, "good")
    
    # ═══════════════════════════════════════════════════════════
    # HESAPLAMALAR
    # ═══════════════════════════════════════════════════════════
    def _doktor_komisyon(self) -> int:
        return int(self.buy_in * DOKTOR_KOMISYON_ORAN)
    
    def _sapik_kayip(self) -> int:
        return int(self.buy_in * SAPIK_KAYIP_ORAN)
    
    def _yaramaz_kazanc(self) -> int:
        return int(self.buy_in * YARAMAZ_KIZ_KAZANC_ORAN)
    
    def _iblis_payi(self) -> int:
        return int(self.evil_treasury * IBLIS_HAVUZ_ORAN)
    
    def _kurt_payi(self) -> int:
        return int(self.good_treasury * KURT_AV_ORAN)
    
    def _bekci_odulu(self) -> int:
        return int(self.buy_in * BEKCI_YAKALAMA_ORAN)
    
    # ═══════════════════════════════════════════════════════════
    # TRANSFER İŞLEMLERİ
    # ═══════════════════════════════════════════════════════════
    def _transfer_p2p(self, from_id: int, to_id: int, amount: int, reason: str) -> int:
        """Oyuncudan oyuncuya transfer (bakiyesi kadar)"""
        if amount <= 0:
            return 0
        if from_id not in self.balances or to_id not in self.balances:
            return 0
        
        actual = min(amount, self.balances[from_id])
        if actual <= 0:
            return 0
        
        self.balances[from_id] -= actual
        self.balances[to_id] += actual
        logger.info(f"💸 {from_id} → {to_id} | {actual:,} BTK | {reason}")
        return actual
    
    def _transfer_treasury_to_player(self, player_id: int, amount: int, treasury: str, reason: str) -> int:
        """Kasadan oyuncuya"""
        if amount <= 0 or player_id not in self.balances:
            return 0
        
        if treasury == "evil":
            actual = min(amount, self.evil_treasury)
            self.evil_treasury -= actual
        else:
            actual = min(amount, self.good_treasury)
            self.good_treasury -= actual
        
        self.balances[player_id] += actual
        logger.info(f"🏦 {treasury} kasa → {player_id} | {actual:,} BTK | {reason}")
        return actual
    
    # ═══════════════════════════════════════════════════════════
    # ROL İŞLEMLERİ
    # ═══════════════════════════════════════════════════════════
    def doktor_korudu(self, doktor_id: int, hasta_id: int) -> int:
        """Doktor koruma komisyonu - hastanın cebinden"""
        amount = self._doktor_komisyon()
        return self._transfer_p2p(hasta_id, doktor_id, amount, "doktor_komisyon")
    
    def sapik_ziyaret(self, sapik_id: int, ev_id: int) -> int:
        """Sapık ziyareti - sapığın cebinden ev sahibine"""
        amount = self._sapik_kayip()
        return self._transfer_p2p(sapik_id, ev_id, amount, "sapik_kayip")
    
    def yaramaz_kiz_ziyaret(self, yk_id: int, ev_id: int) -> int:
        """Yaramaz Kız ziyareti - ev sahibinin cebinden"""
        amount = self._yaramaz_kazanc()
        return self._transfer_p2p(ev_id, yk_id, amount, "yaramaz_kiz_kazanc")
    
    def iblis_gece_payi(self, iblis_id: int) -> int:
        """İblis her gece kötü kasadan pay alır"""
        amount = self._iblis_payi()
        return self._transfer_treasury_to_player(iblis_id, amount, "evil", "iblis_gece_payi")
    
    def kurt_vampir_avladı(self, kurt_id: int) -> int:
        """Kurt vampir avlarsa köy kasasından pay"""
        amount = self._kurt_payi()
        return self._transfer_treasury_to_player(kurt_id, amount, "good", "kurt_vampir_av")
    
    def hirsiz_caldi(self, hirsiz_id: int, hedef_id: int) -> int:
        """Hırsız soygun - hedefin cebinden %10-20"""
        if hedef_id not in self.balances:
            return 0
        
        oran = random.uniform(HIRSIZ_CALMA_MIN, HIRSIZ_CALMA_MAX)
        amount = int(self.balances[hedef_id] * oran)
        result = self._transfer_p2p(hedef_id, hirsiz_id, amount, "hirsiz_caldi")
        self.thief_stolen_total += result
        return result
    
    def bekci_hirsizi_yakaladi(self, bekci_id: int) -> int:
        """Bekçi hırsızı yakalarsa köy kasasından ödül"""
        amount = self._bekci_odulu()
        return self._transfer_treasury_to_player(bekci_id, amount, "good", "bekci_yakalama")
    
    # ═══════════════════════════════════════════════════════════
    # ÖLÜM İŞLEMLERİ
    # ═══════════════════════════════════════════════════════════
    def player_died(self, user_id: int):
        """Ölen oyuncunun cebi takımının kasasına"""
        if user_id not in self.balances:
            return 0
        
        amount = self.balances[user_id]
        if amount <= 0:
            return 0
        
        self.balances[user_id] = 0
        
        if self.get_team(user_id) == "evil":
            self.evil_treasury += amount
        else:
            self.good_treasury += amount
        
        logger.info(f"💀 {user_id} öldü | {amount:,} BTK → {self.get_team(user_id)} kasası")
        return amount
    
    # ═══════════════════════════════════════════════════════════
    # OYUN SONU
    # ═══════════════════════════════════════════════════════════
    def get_final_rewards(self, winning_team_ids: list[int]) -> Dict[int, int]:
        """Oyun sonu kazançları hesapla"""
        # Toplam havuz = iki kasanın toplamı
        total_pool = self.good_treasury + self.evil_treasury
        
        # Kazananları belirle
        winners = [uid for uid in winning_team_ids if uid in self.balances]
        alive_winners = [uid for uid in winners if self.players[uid].alive]
        
        if not winners:
            return {uid: self.balances.get(uid, 0) for uid in self.players}
        
        # %60 eşit dağıtım
        equal_part = int(total_pool * 0.6)
        equal_share = equal_part // len(winners) if winners else 0
        
        # %40 canlı bonusu
        alive_part = int(total_pool * 0.4)
        alive_share = alive_part // len(alive_winners) if alive_winners else 0
        
        # Kalan varsa ilk kazanana ekle
        distributed = (equal_share * len(winners)) + (alive_share * len(alive_winners))
        remainder = total_pool - distributed
        
        rewards = {}
        for uid in self.players:
            base = self.balances.get(uid, 0)
            if uid in winners:
                base += equal_share
                if uid in alive_winners:
                    base += alive_share
            rewards[uid] = base
        
        if winners and remainder > 0:
            rewards[winners[0]] += remainder
        
        logger.info(f"🏆 Oyun sonu | Havuz: {total_pool:,} | Kazanan: {len(winners)}")
        return rewards
    
    def get_net(self, user_id: int, rewards: dict) -> int:
        """Net kazanç (oyun sonu - giriş ücreti)"""
        final = rewards.get(user_id, 0)
        return final - self.buy_in

# utils/format.py - Sayı Formatlama
import logging
from config import CURRENCY_SYMBOL, LOG_FILE

# Logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

def format_amount(amount) -> str:
    """Büyük sayıları formatla - Decimal128, Decimal veya int kabul eder"""
    from bson.decimal128 import Decimal128
    from decimal import Decimal
    
    if amount is None:
        amount = 0
    if isinstance(amount, Decimal128):
        amount = int(amount.to_decimal())
    elif isinstance(amount, Decimal):
        amount = int(amount)
    else:
        try:
            amount = int(amount)
        except:
            amount = 0
    
    if amount < 1000:
        return f"{amount}{CURRENCY_SYMBOL}"
    
    units = [
        (10**60, "Nvd"), (10**57, "Ocd"), (10**54, "Spt"), (10**51, "Sxd"),
        (10**48, "Qnd"), (10**45, "Qtd"), (10**42, "Trd"), (10**39, "Dcd"),
        (10**36, "Udc"), (10**33, "Dc"), (10**30, "N"), (10**27, "Ot"),
        (10**24, "Sp"), (10**21, "Sx"), (10**18, "Qt"), (10**15, "Q"),
        (10**12, "T"), (10**9, "B"), (10**6, "M"), (10**3, "K")
    ]
    
    for unit, suffix in units:
        if amount >= unit:
            value = amount / unit
            if value >= 100:
                formatted = f"{value:.0f}"
            elif value >= 10:
                formatted = f"{value:.1f}"
            else:
                formatted = f"{value:.2f}".rstrip('0').rstrip('.')
            return f"{formatted}{suffix}{CURRENCY_SYMBOL}"
    
    return f"{amount}{CURRENCY_SYMBOL}"


def parse_amount(text: str, balance: int) -> tuple:
    """Yazıyı sayıya çevir (100k, 5m, allin)"""
    if text.lower() == "allin":
        return (balance, "") if balance > 0 else (None, "Bakiyeniz yetersiz.")
    
    text = text.lower().replace(",", "").replace(".", "").strip()
    
    muls = {
        "k": 10**3, "m": 10**6, "b": 10**9, "t": 10**12,
        "q": 10**15, "qt": 10**18, "sx": 10**21, "sp": 10**24,
        "o": 10**27, "n": 10**30, "d": 10**33
    }
    
    try:
        if len(text) > 2 and text[-2:] in muls:
            val = int(text[:-2]) * muls[text[-2:]]
        elif text[-1] in muls:
            val = int(text[:-1]) * muls[text[-1]]
        else:
            val = int(text)
    except (ValueError, IndexError):
        return None, "Geçersiz miktar. Örn: 100k, 5m, 1qt"
    
    if val <= 0:
        return None, "Miktar 0'dan büyük olmalı."
    if val > balance:
        return None, f"Yetersiz bakiye. Bakiyeniz: {format_amount(balance)}"
    return val, ""

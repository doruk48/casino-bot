# core/daily.py - Günlük Bonus
from datetime import datetime

def get_daily_bonus(streak: int) -> int:
    if streak < 0:
        streak = 0
    streak = min(streak, 10)
    return 50000 * (2 ** streak)

def can_claim_daily(last_daily: str) -> tuple[bool, int]:
    if not last_daily:
        return True, 0
    
    last = datetime.fromisoformat(last_daily)
    now = datetime.now()
    delta = now - last
    
    if delta.days >= 1:
        return True, 0
    else:
        hours_left = 24 - delta.seconds // 3600
        return False, hours_left

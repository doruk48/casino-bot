"""
Zamanlayıcı yönetimi: Geri sayım, süre bitimi, ara uyarılar.
"""
import asyncio
from ..engine import GameRoom, GameState, set_game


async def start_timer(game: GameRoom, duration: int, on_timeout, chat_id, context):
    """
    Belirli süre sonra timeout fonksiyonunu çağırır.
    Ara uyarıları da yönetir (60sn, 30sn, 10sn kala).
    """
    # Önceki zamanlayıcıyı iptal et
    cancel_timer(game)

    # Süre bitince çağrılacak ana görev
    async def _timer_task():
        # Ara uyarı noktaları
        warnings = [60, 30, 10]  # saniye kala uyarı
        remaining = duration

        for warn_at in sorted(warnings, reverse=True):
            if remaining > warn_at:
                await asyncio.sleep(remaining - warn_at)
                remaining = warn_at
                # Oyun hala aynı state'te mi kontrol et
                if game.state in [GameState.BLUE_CLUE, GameState.RED_CLUE,
                                 GameState.BLUE_GUESS, GameState.RED_GUESS]:
                    team = game.current_turn.value if game.current_turn else ""
                    if game.state in [GameState.BLUE_CLUE, GameState.RED_CLUE]:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"⏰ <b>{warn_at} saniye</b> kaldı!\n"
                                 f"{team.upper()} takım kaptanı ipucunu vermeli!",
                            parse_mode="HTML"
                        )
                    else:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"⏰ <b>{warn_at} saniye</b> kaldı!\n"
                                 f"{team.upper()} takım sözcüsü tahmin yapmalı!",
                            parse_mode="HTML"
                        )

        # Kalan süreyi bekle
        if remaining > 0:
            await asyncio.sleep(remaining)

        # Süre bitti, timeout fonksiyonunu çağır
        await on_timeout(game, chat_id, context)

    game.timer_task = asyncio.create_task(_timer_task())


def cancel_timer(game: GameRoom):
    """Aktif zamanlayıcıyı iptal eder."""
    if game.timer_task:
        game.timer_task.cancel()
        game.timer_task = None

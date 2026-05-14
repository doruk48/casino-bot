import asyncio

async def start_timer(game, duration: int, on_timeout, chat_id, context):
    """Belirli süre sonra timeout fonksiyonunu çağırır."""
    if game.timer_task:
        game.timer_task.cancel()
    async def _timer():
        await asyncio.sleep(duration)
        await on_timeout(game, chat_id, context)
    game.timer_task = asyncio.create_task(_timer())

def cancel_timer(game):
    if game.timer_task:
        game.timer_task.cancel()
        game.timer_task = None

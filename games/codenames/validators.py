from .engine import GameState

def validate_command(game, user_id: int, allowed_states: list, allowed_roles: list):
    """
    Döndürür: (is_valid, player, error_message)
    """
    if not game:
        return False, None, "⚠️ Aktif bir oyun bulunamadı."

    player = game.get_player(user_id)
    if not player and "any" not in allowed_roles:
        return False, None, "⚠️ Bu oyunda değilsiniz."

    if game.state not in allowed_states:
        return False, player, f"⏳ Bu komut şu an kullanılamaz. Aşama: {game.state.value}"

    if "captain" in allowed_roles and not player.is_captain:
        return False, player, "🛡️ Bu komut sadece kaptanlara özel."
    if "spokesperson" in allowed_roles and not player.is_spokesperson:
        return False, player, "🎤 Bu komut sadece takım sözcüsüne özel."
    if "player" in allowed_roles and player.team != game.current_turn:
        return False, player, "⏳ Sıra sizin takımınızda değil."
    if "host" in allowed_roles and user_id != game.host_id:
        return False, player, "🛡️ Bu işlem sadece oyun sahibine özel."

    return True, player, None

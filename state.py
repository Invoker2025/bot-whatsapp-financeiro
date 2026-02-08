# Gerenciamento de estados dos usuários
user_states = {}


def get_pending(user_id: str) -> dict:
    """Retorna os dados pendentes de um usuário"""
    return user_states.get(user_id, None)


def set_pending(user_id: str, data: dict):
    """Define dados pendentes para um usuário"""
    user_states[user_id] = data
    print(f"✅ Estado salvo para {user_id}")


def clear_pending(user_id: str):
    """Limpa os dados pendentes de um usuário"""
    if user_id in user_states:
        del user_states[user_id]
        print(f"🗑️ Estado limpo para {user_id}")

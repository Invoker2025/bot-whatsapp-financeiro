# Gerenciamento de estados dos usuários com persistência SQLite
import json
import os
import sqlite3
from datetime import date, datetime
from typing import Any, Dict, Optional

DB_NAME = os.getenv("STATE_DB_PATH", "gastos.db")


def _get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def _init_table():
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_states (
            user_id TEXT PRIMARY KEY,
            state_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


_init_table()


def _json_default(value: Any):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def get_pending(user_id: str) -> Optional[Dict[str, Any]]:
    """Retorna os dados pendentes de um usuário (do SQLite)"""
    # Tenta cache em memória primeiro
    if hasattr(get_pending, "_cache") and user_id in get_pending._cache:
        return get_pending._cache[user_id]

    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT state_data FROM user_states WHERE user_id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        try:
            data = json.loads(row["state_data"])
            # Atualiza cache em memória
            if not hasattr(get_pending, "_cache"):
                get_pending._cache = {}
            get_pending._cache[user_id] = data
            return data
        except (json.JSONDecodeError, KeyError):
            return None
    return None


def set_pending(user_id: str, data: dict):
    """Define dados pendentes para um usuário (persistente)"""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO user_states (user_id, state_data, created_at, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            state_data = excluded.state_data,
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, json.dumps(data, ensure_ascii=False, default=_json_default))
    )
    conn.commit()
    conn.close()

    # Atualiza cache em memória
    if not hasattr(get_pending, "_cache"):
        get_pending._cache = {}
    get_pending._cache[user_id] = data

    print("Estado pendente salvo.")


def clear_pending(user_id: str):
    """Limpa os dados pendentes de um usuário"""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM user_states WHERE user_id = ?",
        (user_id,)
    )
    conn.commit()
    conn.close()

    # Limpa cache em memória
    if hasattr(get_pending, "_cache") and user_id in get_pending._cache:
        del get_pending._cache[user_id]

    print("Estado pendente limpo.")

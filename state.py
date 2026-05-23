# Gerenciamento de estados dos usuários com persistência SQLite
import json
import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

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


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


def set_pending(
    user_id: str,
    data: dict,
    channel: Optional[str] = None,
    reminder_seconds: int = 120,
):
    """Define dados pendentes para um usuário (persistente)"""
    data = dict(data)
    if channel:
        data["_channel"] = channel

    data["_reminder_due_at"] = (
        _now_utc() + timedelta(seconds=max(1, reminder_seconds))
    ).isoformat()
    data["_reminder_sent"] = False

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


def get_due_reminders() -> List[Tuple[str, Dict[str, Any]]]:
    now = _now_utc()
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, state_data FROM user_states")
    rows = cursor.fetchall()
    conn.close()

    due = []
    for row in rows:
        try:
            data = json.loads(row["state_data"])
        except (json.JSONDecodeError, KeyError):
            continue

        if data.get("_reminder_sent"):
            continue

        due_at = _parse_datetime(str(data.get("_reminder_due_at", "")))
        if due_at and due_at <= now:
            due.append((row["user_id"], data))

    return due


def mark_reminder_sent(user_id: str) -> None:
    data = get_pending(user_id)
    if not data:
        return

    data["_reminder_sent"] = True
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE user_states
        SET state_data = ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
        """,
        (json.dumps(data, ensure_ascii=False, default=_json_default), user_id),
    )
    conn.commit()
    conn.close()

    if not hasattr(get_pending, "_cache"):
        get_pending._cache = {}
    get_pending._cache[user_id] = data

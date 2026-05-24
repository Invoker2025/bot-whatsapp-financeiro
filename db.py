import os
import sqlite3
from datetime import datetime
from typing import Dict, Tuple

from time_utils import now_local


DB_NAME = "gastos.db"
DATABASE_URL = os.getenv("DATABASE_URL", "")


def _use_postgres() -> bool:
    return DATABASE_URL.startswith(("postgres://", "postgresql://"))


def database_backend() -> str:
    return "postgres" if _use_postgres() else "sqlite"


def _postgres_url() -> str:
    if DATABASE_URL.startswith("postgres://"):
        return DATABASE_URL.replace("postgres://", "postgresql://", 1)
    return DATABASE_URL


def get_connection():
    if _use_postgres():
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "DATABASE_URL esta configurado, mas psycopg nao esta instalado."
            ) from exc

        return psycopg.connect(_postgres_url())

    return sqlite3.connect(DB_NAME)


def _placeholder() -> str:
    return "%s" if _use_postgres() else "?"


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    id_column = "SERIAL PRIMARY KEY" if _use_postgres() else "INTEGER PRIMARY KEY AUTOINCREMENT"

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS gastos (
            id {id_column},
            tipo TEXT,
            valor REAL,
            categoria TEXT,
            subcategoria TEXT,
            meio_pagamento TEXT,
            parcelado TEXT,
            parcela_atual INTEGER,
            total_parcelas INTEGER,
            descricao TEXT,
            origem TEXT,
            data TEXT
        )
    """)

    conn.commit()
    conn.close()


def check_connection() -> bool:
    try:
        init_db()
        return True
    except Exception as exc:
        print(f"Erro ao verificar banco de dados: {exc}")
        return False


def save_transaction(data: Dict):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    placeholder = _placeholder()
    placeholders = ", ".join([placeholder] * 11)

    cursor.execute(f"""
        INSERT INTO gastos (
            tipo, valor, categoria, subcategoria,
            meio_pagamento, parcelado,
            parcela_atual, total_parcelas,
            descricao, origem, data
        ) VALUES ({placeholders})
    """, (
        data.get("tipo"),
        data.get("valor"),
        data.get("categoria"),
        data.get("subcategoria"),
        data.get("meio_pagamento"),
        data.get("parcelado"),
        data.get("parcela_atual"),
        data.get("total_parcelas"),
        data.get("descricao"),
        data.get("origem"),
        data.get("data") or now_local().isoformat()
    ))

    conn.commit()
    conn.close()


def _parse_transaction_date(value: str):
    if not value:
        return None

    text = str(value)
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:26], fmt)
        except ValueError:
            continue

    return None


def get_month_summary_db(mes: int = None, ano: int = None) -> Tuple[float, Dict]:
    conn = get_connection()
    cursor = conn.cursor()

    if not mes or not ano:
        now = now_local()
        mes = mes or now.month
        ano = ano or now.year

    cursor.execute("""
        SELECT categoria, valor, data
        FROM gastos
        WHERE tipo = 'Gasto'
    """)

    rows = cursor.fetchall()
    conn.close()

    categorias = {}
    for categoria, valor, data in rows:
        parsed_date = _parse_transaction_date(data)
        if not parsed_date or parsed_date.month != mes or parsed_date.year != ano:
            continue

        value = float(valor or 0)
        categorias[categoria] = categorias.get(categoria, 0.0) + value

    total = sum(categorias.values())
    return total, categorias

import sqlite3
from typing import Tuple, Dict

from time_utils import now_local


DB_NAME = "gastos.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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


def save_transaction(data: Dict):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO gastos (
            tipo, valor, categoria, subcategoria,
            meio_pagamento, parcelado,
            parcela_atual, total_parcelas,
            descricao, origem, data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def get_month_summary_db(mes: int = None, ano: int = None) -> Tuple[float, Dict]:
    conn = get_connection()
    cursor = conn.cursor()

    if not mes or not ano:
        now = now_local()
        mes = mes or now.month
        ano = ano or now.year

    cursor.execute("""
        SELECT categoria, SUM(valor)
        FROM gastos
        WHERE strftime('%m', data) = ?
          AND strftime('%Y', data) = ?
          AND tipo = 'Gasto'
        GROUP BY categoria
    """, (f"{mes:02d}", str(ano)))

    rows = cursor.fetchall()

    total = sum(valor for _, valor in rows)
    categorias = {categoria: valor for categoria, valor in rows}

    conn.close()
    return total, categorias

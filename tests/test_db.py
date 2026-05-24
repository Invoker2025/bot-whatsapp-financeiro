import db


def test_sqlite_storage_summary(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATABASE_URL", "")
    monkeypatch.setattr(db, "DB_NAME", str(tmp_path / "transactions.db"))

    db.save_transaction(
        {
            "tipo": "Gasto",
            "valor": 25,
            "categoria": "Alimentação",
            "subcategoria": "Lanche",
            "meio_pagamento": "Pix",
            "parcelado": "Não",
            "parcela_atual": 1,
            "total_parcelas": 1,
            "descricao": "Lanche",
            "origem": "WhatsApp",
            "data": "2026-05-24T09:00:00.000000",
        }
    )
    db.save_transaction(
        {
            "tipo": "Gasto",
            "valor": 10,
            "categoria": "Saúde",
            "subcategoria": "Farmácia",
            "meio_pagamento": "Débito",
            "parcelado": "Não",
            "parcela_atual": 1,
            "total_parcelas": 1,
            "descricao": "Farmácia",
            "origem": "WhatsApp",
            "data": "2026-06-24T09:00:00.000000",
        }
    )

    total, categories = db.get_month_summary_db(5, 2026)

    assert total == 25
    assert categories == {"Alimentação": 25}
    assert db.database_backend() == "sqlite"

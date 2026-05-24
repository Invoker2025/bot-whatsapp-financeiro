import api_client


def test_save_to_api_batches_installments_and_records_db(monkeypatch):
    sheet_calls = []
    db_rows = []

    monkeypatch.setattr(api_client, "append_transactions", lambda rows: sheet_calls.append(rows) or True)
    monkeypatch.setattr(api_client, "save_transaction", lambda row: db_rows.append(row))
    monkeypatch.setattr(api_client, "google_sheets_configured", lambda: True)

    ok = api_client.save_to_api(
        {
            "tipo": "GASTO",
            "valor": 15,
            "categoria": "Alimentação",
            "subcategoria": "Almoço",
            "descricao": "Almoço",
            "meio": "Crédito",
            "total_parcelas": 2,
        }
    )

    assert ok is True
    assert len(sheet_calls) == 1
    assert len(sheet_calls[0]) == 2
    assert len(db_rows) == 2
    assert db_rows[0]["valor"] == 7.5

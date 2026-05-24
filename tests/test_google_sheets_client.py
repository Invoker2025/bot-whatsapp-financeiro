import google_sheets_client as sheets


class FakeWorksheet:
    def __init__(self, title):
        self.title = title
        self.id = abs(hash(title)) % 100000
        self.appended = []

    def append_rows(self, values, value_input_option=None):
        self.appended.append(values)


def test_append_transactions_batches_installments(monkeypatch):
    worksheets = {name: FakeWorksheet(name) for name in sheets.TAB_DEFINITIONS}
    summary_calls = []

    monkeypatch.setattr(sheets, "is_configured", lambda: True)
    monkeypatch.setattr(sheets, "_spreadsheet", lambda: object())
    monkeypatch.setattr(sheets, "_ensure_runtime_worksheets", lambda spreadsheet: worksheets)
    monkeypatch.setattr(
        sheets,
        "update_summary",
        lambda spreadsheet, worksheets=None: summary_calls.append(True),
    )

    ok = sheets.append_transactions(
        [
            {
                "data": "2026-05-24T09:08:00.000000",
                "tipo": "Gasto",
                "descricao": "Almoço (1/2)",
                "categoria": "Alimentação",
                "subcategoria": "Almoço",
                "meio_pagamento": "Crédito",
                "valor": 7.5,
                "parcelado": "Sim",
                "parcela_atual": 1,
                "total_parcelas": 2,
                "origem": "WhatsApp",
            },
            {
                "data": "2026-06-24T09:08:00.000000",
                "tipo": "Gasto",
                "descricao": "Almoço (2/2)",
                "categoria": "Alimentação",
                "subcategoria": "Almoço",
                "meio_pagamento": "Crédito",
                "valor": 7.5,
                "parcelado": "Sim",
                "parcela_atual": 2,
                "total_parcelas": 2,
                "origem": "WhatsApp",
            },
        ]
    )

    assert ok is True
    assert len(worksheets["Transacoes"].appended) == 1
    assert len(worksheets["Transacoes"].appended[0]) == 2
    assert len(worksheets["Despesas"].appended) == 1
    assert len(worksheets["Parceladas"].appended[0]) == 2
    assert len(summary_calls) == 1


def test_latest_transaction_rows_fill_dashboard_limit():
    rows = sheets._latest_transaction_rows(
        None,
        3,
        [
            {
                "Data": "24/05/2026 09:08",
                "Tipo": "Gasto",
                "Descricao": "Almoço (1/2)",
                "Categoria": "Alimentação",
                "Meio": "Crédito",
                "Valor": 7.5,
                "Parcelado": "Sim",
                "Parcela": 1,
                "Total Parcelas": 2,
            }
        ],
    )

    assert len(rows) == 3
    assert rows[0][-1] == "1/2"
    assert rows[1][2] == ""

from datetime import datetime
from typing import Any, Dict, List

import gspread

from config import GOOGLE_SERVICE_ACCOUNT_FILE, GOOGLE_SHEET_ID


TRANSACTIONS_HEADERS = [
    "Data",
    "Tipo",
    "Descricao",
    "Categoria",
    "Subcategoria",
    "Meio",
    "Valor",
    "Parcelado",
    "Parcela",
    "Total Parcelas",
    "Origem",
]

DESPESAS_HEADERS = [
    "Data",
    "Descricao",
    "Categoria",
    "Subcategoria",
    "Meio",
    "Valor",
    "Parcela",
    "Status",
]

RECEITAS_HEADERS = ["Data", "Descricao", "Valor", "Meio", "Origem"]
PARCELADAS_HEADERS = ["Data", "Descricao", "Categoria", "Valor", "Parcela", "Meio"]
CONTAS_HEADERS = ["Data", "Descricao", "Categoria", "Valor", "Status"]
CATEGORIAS_HEADERS = ["Categoria", "Orcamento", "Real Gasto", "Sobra Para Gastar"]
METAS_HEADERS = ["Descricao", "Valor", "Status", "Valor Atual"]
DIVIDAS_HEADERS = ["Descricao", "Data", "Parcela", "Valor", "Status"]

TAB_DEFINITIONS = {
    "Resumo": [],
    "Transacoes": TRANSACTIONS_HEADERS,
    "Receitas": RECEITAS_HEADERS,
    "Despesas": DESPESAS_HEADERS,
    "Contas": CONTAS_HEADERS,
    "Parceladas": PARCELADAS_HEADERS,
    "Categorias": CATEGORIAS_HEADERS,
    "Metas": METAS_HEADERS,
    "Dividas": DIVIDAS_HEADERS,
}


def is_configured() -> bool:
    return bool(GOOGLE_SHEET_ID and GOOGLE_SERVICE_ACCOUNT_FILE)


def _client():
    return gspread.service_account(filename=GOOGLE_SERVICE_ACCOUNT_FILE)


def _spreadsheet():
    return _client().open_by_key(GOOGLE_SHEET_ID)


def _worksheet(spreadsheet, title: str, headers: List[str]):
    try:
        worksheet = spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=title, rows=200, cols=max(len(headers), 8))

    if headers:
        current_headers = worksheet.row_values(1)
        if current_headers != headers:
            worksheet.update("A1", [headers])
            _format_header(spreadsheet, worksheet.id, len(headers))

    return worksheet


def _format_header(spreadsheet, sheet_id: int, column_count: int) -> None:
    spreadsheet.batch_update(
        {
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": column_count,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": {"red": 0.13, "green": 0.50, "blue": 0.27},
                                "textFormat": {
                                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                                    "bold": True,
                                },
                                "horizontalAlignment": "CENTER",
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                    }
                },
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sheet_id,
                            "gridProperties": {"frozenRowCount": 1},
                        },
                        "fields": "gridProperties.frozenRowCount",
                    }
                },
            ]
        }
    )


def ensure_finance_sheet() -> None:
    if not is_configured():
        return

    spreadsheet = _spreadsheet()
    for title, headers in TAB_DEFINITIONS.items():
        _worksheet(spreadsheet, title, headers)
    update_summary()


def append_transaction(data: Dict[str, Any]) -> bool:
    if not is_configured():
        return False

    spreadsheet = _spreadsheet()
    for title, headers in TAB_DEFINITIONS.items():
        _worksheet(spreadsheet, title, headers)

    normalized = _normalize_transaction(data)
    spreadsheet.worksheet("Transacoes").append_row(
        [
            normalized["data"],
            normalized["tipo"],
            normalized["descricao"],
            normalized["categoria"],
            normalized["subcategoria"],
            normalized["meio_pagamento"],
            normalized["valor"],
            normalized["parcelado"],
            normalized["parcela_atual"],
            normalized["total_parcelas"],
            normalized["origem"],
        ],
        value_input_option="USER_ENTERED",
    )

    if normalized["tipo"] == "Receita":
        spreadsheet.worksheet("Receitas").append_row(
            [
                normalized["data"],
                normalized["descricao"],
                normalized["valor"],
                normalized["meio_pagamento"],
                normalized["origem"],
            ],
            value_input_option="USER_ENTERED",
        )
    else:
        spreadsheet.worksheet("Despesas").append_row(
            [
                normalized["data"],
                normalized["descricao"],
                normalized["categoria"],
                normalized["subcategoria"],
                normalized["meio_pagamento"],
                normalized["valor"],
                _parcel_label(normalized),
                "pago",
            ],
            value_input_option="USER_ENTERED",
        )

        if normalized["categoria"] == "Contas":
            spreadsheet.worksheet("Contas").append_row(
                [
                    normalized["data"],
                    normalized["descricao"],
                    normalized["categoria"],
                    normalized["valor"],
                    "pago",
                ],
                value_input_option="USER_ENTERED",
            )

        if normalized["parcelado"] == "Sim":
            spreadsheet.worksheet("Parceladas").append_row(
                [
                    normalized["data"],
                    normalized["descricao"],
                    normalized["categoria"],
                    normalized["valor"],
                    _parcel_label(normalized),
                    normalized["meio_pagamento"],
                ],
                value_input_option="USER_ENTERED",
            )

    update_summary(spreadsheet)
    return True


def update_summary(spreadsheet=None) -> None:
    if not is_configured():
        return

    spreadsheet = spreadsheet or _spreadsheet()
    resumo = _worksheet(spreadsheet, "Resumo", [])
    transacoes = _worksheet(spreadsheet, "Transacoes", TRANSACTIONS_HEADERS)
    rows = transacoes.get_all_records()

    now = datetime.now()
    entradas = despesas = contas = parceladas = 0.0
    categorias: Dict[str, float] = {}

    for row in rows:
        row_date = _parse_date(str(row.get("Data", "")))
        if not row_date or row_date.month != now.month or row_date.year != now.year:
            continue

        valor = _to_float(row.get("Valor", 0))
        tipo = str(row.get("Tipo", ""))
        categoria = str(row.get("Categoria", "Outros") or "Outros")

        if tipo == "Receita":
            entradas += valor
        else:
            if categoria == "Contas":
                contas += valor
            else:
                despesas += valor

            if str(row.get("Parcelado", "")) == "Sim":
                parceladas += valor

            categorias[categoria] = categorias.get(categoria, 0.0) + valor

    saldo = entradas - despesas - contas
    resumo.clear()
    resumo.update(
        "A1",
        [
            ["Resumo do Mes"],
            ["Entradas", entradas],
            ["Contas", contas],
            ["Despesas", despesas],
            ["Parceladas", parceladas],
            ["Saldo", saldo],
            [],
            ["Categorias", "Real Gasto"],
            *[[categoria, valor] for categoria, valor in sorted(categorias.items())],
        ],
        value_input_option="USER_ENTERED",
    )

    spreadsheet.batch_update(
        {
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": resumo.id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": 2,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": {"red": 0.13, "green": 0.50, "blue": 0.27},
                                "textFormat": {
                                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                                    "bold": True,
                                },
                                "horizontalAlignment": "CENTER",
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                    }
                }
            ]
        }
    )


def _normalize_transaction(data: Dict[str, Any]) -> Dict[str, Any]:
    parsed_date = _parse_date(str(data.get("data", ""))) or datetime.now()
    total_parcelas = int(data.get("total_parcelas", 1) or 1)
    parcela_atual = int(data.get("parcela_atual", 1) or 1)

    return {
        "data": parsed_date.strftime("%d/%m/%Y"),
        "tipo": data.get("tipo", "Gasto"),
        "descricao": data.get("descricao", ""),
        "categoria": data.get("categoria", "Geral"),
        "subcategoria": data.get("subcategoria", ""),
        "meio_pagamento": data.get("meio_pagamento", data.get("meio", "")),
        "valor": round(float(data.get("valor", 0) or 0), 2),
        "parcelado": data.get("parcelado", "Não"),
        "parcela_atual": parcela_atual,
        "total_parcelas": total_parcelas,
        "origem": data.get("origem", "WhatsApp"),
    }


def _parcel_label(data: Dict[str, Any]) -> str:
    return f"{data['parcela_atual']}/{data['total_parcelas']}"


def _parse_date(value: str):
    if not value:
        return None

    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(value[:26], fmt)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _to_float(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value or "0").replace("R$", "").strip()
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0

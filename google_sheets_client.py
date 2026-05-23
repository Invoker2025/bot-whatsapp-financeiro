from datetime import datetime
from typing import Any, Dict, List
import unicodedata

import gspread
from gspread.utils import a1_range_to_grid_range

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
PARCELADAS_HEADERS = ["Data", "Descricao",
                      "Categoria", "Valor", "Parcela", "Meio"]
CONTAS_HEADERS = ["Data", "Descricao", "Categoria", "Valor", "Status"]
CATEGORIAS_HEADERS = ["Categoria", "Orcamento",
                      "Real Gasto", "Sobra Para Gastar"]
METAS_HEADERS = ["Descricao", "Valor", "Status", "Valor Atual"]
DIVIDAS_HEADERS = ["Descricao", "Data", "Parcela", "Valor", "Status"]

TAB_DEFINITIONS = {
    "Dashboard": [],
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

LEGACY_TABS = {
    "Dashboard",
    "LANÇAMENTOS",
    "LANCAMENTOS",
    "APOIO",
    "MAPEAMENTO",
    "CONFIG",
}

COLORS = {
    "green": {"red": 0.42, "green": 0.66, "blue": 0.43},
    "green_dark": {"red": 0.13, "green": 0.50, "blue": 0.27},
    "teal": {"red": 0.33, "green": 0.61, "blue": 0.64},
    "blue": {"red": 0.39, "green": 0.64, "blue": 0.84},
    "yellow": {"red": 1.00, "green": 0.77, "blue": 0.25},
    "orange": {"red": 1.00, "green": 0.61, "blue": 0.42},
    "red": {"red": 1.00, "green": 0.39, "blue": 0.42},
    "pale_green": {"red": 0.85, "green": 0.96, "blue": 0.88},
    "pale_blue": {"red": 0.86, "green": 0.93, "blue": 0.98},
    "pale_yellow": {"red": 1.00, "green": 0.95, "blue": 0.78},
    "pale_orange": {"red": 1.00, "green": 0.91, "blue": 0.86},
    "pale_red": {"red": 1.00, "green": 0.88, "blue": 0.89},
    "white": {"red": 1, "green": 1, "blue": 1},
    "canvas": {"red": 0.96, "green": 0.98, "blue": 0.97},
    "muted": {"red": 0.55, "green": 0.61, "blue": 0.67},
    "line": {"red": 0.84, "green": 0.88, "blue": 0.91},
    "dark": {"red": 0.05, "green": 0.09, "blue": 0.16},
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
        rows = 120 if title == "Dashboard" else 200
        cols = 18 if title == "Dashboard" else max(len(headers), 8)
        worksheet = spreadsheet.add_worksheet(
            title=title, rows=rows, cols=cols)

    if headers:
        current_headers = worksheet.row_values(1)
        if current_headers != headers:
            worksheet.update(
                [headers], "A1", value_input_option="USER_ENTERED")
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


def _format_a1(
    spreadsheet,
    sheet_id: int,
    a1_range: str,
    background: str,
    foreground: str = "dark",
    bold: bool = False,
    align: str = "CENTER",
    font_size: int = None,
    wrap: str = "WRAP",
) -> Dict[str, Any]:
    text_format = {
        "foregroundColor": COLORS[foreground],
        "bold": bold,
    }
    if font_size:
        text_format["fontSize"] = font_size

    return {
        "repeatCell": {
            "range": a1_range_to_grid_range(a1_range, sheet_id),
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": COLORS[background],
                    "textFormat": text_format,
                    "horizontalAlignment": align,
                    "verticalAlignment": "MIDDLE",
                    "wrapStrategy": wrap,
                }
            },
            "fields": (
                "userEnteredFormat(backgroundColor,textFormat,"
                "horizontalAlignment,verticalAlignment,wrapStrategy)"
            ),
        }
    }


def _merge_cells(sheet_id: int, a1_range: str) -> Dict[str, Any]:
    return {
        "mergeCells": {
            "range": a1_range_to_grid_range(a1_range, sheet_id),
            "mergeType": "MERGE_ALL",
        }
    }


def _format_borders(sheet_id: int, a1_range: str) -> Dict[str, Any]:
    border = {
        "style": "SOLID",
        "width": 1,
        "color": {"red": 0.78, "green": 0.82, "blue": 0.87},
    }
    return {
        "updateBorders": {
            "range": a1_range_to_grid_range(a1_range, sheet_id),
            "top": border,
            "bottom": border,
            "left": border,
            "right": border,
            "innerHorizontal": border,
            "innerVertical": border,
        }
    }


def _set_column_width(sheet_id: int, start: int, end: int, width: int) -> Dict[str, Any]:
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "startIndex": start,
                "endIndex": end,
            },
            "properties": {"pixelSize": width},
            "fields": "pixelSize",
        }
    }


def _number_format(sheet_id: int, a1_range: str, pattern: str) -> Dict[str, Any]:
    return {
        "repeatCell": {
            "range": a1_range_to_grid_range(a1_range, sheet_id),
            "cell": {
                "userEnteredFormat": {
                    "numberFormat": {
                        "type": "NUMBER",
                        "pattern": pattern,
                    }
                }
            },
            "fields": "userEnteredFormat.numberFormat",
        }
    }


def _hide_sheet(sheet_id: int) -> Dict[str, Any]:
    return {
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "hidden": True,
            },
            "fields": "hidden",
        }
    }


def _dashboard_has_template(worksheet) -> bool:
    return worksheet.acell("A1").value == "PLANILHA IA" or worksheet.acell("B1").value == "PLANILHA IA"


def _build_dashboard_layout(spreadsheet) -> None:
    dashboard = _worksheet(spreadsheet, "Dashboard", [])
    dashboard.clear()

    dashboard.update(
        [
            ["", "PLANILHA IA", "", "", "", "", "", "",
                "", "", "", "", "", "", "", "", ""],
            ["", "Dashboard financeiro automático", "", "", "",
                "", "", "", "", "", "", "", "", "", "", "", ""],
            ["", "Mês", datetime.now().strftime("%m/%Y"), "", "", "Entradas",
             0, "", "Despesas", 0, "", "Saldo", 0, "", "Orçamento", 0, ""],
            ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
            ["", "Receitas", "", "", "", "Metas", "", "", "",
                "Dívidas", "", "", "", "", "Resumo", "", ""],
            ["", "Descrição", "Valor", "", "", "Descrição", "Valor", "Status", "",
                "Descrição", "Data", "Parcela", "Valor", "Status", "Este mês", ""],
            ["", "Sem receitas", 0, "", "", "Reserva de Emergência", 0,
                "pendente", "", "Sem dívidas", "", "", 0, "pendente", "Entradas", 0],
            ["", "", 0, "", "", "Viagem de fim de ano", 0,
                "pendente", "", "", "", "", "", "", "Contas", 0],
            ["", "Total", 0, "", "", "Total", 0, "", "",
                "Total", "", "", 0, "", "Despesas", 0],
            ["", "", "", "", "", "", "", "", "",
                "", "", "", "", "", "Saldo", 0, ""],
            ["", "Contas", "", "", "", "", "", "", "",
                "Categorias", "", "", "", "", "Parceladas", "", ""],
            ["", "Descrição", "Data", "Categoria", "Valor", "Status", "", "", "",
                "Categoria", "Orçamento", "Real Gasto", "Sobra", "", "Descrição", "Valor", ""],
            ["", "Sem contas", "", "", 0, "pendente", "", "", "",
                "Moradia", 2200, 0, 2200, "", "Sem parcelas", 0, ""],
            ["", "", "", "", 0, "", "", "", "",
                "Alimentação", 600, 0, 600, "", "", 0, ""],
            ["", "Total", "", "", 0, "", "", "", "",
                "Mercado", 600, 0, 600, "", "Total", 0, ""],
            ["", "", "", "", "", "", "", "", "",
                "Transporte", 300, 0, 300, "", "", "", ""],
            ["", "Despesas", "", "", "", "", "", "", "",
                "Lazer", 200, 0, 200, "", "", "", ""],
            ["", "Descrição", "Data", "Forma", "Categoria", "Valor",
                "", "", "", "Saúde", 200, 0, 200, "", "Gasto", 0, ""],
            ["", "Sem despesas", "", "", "", 0, "", "", "",
                "Shopping", 200, 0, 200, "", "Sobra", 0, ""],
            ["", "", "", "", "", 0, "", "", "",
                "Outros", 300, 0, 300, "", "", "", ""],
            ["", "Total", "", "", "", 0, "", "", "",
                "Total", 4600, 0, 4600, "", "", "", ""],
            [],
            ["", "Últimas transações", "", "", "", "", "",
                "", "", "", "", "", "", "", "", "", ""],
            ["", "Data", "Tipo", "Descrição", "Categoria", "Meio",
                "Valor", "Parcelas", "", "", "", "", "", "", "", "", ""],
            ["", "", "", "Sem lançamentos", "", "", 0,
                "", "", "", "", "", "", "", "", "", ""],
            ["", "", "", "", "", "", 0, "", "", "", "", "", "", "", "", "", ""],
        ],
        "A1",
        value_input_option="USER_ENTERED",
    )

    requests = [
        _merge_cells(dashboard.id, "B1:Q1"),
        _merge_cells(dashboard.id, "B2:Q2"),
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": dashboard.id,
                    "gridProperties": {
                        "frozenRowCount": 4,
                        "hideGridlines": True,
                    },
                },
                "fields": "gridProperties(frozenRowCount,hideGridlines)",
            }
        },
        _set_column_width(dashboard.id, 0, 1, 32),
        _set_column_width(dashboard.id, 1, 2, 125),
        _set_column_width(dashboard.id, 2, 3, 105),
        _set_column_width(dashboard.id, 3, 4, 140),
        _set_column_width(dashboard.id, 4, 6, 105),
        _set_column_width(dashboard.id, 6, 9, 92),
        _set_column_width(dashboard.id, 9, 14, 110),
        _set_column_width(dashboard.id, 14, 17, 120),
        _format_a1(spreadsheet, dashboard.id, "A1:Q30", "canvas", "dark"),
        _format_a1(spreadsheet, dashboard.id, "B1:Q1",
                   "green_dark", "white", True, "LEFT", 22),
        _format_a1(spreadsheet, dashboard.id, "B2:Q2",
                   "green_dark", "white", False, "LEFT", 11),
        _format_a1(spreadsheet, dashboard.id, "B3:C3", "white", "dark", True),
        _format_a1(spreadsheet, dashboard.id, "F3:G3",
                   "pale_green", "dark", True),
        _format_a1(spreadsheet, dashboard.id, "I3:J3",
                   "pale_orange", "dark", True),
        _format_a1(spreadsheet, dashboard.id, "L3:M3",
                   "pale_blue", "dark", True),
        _format_a1(spreadsheet, dashboard.id, "O3:P3",
                   "pale_yellow", "dark", True),
        _format_a1(spreadsheet, dashboard.id, "B5:C5", "green", "white", True),
        _format_a1(spreadsheet, dashboard.id, "F5:H5", "teal", "white", True),
        _format_a1(spreadsheet, dashboard.id,
                   "J5:N5", "yellow", "white", True),
        _format_a1(spreadsheet, dashboard.id,
                   "B11:F11", "blue", "white", True),
        _format_a1(spreadsheet, dashboard.id,
                   "B17:F17", "orange", "white", True),
        _format_a1(spreadsheet, dashboard.id,
                   "J11:M11", "orange", "white", True),
        _format_a1(spreadsheet, dashboard.id, "O11:P11", "red", "white", True),
        _format_a1(spreadsheet, dashboard.id, "B23:H23",
                   "green_dark", "white", True),
        _format_a1(spreadsheet, dashboard.id, "O5:P5",
                   "pale_yellow", "dark", True),
        _format_a1(spreadsheet, dashboard.id, "B6:C6",
                   "pale_green", "dark", True),
        _format_a1(spreadsheet, dashboard.id, "F6:H6",
                   "pale_blue", "dark", True),
        _format_a1(spreadsheet, dashboard.id, "J6:N6",
                   "pale_yellow", "dark", True),
        _format_a1(spreadsheet, dashboard.id, "B12:F12",
                   "pale_blue", "dark", True),
        _format_a1(spreadsheet, dashboard.id, "B18:F18",
                   "pale_orange", "dark", True),
        _format_a1(spreadsheet, dashboard.id, "J12:M12",
                   "pale_orange", "dark", True),
        _format_a1(spreadsheet, dashboard.id,
                   "O12:P12", "pale_red", "dark", True),
        _format_a1(spreadsheet, dashboard.id, "B24:H24",
                   "pale_green", "dark", True),
        _format_a1(spreadsheet, dashboard.id, "B9:C9",
                   "pale_green", "dark", True),
        _format_a1(spreadsheet, dashboard.id, "F9:H9",
                   "pale_blue", "dark", True),
        _format_a1(spreadsheet, dashboard.id, "J9:N9",
                   "pale_yellow", "dark", True),
        _format_a1(spreadsheet, dashboard.id, "B15:F15",
                   "pale_blue", "dark", True),
        _format_a1(spreadsheet, dashboard.id, "B21:F21",
                   "pale_orange", "dark", True),
        _format_a1(spreadsheet, dashboard.id, "J21:M21",
                   "pale_orange", "dark", True),
        _format_a1(spreadsheet, dashboard.id,
                   "O15:P15", "pale_red", "dark", True),
        _format_borders(dashboard.id, "B5:C9"),
        _format_borders(dashboard.id, "F5:H9"),
        _format_borders(dashboard.id, "J5:N9"),
        _format_borders(dashboard.id, "B11:F15"),
        _format_borders(dashboard.id, "B17:F21"),
        _format_borders(dashboard.id, "J11:M21"),
        _format_borders(dashboard.id, "O11:P19"),
        _format_borders(dashboard.id, "O5:P10"),
        _format_borders(dashboard.id, "B23:H27"),
        _format_borders(dashboard.id, "B3:C3"),
        _format_borders(dashboard.id, "F3:G3"),
        _format_borders(dashboard.id, "I3:J3"),
        _format_borders(dashboard.id, "L3:M3"),
        _format_borders(dashboard.id, "O3:P3"),
        _number_format(dashboard.id, "C7:C9", '"R$" #,##0.00'),
        _number_format(dashboard.id, "G7:G9", '"R$" #,##0.00'),
        _number_format(dashboard.id, "M7:M9", '"R$" #,##0.00'),
        _number_format(dashboard.id, "E13:E15", '"R$" #,##0.00'),
        _number_format(dashboard.id, "F19:F21", '"R$" #,##0.00'),
        _number_format(dashboard.id, "K13:M21", '"R$" #,##0.00'),
        _number_format(dashboard.id, "P3:P21", '"R$" #,##0.00'),
        _number_format(dashboard.id, "P13:P15", '"R$" #,##0.00'),
        _number_format(dashboard.id, "P18:P19", '"R$" #,##0.00'),
        _number_format(dashboard.id, "G25:G27", '"R$" #,##0.00'),
        _format_a1(spreadsheet, dashboard.id, "B6:Q27", "white",
                   "dark", False, "CENTER", None, "CLIP"),
    ]
    for worksheet in spreadsheet.worksheets():
        if worksheet.title != "Dashboard":
            requests.append(_hide_sheet(worksheet.id))

    spreadsheet.batch_update({"requests": requests})


def ensure_finance_sheet() -> None:
    if not is_configured():
        return

    spreadsheet = _spreadsheet()
    for title, headers in TAB_DEFINITIONS.items():
        _worksheet(spreadsheet, title, headers)
    dashboard = _worksheet(spreadsheet, "Dashboard", [])
    if not _dashboard_has_template(dashboard):
        _build_dashboard_layout(spreadsheet)
    update_summary()


def reset_finance_template(delete_legacy: bool = True) -> None:
    """
    Prepara uma planilha limpa para o bot.

    Abas fora do template do bot sao apagadas. As abas usadas pelo bot sao
    limpas e recriadas com cabecalhos.
    """
    if not is_configured():
        return

    spreadsheet = _spreadsheet()

    for title, headers in TAB_DEFINITIONS.items():
        worksheet = _worksheet(spreadsheet, title, headers)

    if delete_legacy:
        _delete_non_template_tabs(spreadsheet)

    for title, headers in TAB_DEFINITIONS.items():
        worksheet = _worksheet(spreadsheet, title, headers)
        worksheet.clear()
        if headers:
            worksheet.update(
                [headers], "A1", value_input_option="USER_ENTERED")
            _format_header(spreadsheet, worksheet.id, len(headers))

    _seed_template_rows(spreadsheet)
    _build_dashboard_layout(spreadsheet)
    update_summary(spreadsheet)
    _reorder_dashboard_first(spreadsheet)


def _delete_non_template_tabs(spreadsheet) -> None:
    for worksheet in spreadsheet.worksheets():
        if worksheet.title in TAB_DEFINITIONS:
            continue

        spreadsheet.del_worksheet(worksheet)


def _reorder_dashboard_first(spreadsheet) -> None:
    dashboard = spreadsheet.worksheet("Dashboard")
    spreadsheet.batch_update(
        {
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": dashboard.id,
                            "index": 0,
                            "hidden": False,
                        },
                        "fields": "index,hidden",
                    }
                }
            ]
        }
    )


def _seed_template_rows(spreadsheet) -> None:
    spreadsheet.worksheet("Categorias").append_rows(
        [
            ["Alimentação", 700, 0, "=B2-C2"],
            ["Transporte", 400, 0, "=B3-C3"],
            ["Lazer", 500, 0, "=B4-C4"],
            ["Moradia", 2000, 0, "=B5-C5"],
            ["Assinaturas", 100, 0, "=B6-C6"],
            ["Saúde", 300, 0, "=B7-C7"],
            ["Shopping", 300, 0, "=B8-C8"],
            ["Outros", 300, 0, "=B9-C9"],
        ],
        value_input_option="USER_ENTERED",
    )

    spreadsheet.worksheet("Metas").append_rows(
        [
            ["Reserva de Emergência", 0, "pendente", 0],
            ["Viagem de fim de ano", 0, "pendente", 0],
        ],
        value_input_option="USER_ENTERED",
    )


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
    _update_category_sheet(spreadsheet, categorias)
    category_rows = _get_category_rows(spreadsheet)
    resumo.clear()
    resumo.update(
        [
            ["Resumo do Mes"],
            ["Entradas", entradas],
            ["Contas", contas],
            ["Despesas", despesas],
            ["Parceladas", parceladas],
            ["Saldo", saldo],
            [],
            ["Categorias", "Real Gasto"],
            *[[row["categoria"], row["real"]] for row in category_rows],
        ],
        "A1",
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
    _update_dashboard(
        spreadsheet,
        {
            "entradas": entradas,
            "contas": contas,
            "despesas": despesas,
            "parceladas": parceladas,
            "saldo": saldo,
            "orcamento": sum(row["orcamento"] for row in category_rows),
            "categorias": category_rows,
        },
    )


def _update_category_sheet(spreadsheet, categorias: Dict[str, float]) -> None:
    worksheet = _worksheet(spreadsheet, "Categorias", CATEGORIAS_HEADERS)
    records = worksheet.get_all_records()
    if not records:
        return

    updates = []
    for index, row in enumerate(records, start=2):
        categoria = str(row.get("Categoria", "")).strip()
        orcamento = _to_float(row.get("Orcamento", 0))
        real = round(categorias.get(categoria, 0.0), 2)
        sobra = round(orcamento - real, 2)
        updates.append([real, sobra])

    if updates:
        worksheet.update(
            updates, f"C2:D{len(updates) + 1}", value_input_option="USER_ENTERED")


def _get_category_rows(spreadsheet) -> List[Dict[str, Any]]:
    worksheet = _worksheet(spreadsheet, "Categorias", CATEGORIAS_HEADERS)
    rows = []
    for row in worksheet.get_all_records():
        categoria = str(row.get("Categoria", "")).strip()
        if not categoria:
            continue
        orcamento = _to_float(row.get("Orcamento", 0))
        real = _to_float(row.get("Real Gasto", 0))
        rows.append(
            {
                "categoria": categoria,
                "orcamento": orcamento,
                "real": real,
                "sobra": round(orcamento - real, 2),
            }
        )
    return rows


def _latest_records(spreadsheet, worksheet_name: str, limit: int) -> List[Dict[str, Any]]:
    worksheet = _worksheet(spreadsheet, worksheet_name,
                           TAB_DEFINITIONS.get(worksheet_name, []))
    records = worksheet.get_all_records()
    return records[-limit:] if records else []


def _update_dashboard(spreadsheet, totals: Dict[str, Any]) -> None:
    dashboard = _worksheet(spreadsheet, "Dashboard", [])
    if not _dashboard_has_template(dashboard):
        _build_dashboard_layout(spreadsheet)

    receitas = _latest_records(spreadsheet, "Receitas", 2)
    despesas = _latest_records(spreadsheet, "Despesas", 2)
    contas = _latest_records(spreadsheet, "Contas", 2)
    parceladas = _latest_records(spreadsheet, "Parceladas", 1)
    categorias = totals.get("categorias", [])[:8]

    dashboard.batch_update(
        [
            {"range": "C3", "values": [[datetime.now().strftime("%m/%Y")]]},
            {"range": "G3", "values": [[totals["entradas"]]]},
            {"range": "J3", "values": [
                [totals["despesas"] + totals["contas"]]]},
            {"range": "M3", "values": [[totals["saldo"]]]},
            {"range": "P3", "values": [[totals["orcamento"]]]},
            {
                "range": "B7:C8",
                "values": _two_col_records(receitas, "Descricao", "Valor", "Sem receitas", 2),
            },
            {"range": "B9:C9", "values": [["Total", totals["entradas"]]]},
            {
                "range": "B13:F14",
                "values": _account_rows(contas, 2),
            },
            {"range": "B15:F15", "values": [
                ["Total", "", "", totals["contas"], ""]]},
            {
                "range": "B19:F20",
                "values": _expense_rows(despesas, 2),
            },
            {"range": "B21:F21", "values": [
                ["Total", "", "", "", totals["despesas"]]]},
            {
                "range": "J13:M20",
                "values": _dashboard_category_rows(categorias, 8),
            },
            {"range": "J21:M21", "values": [["Total", totals["orcamento"], totals["despesas"] +
                                             totals["contas"], totals["orcamento"] - totals["despesas"] - totals["contas"]]]},
            {
                "range": "O13:P14",
                "values": _parcel_rows(parceladas),
            },
            {"range": "O15:P15", "values": [["Total", totals["parceladas"]]]},
            {
                "range": "O6:P10",
                "values": [
                    ["Este mês", ""],
                    ["Entradas", totals["entradas"]],
                    ["Contas", totals["contas"]],
                    ["Despesas", totals["despesas"]],
                    ["Saldo", totals["saldo"]],
                ],
            },
            {"range": "P18:P19", "values": [[totals["despesas"] + totals["contas"]], [
                totals["orcamento"] - totals["despesas"] - totals["contas"]]]},
            {
                "range": "B25:H26",
                "values": _latest_transaction_rows(spreadsheet, 2),
            },
        ],
        value_input_option="USER_ENTERED",
    )


def _two_col_records(records, first_key, second_key, empty_label, limit):
    output = []
    for record in records[-limit:]:
        output.append([record.get(first_key, ""),
                      _to_float(record.get(second_key, 0))])
    while len(output) < limit:
        output.append([empty_label if not output else "", 0])
    return output


def _account_rows(records, limit):
    output = []
    for record in records[-limit:]:
        output.append(
            [
                record.get("Descricao", ""),
                record.get("Data", ""),
                record.get("Categoria", ""),
                _to_float(record.get("Valor", 0)),
                record.get("Status", ""),
            ]
        )
    while len(output) < limit:
        output.append(["Sem contas" if not output else "", "", "", 0, ""])
    return output


def _expense_rows(records, limit):
    output = []
    for record in records[-limit:]:
        output.append(
            [
                record.get("Descricao", ""),
                record.get("Data", ""),
                record.get("Meio", ""),
                record.get("Categoria", ""),
                _to_float(record.get("Valor", 0)),
            ]
        )
    while len(output) < limit:
        output.append(["Sem despesas" if not output else "", "", "", "", 0])
    return output


def _dashboard_category_rows(rows, limit):
    output = []
    for row in rows[:limit]:
        output.append([row["categoria"], row["orcamento"],
                      row["real"], row["sobra"]])
    while len(output) < limit:
        output.append(["", 0, 0, 0])
    return output


def _parcel_rows(records):
    if not records:
        return [["Sem parcelas", 0], ["", 0]]
    record = records[-1]
    return [[record.get("Descricao", ""), _to_float(record.get("Valor", 0))], ["", 0]]


def _latest_transaction_rows(spreadsheet, limit):
    records = _latest_records(spreadsheet, "Transacoes", limit)
    output = []
    for record in records[-limit:]:
        output.append(
            [
                record.get("Data", ""),
                record.get("Tipo", ""),
                record.get("Descricao", ""),
                record.get("Categoria", ""),
                record.get("Meio", ""),
                _to_float(record.get("Valor", 0)),
                _parcel_display(record),
            ]
        )

    while len(output) < limit:
        output.append(
            ["", "", "Sem lançamentos" if not output else "", "", "", 0, ""])
    return output


def _parcel_display(record: Dict[str, Any]) -> str:
    parcelado = str(record.get("Parcelado", "") or "").strip().lower()
    meio = _normalize_text(record.get("Meio", ""))
    parcela = record.get("Parcela", "")
    total = record.get("Total Parcelas", "")

    try:
        total_int = int(total or 0)
    except (TypeError, ValueError):
        total_int = 0

    if _is_credit_payment(meio) and parcelado == "sim" and parcela and total and total_int > 1:
        return f"{parcela}/{total}"

    return ""


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
    meio = _normalize_text(data.get("meio_pagamento", ""))
    parcelado = str(data.get("parcelado", "") or "").lower()
    total_parcelas = int(data.get("total_parcelas", 1) or 1)

    if _is_credit_payment(meio) and parcelado == "sim" and total_parcelas > 1:
        return f"{data['parcela_atual']}/{data['total_parcelas']}"

    return ""


def _normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    return "".join(char for char in text if not unicodedata.combining(char))


def _is_credit_payment(meio: str) -> bool:
    return meio.startswith("cr") or "credito" in meio or "cartao" in meio


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

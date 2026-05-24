from typing import Any, Dict, Tuple

import requests
from dateutil.relativedelta import relativedelta

from config import PLANILHA_API_URL
from db import get_month_summary_db, save_transaction
from google_sheets_client import append_transactions, is_configured as google_sheets_configured
from time_utils import now_local


LAST_SAVE_ERROR = ""
SHEET_SAVE_ERRORS = 0
SHEET_QUOTA_ERRORS = 0
LAST_QUOTA_ERROR_AT = ""


def _sanitize_error(exc: Exception) -> str:
    message = str(exc).replace("\n", " ").strip()
    if len(message) > 500:
        message = f"{message[:500]}..."
    return message or exc.__class__.__name__


def _set_last_save_error(message: str) -> None:
    global LAST_SAVE_ERROR
    LAST_SAVE_ERROR = message


def get_last_save_error() -> str:
    return LAST_SAVE_ERROR


def _record_sheet_error(error: str) -> None:
    global SHEET_SAVE_ERRORS, SHEET_QUOTA_ERRORS, LAST_QUOTA_ERROR_AT
    SHEET_SAVE_ERRORS += 1
    if "429" in error or "quota" in error.lower():
        SHEET_QUOTA_ERRORS += 1
        LAST_QUOTA_ERROR_AT = now_local().isoformat(timespec="seconds")


def get_save_metrics() -> Dict[str, Any]:
    return {
        "sheet_save_errors": SHEET_SAVE_ERRORS,
        "sheet_quota_errors": SHEET_QUOTA_ERRORS,
        "last_quota_error_at": LAST_QUOTA_ERROR_AT,
    }


def _dashboard_api_base() -> str:
    if not PLANILHA_API_URL:
        return ""

    base = PLANILHA_API_URL.rstrip("/")
    if not base.endswith("/api"):
        base = f"{base}/api"
    return base


def _save_transactions(items: list[Dict[str, Any]]) -> bool:
    db_saved = False
    sheet_saved = False

    try:
        for data in items:
            save_transaction(data)
        db_saved = True
        print("Transacoes salvas no banco de dados.")
    except Exception as exc:
        error = f"Banco de dados: {_sanitize_error(exc)}"
        _set_last_save_error(error)
        print(f"Falha ao salvar no banco de dados: {error}")

    try:
        if append_transactions(items):
            sheet_saved = True
            print("Transacoes salvas no Google Sheets.")
    except Exception as exc:
        error = f"Google Sheets: {_sanitize_error(exc)}"
        _set_last_save_error(error)
        _record_sheet_error(error)
        print(f"Falha ao salvar no Google Sheets: {error}")

    api_base = _dashboard_api_base()

    if api_base:
        try:
            for data in items:
                response = requests.post(
                    f"{api_base}/transactions",
                    json=data,
                    timeout=15,
                )
                response.raise_for_status()
            print("Transacao salva no dashboard.")
            return sheet_saved
        except Exception as exc:
            error = f"Dashboard API: {_sanitize_error(exc)}"
            _set_last_save_error(error)
            print(f"Falha ao salvar no dashboard: {error}")

    if google_sheets_configured():
        return sheet_saved

    return db_saved


def _normalize_transaction(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    tipo = str(data.get("tipo", "Gasto")).upper()
    tipo = "Receita" if tipo == "RECEITA" else "Gasto"

    try:
        total_parcelas = int(data.get("total_parcelas", 1) or 1)
    except (TypeError, ValueError):
        total_parcelas = 1

    total_parcelas = max(total_parcelas, 1)
    parcelado = "Sim" if total_parcelas > 1 else "Não"

    # Pega o meio de pagamento: tenta "meio_pagamento" primeiro, depois "meio"
    meio = data.get("meio_pagamento") or data.get("meio", "Pix") or "Pix"

    transaction_base = {
        "tipo": tipo,
        "valor": float(data.get("valor", 0) or 0),
        "categoria": data.get("categoria", "Geral") or "Geral",
        "subcategoria": data.get("subcategoria", "") or "",
        "meio_pagamento": meio,
        "parcelado": parcelado,
        "total_parcelas": total_parcelas,
        "descricao": data.get("descricao", "") or "",
        "origem": "WhatsApp",
    }

    return transaction_base, total_parcelas


def save_to_api(data: Dict[str, Any]) -> bool:
    """
    Salva a transacao no dashboard quando PLANILHA_API_URL estiver configurada.
    Se a API externa falhar, preserva a transacao no SQLite local.
    """
    try:
        _set_last_save_error("")
        transaction_base, total_parcelas = _normalize_transaction(data)
        print("Salvando transacao financeira.")
        transactions = []

        if total_parcelas > 1:
            valor_parcela = transaction_base["valor"] / total_parcelas
            data_base = now_local()

            for parcela in range(1, total_parcelas + 1):
                data_parcela = data_base + relativedelta(months=parcela - 1)
                parcela_data = transaction_base.copy()
                parcela_data.update(
                    {
                        "valor": valor_parcela,
                        "parcela_atual": parcela,
                        # Formato ISO completo para compatibilidade com _parse_date do Sheets
                        "data": data_parcela.strftime("%Y-%m-%dT%H:%M:%S.%f"),
                        "descricao": (
                            f"{transaction_base['descricao']} "
                            f"({parcela}/{total_parcelas})"
                        ),
                    }
                )
                transactions.append(parcela_data)

            saved = _save_transactions(transactions)
            return saved if google_sheets_configured() else True

        transaction_base.update(
            {
                "parcela_atual": 1,
                # Formato ISO completo para compatibilidade com _parse_date do Sheets
                "data": now_local().strftime("%Y-%m-%dT%H:%M:%S.%f"),
            }
        )
        saved = _save_transactions([transaction_base])
        return saved if google_sheets_configured() else True

    except Exception as exc:
        error = f"Salvar transacao: {_sanitize_error(exc)}"
        _set_last_save_error(error)
        print(f"Erro ao salvar transacao: {error}")
        return False


def get_month_summary(mes: int = None, ano: int = None) -> tuple:
    try:
        api_base = _dashboard_api_base()
        if api_base:
            now = now_local()
            mes = mes or now.month
            ano = ano or now.year

            response = requests.get(
                f"{api_base}/charts/category",
                params={"mes": mes, "ano": ano},
                timeout=15,
            )
            response.raise_for_status()
            categorias = {
                item.get("name", "Outros"): float(item.get("value", 0) or 0)
                for item in response.json()
            }
            return sum(categorias.values()), categorias

        return get_month_summary_db(mes, ano)
    except Exception as exc:
        print(f"Erro ao buscar resumo mensal: {exc}")
        return 0.0, {}


# Compatibilidade com o nome antigo.
save_to_sheet = save_to_api

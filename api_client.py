from datetime import datetime
from typing import Any, Dict, Tuple

import requests
from dateutil.relativedelta import relativedelta

from config import PLANILHA_API_URL
from db import get_month_summary_db, save_transaction
from google_sheets_client import append_transaction, is_configured as google_sheets_configured


def _dashboard_api_base() -> str:
    if not PLANILHA_API_URL:
        return ""

    base = PLANILHA_API_URL.rstrip("/")
    if not base.endswith("/api"):
        base = f"{base}/api"
    return base


def _save_transaction(data: Dict[str, Any]) -> bool:
    sheet_saved = False

    try:
        if append_transaction(data):
            sheet_saved = True
            print("Transacao salva no Google Sheets.")
    except Exception as exc:
        print(f"Falha ao salvar no Google Sheets: {exc}")

    api_base = _dashboard_api_base()

    if api_base:
        try:
            response = requests.post(
                f"{api_base}/transactions",
                json=data,
                timeout=15,
            )
            response.raise_for_status()
            print("Transacao salva no dashboard.")
            return sheet_saved
        except Exception as exc:
            print(f"Falha ao salvar no dashboard, usando SQLite local: {exc}")

    save_transaction(data)
    return sheet_saved


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
        transaction_base, total_parcelas = _normalize_transaction(data)
        print("Salvando transacao financeira.")
        sheet_results = []

        if total_parcelas > 1:
            valor_parcela = transaction_base["valor"] / total_parcelas
            data_base = datetime.now()

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
                sheet_results.append(_save_transaction(parcela_data))

            return all(sheet_results) if google_sheets_configured() else True

        transaction_base.update(
            {
                "parcela_atual": 1,
                # Formato ISO completo para compatibilidade com _parse_date do Sheets
                "data": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f"),
            }
        )
        sheet_results.append(_save_transaction(transaction_base))
        return all(sheet_results) if google_sheets_configured() else True

    except Exception as exc:
        print(f"Erro ao salvar transacao: {exc}")
        return False


def get_month_summary(mes: int = None, ano: int = None) -> tuple:
    try:
        api_base = _dashboard_api_base()
        if api_base:
            now = datetime.now()
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

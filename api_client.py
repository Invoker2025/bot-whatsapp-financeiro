from datetime import datetime
from typing import Any, Dict, Tuple

import requests
from dateutil.relativedelta import relativedelta

from config import PLANILHA_API_URL
from db import get_month_summary_db, save_transaction
from google_sheets_client import append_transaction


def _dashboard_api_base() -> str:
    if not PLANILHA_API_URL:
        return ""

    base = PLANILHA_API_URL.rstrip("/")
    if not base.endswith("/api"):
        base = f"{base}/api"
    return base


def _save_transaction(data: Dict[str, Any]) -> None:
    try:
        if append_transaction(data):
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
            return
        except Exception as exc:
            print(f"Falha ao salvar no dashboard, usando SQLite local: {exc}")

    save_transaction(data)


def _normalize_transaction(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    tipo = str(data.get("tipo", "Gasto")).upper()
    tipo = "Receita" if tipo == "RECEITA" else "Gasto"

    try:
        total_parcelas = int(data.get("total_parcelas", 1) or 1)
    except (TypeError, ValueError):
        total_parcelas = 1

    total_parcelas = max(total_parcelas, 1)
    parcelado = "Sim" if total_parcelas > 1 else "Não"

    transaction_base = {
        "tipo": tipo,
        "valor": float(data.get("valor", 0) or 0),
        "categoria": data.get("categoria", "Geral") or "Geral",
        "subcategoria": data.get("subcategoria", "") or "",
        "meio_pagamento": data.get("meio", "Pix") or "Pix",
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
        print(f"Salvando transacao: {transaction_base}")

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
                        "data": data_parcela.isoformat(),
                        "descricao": (
                            f"{transaction_base['descricao']} "
                            f"({parcela}/{total_parcelas})"
                        ),
                    }
                )
                _save_transaction(parcela_data)

            return True

        transaction_base.update(
            {
                "parcela_atual": 1,
                "data": datetime.now().isoformat(),
            }
        )
        _save_transaction(transaction_base)
        return True

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

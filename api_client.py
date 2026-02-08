import requests
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Dict, Any
import time

# URL da API da planilha web
API_URL = "https://financial-details-1.preview.emergentagent.com/api/transactions"


def save_to_api(data: Dict[str, Any]) -> bool:
    """
    Envia transação para a API da planilha web
    """
    try:
        # Normaliza o tipo
        tipo = data.get("tipo", "Gasto")
        if tipo.upper() == "GASTO":
            tipo = "Gasto"
        elif tipo.upper() == "RECEITA":
            tipo = "Receita"

        # Normaliza parcelado
        total_parcelas = int(data.get("total_parcelas", 1))
        parcelado = "Sim" if total_parcelas > 1 else "Não"

        # Prepara os dados
        transaction_data = {
            "tipo": tipo,
            "valor": float(data.get("valor", 0)),
            "categoria": data.get("categoria", "Geral"),
            "subcategoria": data.get("subcategoria", "") or "",
            "meio_pagamento": data.get("meio", "Pix"),
            "parcelado": parcelado,
            "parcela_atual": 1,
            "total_parcelas": total_parcelas,
            "descricao": data.get("descricao", ""),
            "origem": "WhatsApp"
        }

        print(f"📤 Enviando para API: {transaction_data}")

        # Se for parcelado, cria múltiplas transações
        if total_parcelas > 1:
            valor_parcela = float(data.get("valor", 0)) / total_parcelas
            data_base = datetime.now()

            for parcela in range(1, total_parcelas + 1):
                parcela_data = transaction_data.copy()
                parcela_data["valor"] = valor_parcela
                parcela_data["parcela_atual"] = parcela
                parcela_data["descricao"] = f"{data.get('descricao', '')} ({parcela}/{total_parcelas})"

                # Cada parcela em um mês diferente!
                data_parcela = data_base + relativedelta(months=parcela - 1)
                parcela_data["data"] = data_parcela.isoformat()

                print(
                    f"📅 Parcela {parcela}/{total_parcelas} → {data_parcela.strftime('%m/%Y')}")

                # Retry logic (tenta 3 vezes)
                for tentativa in range(3):
                    try:
                        response = requests.post(
                            API_URL, json=parcela_data, timeout=30)

                        if response.status_code == 200:
                            print(
                                f"✅ Parcela {parcela}/{total_parcelas} salva!")
                            break
                        else:
                            print(
                                f"❌ Erro ao salvar parcela {parcela}: {response.status_code}")
                            if tentativa < 2:
                                time.sleep(2)
                            else:
                                return False
                    except requests.exceptions.Timeout:
                        print(
                            f"⏱️ Timeout na parcela {parcela}, tentativa {tentativa + 1}/3")
                        if tentativa < 2:
                            time.sleep(2)
                        else:
                            return False

            return True

        else:
            # Transação única
            response = requests.post(
                API_URL, json=transaction_data, timeout=30)

            if response.status_code == 200:
                print(f"✅ Transação salva com sucesso!")
                return True
            else:
                print(f"❌ Erro ao salvar: {response.status_code}")
                return False

    except Exception as e:
        print(f"❌ Erro ao salvar na API: {e}")
        return False


def get_month_summary(mes: int = None, ano: int = None) -> tuple:
    """Busca o resumo do mês da API"""
    try:
        now = datetime.now()
        mes = mes or now.month
        ano = ano or now.year

        summary_url = f"https://financial-details-1.preview.emergentagent.com/api/dashboard/summary?mes={mes}&ano={ano}"
        response = requests.get(summary_url, timeout=30)

        if response.status_code == 200:
            data = response.json()
            total = data.get("despesas", 0) + data.get("contas", 0)

            category_url = f"https://financial-details-1.preview.emergentagent.com/api/charts/category?mes={mes}&ano={ano}"
            cat_response = requests.get(category_url, timeout=30)

            categorias = {}
            if cat_response.status_code == 200:
                cat_data = cat_response.json()
                categorias = {item["name"]: item["value"] for item in cat_data}

            return total, categorias
        else:
            return 0.0, {}

    except Exception as e:
        print(f"❌ Erro ao buscar resumo: {e}")
        return 0.0, {}


# Mantém compatibilidade
save_to_sheet = save_to_api

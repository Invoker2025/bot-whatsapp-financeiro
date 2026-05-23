import json
import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from config import OPENAI_API_KEY

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


client = OpenAI(api_key=OPENAI_API_KEY) if OpenAI and OPENAI_API_KEY else None


# Regras locais ficam antes do GPT para evitar classificacoes instaveis em
# compras comuns. As chaves podem ter acento; a busca normaliza tudo.
MAPEAMENTO_FALLBACK = {
    # Alimentacao
    "mercado livre": ("Shopping", "Mercado Livre"),
    "mercadolivre": ("Shopping", "Mercado Livre"),
    "supermercado": ("Alimentação", "Supermercado"),
    "restaurante": ("Alimentação", "Restaurante"),
    "lanchonete": ("Alimentação", "Lanche"),
    "hamburguer": ("Alimentação", "Lanche"),
    "hambúrguer": ("Alimentação", "Lanche"),
    "hamburger": ("Alimentação", "Lanche"),
    "quentinha": ("Alimentação", "Almoço"),
    "marmita": ("Alimentação", "Almoço"),
    "almoco": ("Alimentação", "Almoço"),
    "almoço": ("Alimentação", "Almoço"),
    "jantar": ("Alimentação", "Jantar"),
    "lanche": ("Alimentação", "Lanche"),
    "pastel": ("Alimentação", "Lanche"),
    "coxinha": ("Alimentação", "Lanche"),
    "salgado": ("Alimentação", "Lanche"),
    "pizza": ("Alimentação", "Lanche"),
    "acai": ("Alimentação", "Lanche"),
    "açaí": ("Alimentação", "Lanche"),
    "sorvete": ("Alimentação", "Lanche"),
    "padaria": ("Alimentação", "Padaria"),
    "pao": ("Alimentação", "Padaria"),
    "pão": ("Alimentação", "Padaria"),
    "cafe": ("Alimentação", "Café"),
    "café": ("Alimentação", "Café"),
    "ifood": ("Alimentação", "iFood"),
    "mercado": ("Alimentação", "Mercado"),
    "hortifruti": ("Alimentação", "Hortifruti"),
    "feira": ("Alimentação", "Feira"),
    "comida": ("Alimentação", "Geral"),
    "bebida": ("Alimentação", "Bebida"),

    # Transporte
    "combustivel": ("Transporte", "Combustível"),
    "combustível": ("Transporte", "Combustível"),
    "gasolina": ("Transporte", "Gasolina"),
    "onibus": ("Transporte", "Ônibus"),
    "ônibus": ("Transporte", "Ônibus"),
    "transporte": ("Transporte", "Geral"),
    "posto": ("Transporte", "Combustível"),
    "uber": ("Transporte", "Uber"),
    "taxi": ("Transporte", "Táxi"),
    "táxi": ("Transporte", "Táxi"),
    "99": ("Transporte", "Aplicativo"),

    # Saude
    "farmacia": ("Saúde", "Farmácia"),
    "farmácia": ("Saúde", "Farmácia"),
    "remedio": ("Saúde", "Remédio"),
    "remédio": ("Saúde", "Remédio"),
    "consulta": ("Saúde", "Consulta"),
    "medico": ("Saúde", "Médico"),
    "médico": ("Saúde", "Médico"),
    "dentista": ("Saúde", "Dentista"),

    # Shopping
    "aliexpress": ("Shopping", "AliExpress"),
    "aliespress": ("Shopping", "AliExpress"),
    "shopee": ("Shopping", "Shopee"),
    "shoope": ("Shopping", "Shopee"),
    "shoppe": ("Shopping", "Shopee"),
    "amazon": ("Shopping", "Amazon"),
    "roupa": ("Shopping", "Vestuário"),
    "tenis": ("Shopping", "Vestuário"),
    "tênis": ("Shopping", "Vestuário"),

    # Contas e moradia
    "condominio": ("Moradia", "Condomínio"),
    "condomínio": ("Moradia", "Condomínio"),
    "aluguel": ("Moradia", "Aluguel"),
    "energia": ("Contas", "Energia"),
    "internet": ("Contas", "Internet"),
    "agua": ("Contas", "Água"),
    "água": ("Contas", "Água"),
    "luz": ("Contas", "Luz"),

    # Assinaturas e lazer
    "assinatura": ("Assinaturas", "Geral"),
    "streaming": ("Assinaturas", "Streaming"),
    "netflix": ("Assinaturas", "Netflix"),
    "spotify": ("Assinaturas", "Spotify"),
    "cinema": ("Lazer", "Cinema"),
    "academia": ("Lazer", "Academia"),
    "lazer": ("Lazer", "Geral"),

    # Educacao e receitas
    "faculdade": ("Educação", "Faculdade"),
    "curso": ("Educação", "Curso"),
    "escola": ("Educação", "Escola"),
    "salario": ("Salário", "Salário"),
    "salário": ("Salário", "Salário"),
    "freelance": ("Receita", "Freelance"),
    "rendimento": ("Receita", "Rendimento"),
}


def normalizar_texto(texto: str) -> str:
    """Remove acentos, deixa minusculo e normaliza espacos."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    return re.sub(r"\s+", " ", texto).strip()


def _keyword_pattern(palavra: str) -> str:
    palavra_norm = re.escape(normalizar_texto(palavra))
    return rf"(?<!\w){palavra_norm}(?!\w)"


def identificar_categoria_fallback(mensagem: str) -> Tuple[str, str]:
    mensagem_norm = normalizar_texto(mensagem)

    regras_ordenadas = sorted(
        MAPEAMENTO_FALLBACK.items(),
        key=lambda item: len(normalizar_texto(item[0])),
        reverse=True,
    )

    for palavra_chave, categoria in regras_ordenadas:
        if re.search(_keyword_pattern(palavra_chave), mensagem_norm):
            return categoria

    return "Outros", "Geral"


def identificar_categoria_gpt(mensagem: str) -> Tuple[str, str]:
    categoria_local, subcategoria_local = identificar_categoria_fallback(mensagem)
    if categoria_local != "Outros":
        return categoria_local, subcategoria_local

    if not client:
        return categoria_local, subcategoria_local

    prompt = f"""
Categorize esta transacao financeira em portugues:
"{mensagem}"

Responda somente JSON valido neste formato:
{{"categoria":"Alimentação","subcategoria":"Lanche"}}

Categorias principais possiveis:
Alimentação, Transporte, Saúde, Lazer, Shopping, Contas, Moradia,
Assinaturas, Educação, Pet, Investimentos, Beleza, Vestuário,
Salário, Receita, Outros.

Exemplos:
- "gastei 42 pastel" -> {{"categoria":"Alimentação","subcategoria":"Lanche"}}
- "gastei 25 marmita" -> {{"categoria":"Alimentação","subcategoria":"Almoço"}}
- "gastei 30 mercado livre" -> {{"categoria":"Shopping","subcategoria":"Mercado Livre"}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Voce categoriza transacoes financeiras e responde apenas JSON valido.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=80,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content or "{}")
        categoria = str(parsed.get("categoria") or "Outros").strip()
        subcategoria = str(parsed.get("subcategoria") or "Geral").strip()
        return categoria or "Outros", subcategoria or "Geral"
    except Exception as exc:
        print(f"[ai_parser] GPT categoria falhou: {exc}")
        return categoria_local, subcategoria_local


def _numero_para_float(valor: str) -> float:
    valor = valor.strip().replace("R$", "").replace(" ", "")

    if "," in valor and "." in valor:
        if valor.rfind(",") > valor.rfind("."):
            valor = valor.replace(".", "").replace(",", ".")
        else:
            valor = valor.replace(",", "")
    elif "," in valor:
        valor = valor.replace(".", "").replace(",", ".")
    elif "." in valor:
        partes = valor.split(".")
        if len(partes) > 1 and all(len(parte) == 3 for parte in partes[1:]):
            valor = valor.replace(".", "")

    return float(valor)


def extrair_valor(mensagem: str) -> float:
    texto = (mensagem or "").replace("R$", " R$ ")
    padrao = re.compile(
        r"(?<!\w)(?:R\$\s*)?((?:\d{1,3}(?:\.\d{3})+|\d+)(?:[,.]\d{1,2})?)(?!\w)",
        re.IGNORECASE,
    )

    for match in padrao.finditer(texto):
        fim = match.end()
        proximo = texto[fim:fim + 12].lower()
        if re.match(r"\s*(x|vezes|parcela|parcelas)\b", proximo):
            continue

        try:
            numero = _numero_para_float(match.group(1))
        except ValueError:
            continue

        if 0.01 <= numero <= 500000 and not (1900 <= numero <= 2100):
            return numero

    return 0.0


def identificar_tipo(mensagem: str) -> str:
    texto = normalizar_texto(mensagem)
    palavras_receita = [
        "recebi",
        "ganhei",
        "receita",
        "salario",
        "entrada",
        "rendimento",
        "freelance",
    ]
    return "RECEITA" if any(palavra in texto for palavra in palavras_receita) else "GASTO"


def identificar_meio_pagamento(mensagem: str) -> str:
    texto = normalizar_texto(mensagem)

    if re.search(r"(?<!\w)pix(?!\w)", texto):
        return "Pix"
    if "debito" in texto or "a vista" in texto:
        return "Débito"
    if "credito" in texto or "cartao de credito" in texto:
        return "Crédito"
    if "dinheiro" in texto:
        return "Dinheiro"

    return "Pendente"


def identificar_parcelamento(mensagem: str, meio: str) -> Tuple[str, int]:
    texto = normalizar_texto(mensagem)
    match = re.search(r"(?:em\s*)?(\d{1,2})\s*(?:x|vezes|parcelas?)\b", texto)

    if match:
        total = max(1, int(match.group(1)))
        return ("Sim" if total > 1 else "Não"), total

    if meio == "Crédito":
        return "Pendente", 1

    return "Não", 1


def _limpar_descricao(mensagem: str) -> str:
    descricao = mensagem.strip()
    descricao = re.sub(r"r\$\s*", " ", descricao, flags=re.IGNORECASE)
    descricao = re.sub(r"\b\d+\s*(?:x|vezes|parcelas?)\b", " ", descricao, flags=re.IGNORECASE)
    descricao = re.sub(r"\b\d+(?:[.,]\d{1,2})?\b", " ", descricao)

    termos = [
        "gastei",
        "gasto",
        "gastar",
        "paguei",
        "pagar",
        "comprei",
        "compra",
        "recebi",
        "ganhei",
        "receita",
        "pagamento",
        "no pix",
        "pix",
        "no crédito",
        "no credito",
        "crédito",
        "credito",
        "no débito",
        "no debito",
        "débito",
        "debito",
        "dinheiro",
        "parcelado",
        "à vista",
        "a vista",
    ]

    for termo in sorted(termos, key=len, reverse=True):
        descricao = re.sub(
            rf"(?<!\w){re.escape(termo)}(?!\w)",
            " ",
            descricao,
            flags=re.IGNORECASE,
        )

    descricao = re.sub(r"\b(?:em|de|do|da|no|na|por|com|para|pra|pro)\b", " ", descricao, flags=re.IGNORECASE)
    descricao = re.sub(r"\s+", " ", descricao).strip(" -.,")

    if not descricao:
        return ""

    return descricao[:1].upper() + descricao[1:]


def parse_message(mensagem: str) -> Dict[str, Any]:
    if not mensagem or not mensagem.strip():
        return {
            "tipo": "GASTO",
            "valor": 0.0,
            "categoria": "Outros",
            "subcategoria": "Geral",
            "meio": "Pendente",
            "descricao": "",
            "parcelado": "Não",
            "total_parcelas": 1,
            "data_compra": datetime.now(),
        }

    tipo = identificar_tipo(mensagem)
    valor = extrair_valor(mensagem)
    categoria, subcategoria = identificar_categoria_gpt(mensagem)
    meio = identificar_meio_pagamento(mensagem)
    parcelado, total_parcelas = identificar_parcelamento(mensagem, meio)
    descricao = _limpar_descricao(mensagem)

    if not descricao:
        descricao = subcategoria if subcategoria != "Geral" else categoria

    if tipo == "RECEITA" and categoria == "Outros":
        categoria = "Salário"
        subcategoria = "Salário"

    return {
        "tipo": tipo,
        "valor": valor,
        "categoria": categoria,
        "subcategoria": subcategoria,
        "meio": meio,
        "descricao": descricao,
        "parcelado": parcelado,
        "total_parcelas": total_parcelas,
        "data_compra": datetime.now(),
    }

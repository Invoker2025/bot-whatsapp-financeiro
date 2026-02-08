import re
from datetime import datetime
from openai import OpenAI
import json

# Cliente OpenAI
client = None
try:
    from config import OPENAI_API_KEY
    if OPENAI_API_KEY:
        client = OpenAI(api_key=OPENAI_API_KEY)
except:
    pass

# Mapeamento fixo (FALLBACK se GPT falhar)
MAPEAMENTO_FALLBACK = {
    'uber': ('Transporte', 'Uber'),
    'taxi': ('Transporte', 'Táxi'),
    '99': ('Transporte', '99'),
    'gasolina': ('Transporte', 'Gasolina'),
    'almoco': ('Alimentação', 'Almoço'),
    'almoço': ('Alimentação', 'Almoço'),
    'jantar': ('Alimentação', 'Jantar'),
    'lanche': ('Alimentação', 'Lanche'),
    'ifood': ('Alimentação', 'iFood'),
    'supermercado': ('Alimentação', 'Supermercado'),
    'farmacia': ('Saúde', 'Farmácia'),
    'farmácia': ('Saúde', 'Farmácia'),
    'remedio': ('Saúde', 'Remédio'),
    'shopee': ('Shopping', 'Shopee'),
    'amazon': ('Shopping', 'Amazon'),
    'cinema': ('Lazer', 'Cinema'),
    'netflix': ('Lazer', 'Netflix'),
    'luz': ('Contas', 'Luz'),
    'agua': ('Contas', 'Água'),
    'internet': ('Contas', 'Internet'),
    'salario': ('Salário', 'Salário'),
    'salário': ('Salário', 'Salário'),
}


def extrair_valor(mensagem: str) -> float:
    """Extrai o valor numérico da mensagem"""
    mensagem_limpa = mensagem.replace('R$', '').replace('r$', '')
    match = re.search(r'(\d+[.,]?\d*)', mensagem_limpa)

    if match:
        valor_str = match.group(1).replace(',', '.')
        return float(valor_str)

    return 0.0


def identificar_tipo(mensagem: str) -> str:
    """Identifica se é Gasto ou Receita"""
    mensagem_lower = mensagem.lower()

    palavras_receita = ['recebi', 'ganhei', 'recebido', 'ganho',
                        'receita', 'salário', 'salario', 'entrada', 'pix de']

    for palavra in palavras_receita:
        if palavra in mensagem_lower:
            return 'Receita'

    return 'Gasto'


def identificar_categoria_fallback(mensagem: str) -> tuple:
    """Usa o mapeamento fixo como fallback"""
    mensagem_lower = mensagem.lower()

    for palavra_chave, (categoria, subcategoria) in MAPEAMENTO_FALLBACK.items():
        if palavra_chave in mensagem_lower:
            return categoria, subcategoria

    return 'Outros', 'Geral'


def identificar_categoria_gpt(mensagem: str) -> tuple:
    """
    USA GPT PARA CATEGORIZAR! 🤖
    Aprende com qualquer categoria que você criar!
    """
    if not client:
        print("⚠️ GPT não disponível, usando fallback")
        return identificar_categoria_fallback(mensagem)

    try:
        categorias_disponiveis = [
            "Alimentação", "Transporte", "Saúde", "Lazer",
            "Shopping", "Contas", "Moradia", "Educação",
            "Pet", "Investimentos", "Beleza", "Vestuário",
            "Salário", "Freelance", "Outros"
        ]

        prompt = f"""Você é um assistente que categoriza gastos financeiros.

Mensagem do usuário: "{mensagem}"

Categorias disponíveis:
{', '.join(categorias_disponiveis)}

Analise a mensagem e retorne APENAS um JSON no formato:
{{"categoria": "nome_da_categoria", "subcategoria": "detalhe_especifico"}}

Exemplos:
- "Gastei 50 de Uber" → {{"categoria": "Transporte", "subcategoria": "Uber"}}
- "Comprei ração pro cachorro" → {{"categoria": "Pet", "subcategoria": "Ração"}}
- "Paguei curso de Python" → {{"categoria": "Educação", "subcategoria": "Curso"}}

Responda APENAS com o JSON, nada mais."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é um assistente de categorização financeira. Responda sempre com JSON válido."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=100
        )

        resposta = response.choices[0].message.content.strip()

        # Remove markdown se houver
        if '```json' in resposta:
            resposta = resposta.split('```json')[1].split('```')[0].strip()
        elif '```' in resposta:
            resposta = resposta.split('```')[1].split('```')[0].strip()

        resultado = json.loads(resposta)
        categoria = resultado.get('categoria', 'Outros')
        subcategoria = resultado.get('subcategoria', 'Geral')

        print(f"🤖 GPT: {categoria} / {subcategoria}")
        return categoria, subcategoria

    except Exception as e:
        print(f"⚠️ GPT falhou: {e}, usando fallback")
        return identificar_categoria_fallback(mensagem)


def identificar_meio_pagamento(mensagem: str) -> str:
    """Identifica o meio de pagamento na mensagem"""
    mensagem_lower = mensagem.lower()

    if 'pix' in mensagem_lower:
        return 'Pix'
    elif 'debito' in mensagem_lower or 'débito' in mensagem_lower:
        return 'Débito'
    elif 'credito' in mensagem_lower or 'crédito' in mensagem_lower:
        return 'Crédito'
    elif 'dinheiro' in mensagem_lower:
        return 'Dinheiro'

    return 'Pendente'


def parse_message(mensagem: str) -> dict:
    """
    Analisa mensagem com INTELIGÊNCIA ARTIFICIAL! 🤖
    """
    tipo = identificar_tipo(mensagem)
    valor = extrair_valor(mensagem)

    # USA GPT! 🚀
    categoria, subcategoria = identificar_categoria_gpt(mensagem)

    meio = identificar_meio_pagamento(mensagem)

    if tipo == 'Receita' and categoria == 'Outros':
        categoria = 'Salário'
        subcategoria = 'Salário'

    return {
        'tipo': tipo.upper(),
        'valor': valor,
        'categoria': categoria,
        'subcategoria': subcategoria,
        'meio': meio,
        'descricao': mensagem,
        'parcelado': 'Não',
        'total_parcelas': 1,
        'data_compra': datetime.now()
    }

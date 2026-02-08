from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from openai import OpenAI
import tempfile
import os
from datetime import datetime

from ai_parser import parse_message
from api_client import save_to_api, get_month_summary
from state import get_pending, set_pending, clear_pending
from config import OPENAI_API_KEY

# ======================================================
# APP + OPENAI
# ======================================================

app = FastAPI()
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ======================================================
# MODELS
# ======================================================


class Message(BaseModel):
    user_id: str
    text: str

# ======================================================
# UTIL - FORMATAÇÃO DE MENSAGEM
# ======================================================


def format_success_msg(data):
    """
    FORMATA A MENSAGEM DE SUCESSO COM EMOJIS
    INCLUINDO CATEGORIA, SUBCATEGORIA E PARCELAS
    """
    tipo = data.get("tipo", "Gasto").upper()
    valor_total = float(data.get("valor", 0))
    total_parcelas = int(data.get("total_parcelas", 1))

    # Ajuste de Emojis e Títulos para Receita vs Gasto
    if tipo == "RECEITA":
        emoji = "📥"
        titulo = "RECEITA REGISTRADA"
        emoji_valor = "💰"
    else:
        emoji = "💸"
        titulo = "GASTO CAPTURADO"
        emoji_valor = "💵"

    msg = f"{emoji} *{titulo}*\n\n"
    msg += f"{emoji_valor} *Valor Total:* R$ {valor_total:.2f}\n"

    # Mostra detalhe de parcelas se houver (Apenas para Gastos)
    if total_parcelas > 1 and tipo == "GASTO":
        valor_parcela = valor_total / total_parcelas
        msg += f"💳 *Parcelas:* {total_parcelas}x de R$ {valor_parcela:.2f}\n"

    msg += f"📂 *Categoria:* {data.get('categoria')}\n"
    msg += f"🏷️ *Subcategoria:* {data.get('subcategoria')}\n"
    msg += f"🏦 *Meio:* {data.get('meio')}\n"
    msg += f"📝 *Descrição:* {data.get('descricao')}\n\n"
    msg += f"🚀 _Planilha atualizada!_"

    return msg

# ======================================================
# TEXTO (WHATSAPP)
# ======================================================


@app.post("/message")
def receive_message(msg: Message):
    user_id = msg.user_id
    pending = get_pending(user_id)

    print(f"DEBUG COMPLETO: {pending}")

    # ----------------------------------
    # 1. Lógica de Estados Pendentes
    # ----------------------------------
    if pending:
        # PASSO: Preencher Meio de Pagamento (PRIMEIRO!)
        meio_pendente = pending.get("meio")
        if not meio_pendente or str(meio_pendente).lower() in ["none", "pendente"]:
            texto = msg.text.strip().title()
            if texto == "1":
                texto = "Pix"
            elif texto == "2":
                texto = "Débito"
            elif texto == "3":
                texto = "Crédito"

            pending["meio"] = texto
            if "Crédito" in texto:
                pending["parcelado"] = "Pendente"
                set_pending(user_id, pending)
                return {
                    "reply": (
                        "💳 *CARTÃO DE CRÉDITO SELECIONADO*\n"
                        "━━━━━━━━━━━━━━━━━━\n\n"
                        "🔄 *Essa compra foi parcelada?*\n\n"
                        "🔹 Digite o *número de parcelas* (ex: `3`)\n"
                        "🔹 Se foi à vista, digite *1*\n\n"
                        "🕒 _Aguardando sua resposta..._"
                    )
                }

            save_to_api(pending)
            msg_final = format_success_msg(pending)
            clear_pending(user_id)
            return {"reply": msg_final}

        # PASSO: Preencher Parcelas (DEPOIS!)
        if str(pending.get("parcelado")).lower() == "pendente":
            try:
                vezes = int(msg.text.strip())
                pending["total_parcelas"] = vezes
                pending["parcelado"] = "Sim" if vezes > 1 else "Não"

                save_to_api(pending)
                msg_final = format_success_msg(pending)
                clear_pending(user_id)
                return {"reply": msg_final}
            except:
                return {"reply": "❌ Por favor, digite apenas o número de parcelas (ex: 3)."}

    # ----------------------------------
    # 2. Comandos (Resumo)
    # ----------------------------------

    texto_limpo = msg.text.strip().lower()
    # Comando: Cancelar
    if texto_limpo in ["/cancelar", "cancelar", "/cancel", "cancel"]:
        clear_pending(user_id)
        return {
            "reply": (
                "❌ *Operação Cancelada*\n\n"
                "Tudo foi limpo! Pode enviar uma nova transação. 😊"
            )
        }
    if texto_limpo == "/resumo":
        try:
            total, cats = get_month_summary()
            resumo_msg = f"📊 *RESUMO DE {datetime.now().month}/{datetime.now().year}*\n\n💰 *Total:* R$ {total:.2f}\n\n📂 *Categorias:*\n"
            for c, v in sorted(cats.items(), key=lambda x: x[1], reverse=True):
                resumo_msg += f"• {c}: R$ {v:.2f}\n"
            return {"reply": resumo_msg}
        except:
            return {"reply": "⚠️ Erro ao gerar resumo."}

    # ----------------------------------
    # 3. Lógica para Nova Mensagem
    # ----------------------------------
    try:
        parsed = parse_message(msg.text)

        # --- BLOCO PARA SALVAR RECEITA DIRETO ---
        if parsed.get("tipo") == "RECEITA":
            parsed["meio"] = parsed.get("meio") if parsed.get(
                "meio") and parsed.get("meio") != "Pendente" else "Pix"
            parsed["subcategoria"] = parsed.get("categoria", "Receita")
            save_to_api(parsed)
            return {"reply": format_success_msg(parsed)}

        # --- SE FALAR "CRÉDITO" NA FRASE, SALVA DIRETO EM 1X ---
        if parsed.get("tipo") == "GASTO" and parsed.get("meio") == "Crédito":
            parsed["parcelado"] = "Não"
            parsed["total_parcelas"] = 1
            save_to_api(parsed)
            return {"reply": format_success_msg(parsed)}

        # FORÇAR RECEITA MANUALMENTE
        palavras_receita = ["recebi", "ganhei",
                            "salário", "salario", "entrada", "pix de"]
        if any(palavra in texto_limpo for palavra in palavras_receita):
            parsed["tipo"] = "RECEITA"
            if parsed["valor"] == 0:
                import re
                numeros = re.findall(r'\d+', texto_limpo)
                if numeros:
                    parsed["valor"] = float(numeros[0])

        print(f"DEBUG IA: {parsed}")

        desc_baixa = str(parsed.get("descricao", "")).lower()

        if "farmácia" in desc_baixa or "remédio" in desc_baixa:
            parsed["categoria"] = "Saúde"
            parsed["subcategoria"] = "Farmácia"
        elif "uber" in desc_baixa or "99" in desc_baixa:
            parsed["categoria"] = "Transporte"
            parsed["subcategoria"] = "Aplicativo"

        if "shopee" in desc_baixa or "shoope" in desc_baixa:
            parsed["categoria"] = "Shopping"
            parsed["subcategoria"] = "Shopee"
        elif "mercado livre" in desc_baixa or "mercadolivre" in desc_baixa:
            parsed["categoria"] = "Shopping"
            parsed["subcategoria"] = "Mercado Livre"
        elif "aliexpress" in desc_baixa or "aliespress" in desc_baixa:
            parsed["categoria"] = "Shopping"
            parsed["subcategoria"] = "AliExpress"
        elif "amazon" in desc_baixa:
            parsed["categoria"] = "Shopping"
            parsed["subcategoria"] = "Amazon"

        if parsed.get("subcategoria") == parsed.get("categoria"):
            detalhe = str(parsed.get("descricao", "")).strip().capitalize()
            if detalhe:
                parsed["subcategoria"] = detalhe

        valor = float(parsed.get("valor", 0))
        if valor <= 0:
            return {"reply": "🤔 Não identifiquei um valor financeiro. Pode repetir?"}

        meio_novo = parsed.get("meio")
        if not meio_novo or str(meio_novo).lower() in ["none", "pendente"]:
            set_pending(user_id, parsed)
            return {
                "reply": (
                    f"✨ *Gasto Capturado!* ✨\n\n"
                    f"💰 *Valor:* `R$ {valor:.2f}`\n"
                    f"📂 *Categoria:* _{parsed.get('categoria')}_\n"
                    f"🏷️ *Subcat:* _{parsed.get('subcategoria')}_\n\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "💳 *Qual o meio de pagamento?*\n\n"
                    "1️⃣  *Pix*\n"
                    "2️⃣  *Débito*\n"
                    "3️⃣  *Crédito*\n\n"
                    "👉 _Responda com o número ou o nome._"
                )
            }

        if "Crédito" in str(parsed.get("meio")) and str(parsed.get("parcelado")).lower() == "pendente":
            set_pending(user_id, parsed)
            return {
                "reply": (
                    "💳 *CARTÃO DE CRÉDITO SELECIONADO*\n"
                    "━━━━━━━━━━━━━━━━━━\n\n"
                    "🔄 *Essa compra foi parcelada?*\n\n"
                    "🔹 Digite o *número de parcelas* (ex: `3`)\n"
                    "🔹 Se foi à vista, digite *1*\n\n"
                    "🕒 _Aguardando sua resposta..._"
                )
            }

        save_to_api(parsed)
        return {"reply": format_success_msg(parsed)}

    except Exception as e:
        print(f"Erro: {e}")
        return {"reply": "❌ Erro interno. Tente novamente."}

# ======================================================
# ÁUDIO (WHATSAPP / WHISPER)
# ======================================================


@app.post("/audio")
async def transcribe_audio(audio: UploadFile = File(...)):
    if not client:
        return {"error": "OpenAI API key não configurada"}

    with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1"
            )
        return {"text": transcription.text}
    except Exception as e:
        print("❌ ERRO STT:", str(e))
        return {"error": "Erro ao transcrever áudio"}
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except:
            pass


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Bot WhatsApp + Planilha Financeira",
        "version": "2.0"
    }

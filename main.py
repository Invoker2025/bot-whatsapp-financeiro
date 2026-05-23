from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from pydantic import BaseModel
from openai import OpenAI
import tempfile
import os
import re
from datetime import datetime

from ai_parser import parse_message
from api_client import save_to_api, get_month_summary
from google_sheets_client import (
    ensure_finance_sheet,
    is_configured as google_sheet_configured,
    reset_finance_template,
)
from state import get_pending, set_pending, clear_pending
from config import OPENAI_API_KEY, WHATSAPP_VERIFY_TOKEN
from twilio_whatsapp import build_twiml_message, normalize_twilio_whatsapp_id, verify_twilio_signature
from whatsapp_cloud import extract_text_messages, send_whatsapp_text, verify_signature

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
                # Validação: mínimo 1, máximo 48 parcelas
                if vezes < 1:
                    return {"reply": "❌ Mínimo é 1 parcela (à vista). Digite um número válido."}
                if vezes > 48:
                    return {"reply": "❌ Máximo é 48 parcelas. Digite um número menor."}
                pending["total_parcelas"] = vezes
                pending["parcelado"] = "Sim" if vezes > 1 else "Não"

                save_to_api(pending)
                msg_final = format_success_msg(pending)
                clear_pending(user_id)
                return {"reply": msg_final}
            except ValueError:
                return {"reply": "❌ Por favor, digite apenas o *número* de parcelas (ex: `3`)."}
            except Exception:
                return {"reply": "❌ Erro ao processar parcelas. Tente novamente."}

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

        # Se a mensagem ja trouxe parcelas, preserva. Se so disse "credito",
        # deixa o fluxo perguntar se foi parcelado.
        if (
            parsed.get("tipo") == "GASTO"
            and parsed.get("meio") == "Crédito"
            and str(parsed.get("parcelado", "")).lower() != "pendente"
        ):
            save_to_api(parsed)
            return {"reply": format_success_msg(parsed)}

        # FORÇAR RECEITA MANUALMENTE (fallback caso IA não identifique)
        palavras_receita = ["recebi", "ganhei",
                            "salário", "salario", "entrada", "pix de"]
        if any(palavra in texto_limpo for palavra in palavras_receita):
            parsed["tipo"] = "RECEITA"
            if parsed["valor"] == 0:
                # Tenta extrair valor com regex melhorada
                numeros = re.findall(r'(?:R\$\s*)?([\d]+(?:[.,]\d{1,2})?)', texto_limpo)
                for num_str in numeros:
                    try:
                        num = float(num_str.replace(",", "."))
                        if 1 <= num <= 50000:
                            parsed["valor"] = num
                            break
                    except ValueError:
                        continue

        print(f"DEBUG IA: {parsed}")

        # Sobrescrita manual de categorias baseadas em palavras-chave na descrição
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
# WHATSAPP CLOUD API
# ======================================================


@app.get("/webhook")
def verify_whatsapp_webhook(
    hub_mode: str = Query("", alias="hub.mode"),
    hub_challenge: str = Query("", alias="hub.challenge"),
    hub_verify_token: str = Query("", alias="hub.verify_token"),
):
    if (
        hub_mode == "subscribe"
        and WHATSAPP_VERIFY_TOKEN
        and hub_verify_token == WHATSAPP_VERIFY_TOKEN
    ):
        return Response(content=hub_challenge, media_type="text/plain")

    raise HTTPException(status_code=403, detail="Invalid verify token")


def process_whatsapp_cloud_text(user_id: str, text: str):
    """
    Processa mensagem recebida do webhook WhatsApp Cloud.
    Com try/except para garantir que erros não sejam engolidos silenciosamente
    pelo BackgroundTasks e que o usuário receba uma resposta de erro.
    """
    try:
        response = receive_message(Message(user_id=user_id, text=text))
        reply = response.get("reply") if isinstance(response, dict) else None
        if reply:
            send_whatsapp_text(user_id, reply)
    except Exception as e:
        print(f"❌ Erro no processamento webhook WhatsApp Cloud: {e}")
        try:
            send_whatsapp_text(
                user_id,
                "❌ Ocorreu um erro ao processar sua mensagem. Tente novamente."
            )
        except Exception:
            pass


@app.post("/webhook")
async def receive_whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()
    signature = request.headers.get("x-hub-signature-256")

    if not verify_signature(raw_body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = await request.json()
    for user_id, text in extract_text_messages(payload):
        background_tasks.add_task(process_whatsapp_cloud_text, user_id, text)

    return {"status": "ok"}


# ======================================================
# TWILIO WHATSAPP
# ======================================================


@app.post("/twilio/whatsapp")
async def receive_twilio_whatsapp(request: Request):
    form = await request.form()
    params = {key: str(value) for key, value in form.items()}
    signature = request.headers.get("x-twilio-signature")

    if not verify_twilio_signature(str(request.url), params, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    user_id = normalize_twilio_whatsapp_id(params.get("From", ""))
    text = (params.get("Body") or "").strip()

    if not user_id:
        raise HTTPException(status_code=400, detail="Missing sender")

    if not text:
        reply = "Envie uma mensagem de texto com o gasto. Ex: gastei 25 no almoco pix"
    else:
        try:
            response = receive_message(Message(user_id=user_id, text=text))
            reply = response.get("reply") if isinstance(response, dict) else "Processado."
        except Exception as e:
            print(f"❌ Erro no webhook Twilio: {e}")
            reply = "❌ Erro interno. Tente novamente."

    return Response(content=build_twiml_message(reply), media_type="application/xml")


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
        "version": "2.0",
        "google_sheet_configured": google_sheet_configured(),
    }


@app.api_route("/sheet/setup", methods=["GET", "POST"])
def setup_sheet():
    if not google_sheet_configured():
        raise HTTPException(status_code=400, detail="GOOGLE_SHEET_ID nao configurado")

    try:
        ensure_finance_sheet()
    except Exception as exc:
        print(f"Erro ao configurar planilha: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    return {"status": "ok", "message": "Planilha configurada"}


@app.api_route("/sheet/reset-template", methods=["GET", "POST"])
def reset_sheet_template():
    if not google_sheet_configured():
        raise HTTPException(status_code=400, detail="GOOGLE_SHEET_ID nao configurado")

    try:
        reset_finance_template()
    except Exception as exc:
        print(f"Erro ao resetar template da planilha: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "status": "ok",
        "message": "Template limpo. Abas antigas foram apagadas.",
    }

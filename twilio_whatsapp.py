import base64
import hashlib
import hmac
import re
from html import escape
from typing import Dict, Optional

import requests

from config import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_PUBLIC_WEBHOOK_URL,
    TWILIO_WHATSAPP_FROM,
)


def normalize_twilio_whatsapp_id(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def build_twiml_message(body: str) -> str:
    return f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response><Message>{escape(body)}</Message></Response>"


def _signature_url(request_url: str) -> str:
    return TWILIO_PUBLIC_WEBHOOK_URL or request_url


def verify_twilio_signature(
    request_url: str,
    params: Dict[str, str],
    signature_header: Optional[str],
) -> bool:
    if not TWILIO_AUTH_TOKEN:
        print("TWILIO_AUTH_TOKEN nao configurado; assinatura Twilio rejeitada.")
        return False

    if not signature_header:
        return False

    data = _signature_url(request_url)
    for key in sorted(params):
        data += key + params[key]

    digest = hmac.new(
        TWILIO_AUTH_TOKEN.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    expected = base64.b64encode(digest).decode("utf-8")

    return hmac.compare_digest(expected, signature_header)


def send_twilio_whatsapp_text(to: str, body: str) -> bool:
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_WHATSAPP_FROM:
        print("Twilio outbound nao configurado; lembrete nao enviado.")
        return False

    to_digits = normalize_twilio_whatsapp_id(to)
    if not to_digits:
        return False

    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    data = {
        "From": TWILIO_WHATSAPP_FROM,
        "To": f"whatsapp:+{to_digits}",
        "Body": body,
    }

    try:
        response = requests.post(
            url,
            data=data,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            timeout=15,
        )
        response.raise_for_status()
        return True
    except Exception as exc:
        print(f"Erro ao enviar lembrete pelo Twilio: {exc}")
        return False

import base64
import hashlib
import hmac
import re
from html import escape
from typing import Dict, Optional

from config import TWILIO_AUTH_TOKEN, TWILIO_PUBLIC_WEBHOOK_URL


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
        return True

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

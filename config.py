import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI API key used by categorization and audio transcription.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Dashboard API URL. Configure it ending with /api, for example:
# https://seu-dashboard.onrender.com/api
PLANILHA_API_URL = os.getenv("PLANILHA_API_URL", "").rstrip("/")

# WhatsApp Cloud API settings.
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v25.0")
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")

# Twilio WhatsApp settings.
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PUBLIC_WEBHOOK_URL = os.getenv("TWILIO_PUBLIC_WEBHOOK_URL", "").rstrip("/")

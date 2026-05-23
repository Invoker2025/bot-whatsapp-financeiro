import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI API key used by categorization and audio transcription.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# App timezone used when writing dates to the spreadsheet.
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "America/Fortaleza")

# Dashboard API URL. Configure it ending with /api, for example:
# https://seu-dashboard.onrender.com/api
PLANILHA_API_URL = os.getenv("PLANILHA_API_URL", "").rstrip("/")

# Google Sheets settings. Create/share a sheet and paste its ID here.
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/etc/secrets/google-creds.json"),
)

# WhatsApp Cloud API settings.
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v25.0")
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")

# Twilio WhatsApp settings.
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")
TWILIO_PUBLIC_WEBHOOK_URL = os.getenv("TWILIO_PUBLIC_WEBHOOK_URL", "").rstrip("/")
PENDING_REMINDER_SECONDS = int(os.getenv("PENDING_REMINDER_SECONDS", "120"))

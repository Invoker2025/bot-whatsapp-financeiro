import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI API Key (para transcrição de áudio via Whisper)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# URL da API da Planilha
API_URL = "https://financial-details-1.preview.emergentagent.com/api/transactions"

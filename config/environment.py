import os
from dotenv import load_dotenv

load_dotenv()

os.environ.pop("GOOGLE_API_KEY", None)

class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        print("⚠️ Alerta: GEMINI_API_KEY não encontrada no arquivo .env")

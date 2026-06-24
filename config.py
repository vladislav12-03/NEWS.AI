import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = os.getenv(
    "GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions"
)
GROQ_MODEL = os.getenv(
    "GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"
)

TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE")

DONATE_URL = os.getenv("DONATE_URL", "")

if not BOT_TOKEN:
    raise ValueError("Не установлен BOT_TOKEN в переменных окружения!")

if not ADMIN_ID:
    raise ValueError("Не установлен ADMIN_ID в переменных окружения!")

if not GROQ_API_KEY:
    raise ValueError("Не установлен GROQ_API_KEY в переменных окружения!")

if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
    raise ValueError(
        "Не установлены TELEGRAM_API_ID или TELEGRAM_API_HASH в переменных окружения!"
    )

if not TELEGRAM_PHONE:
    raise ValueError("Не установлен TELEGRAM_PHONE в переменных окружения!")

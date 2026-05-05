import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "8789867141:AAGVDeakEiDEB1eiiwbXfxhVK1zDzusYVmU")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "7165975728").split(",")))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
USERS_DIR = os.path.join(DATA_DIR, "users")
LOGS_DIR = os.path.join(DATA_DIR, "logs")
DB_PATH = os.path.join(DATA_DIR, "bot.db")
USERS_JSON_PATH = os.path.join(DATA_DIR, "users.json")

MAX_FILE_SIZE_MB = 20
MAX_FILES_PER_USER = 10
MAX_PROCESSES_PER_USER_FREE = 2
MAX_PROCESSES_PER_USER_PREMIUM = 10
MAX_STORAGE_MB_FREE = 50
MAX_STORAGE_MB_PREMIUM = 500

SCRIPT_TIMEOUT = 3600
LOG_MAX_LINES = 500

FLASK_PORT = int(os.getenv("BOT_PORT", 5000))

PACKAGE_MAP = {
    "telebot": "pyTelegramBotAPI",
    "telegram": "python-telegram-bot",
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "sklearn": "scikit-learn",
    "bs4": "beautifulsoup4",
    "yaml": "PyYAML",
    "dotenv": "python-dotenv",
    "pymongo": "pymongo",
    "psycopg2": "psycopg2-binary",
    "aiohttp": "aiohttp",
    "flask": "Flask",
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "requests": "requests",
    "pydantic": "pydantic",
    "sqlalchemy": "SQLAlchemy",
    "discord": "discord.py",
    "tweepy": "tweepy",
    "instagrapi": "instagrapi",
    "selenium": "selenium",
    "playwright": "playwright",
    "numpy": "numpy",
    "pandas": "pandas",
    "matplotlib": "matplotlib",
    "scipy": "scipy",
    "tensorflow": "tensorflow",
    "torch": "torch",
    "keras": "keras",
    "transformers": "transformers",
    "cryptography": "cryptography",
    "jwt": "PyJWT",
    "celery": "celery",
    "redis": "redis",
    "motor": "motor",
    "aiogram": "aiogram",
    "pyrogram": "pyrogram",
    "telethon": "Telethon",
    "googletrans": "googletrans==4.0.0-rc1",
    "gtts": "gTTS",
    "pyttsx3": "pyttsx3",
    "speech_recognition": "SpeechRecognition",
    "paramiko": "paramiko",
    "fabric": "fabric",
    "boto3": "boto3",
    "stripe": "stripe",
    "twilio": "twilio",
    "sendgrid": "sendgrid",
}

for d in [DATA_DIR, USERS_DIR, LOGS_DIR]:
    os.makedirs(d, exist_ok=True)

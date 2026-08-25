"""Конфигурация проекта."""
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()

def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default

def _env_bool(key: str, default: bool) -> bool:
    val = _env(key, str(default)).lower()
    return val in ("1", "true", "yes", "on")


BOT_TOKEN: str = _env("BOT_TOKEN")

ADMIN_ID: int = _env_int("ADMIN_ID", 0)
ADMIN_SECRET: str = _env("ADMIN_SECRET")

PROXY_URL: str = _env("PROXY_URL")

# Жёстко задаём модель, чтобы исключить влияние переменной окружения
WHISPER_MODEL: str = "small"
WHISPER_DEVICE: str = _env("WHISPER_DEVICE", "cpu")
WHISPER_LANGUAGE: str = _env("WHISPER_LANGUAGE", "auto")
WHISPER_VAD_FILTER: bool = _env_bool("WHISPER_VAD_FILTER", True)

LLM_PROVIDER: str = _env("LLM_PROVIDER", "none")
LLM_API_KEY: str = _env("LLM_API_KEY")
LLM_MODEL: str = _env("LLM_MODEL")

FREE_MONTHLY_LIMIT: int = _env_int("FREE_MONTHLY_LIMIT", 3)
FREE_MAX_MINUTES: int = _env_int("FREE_MAX_MINUTES", 15)
PRO_TRIAL_HOURS: int = _env_int("PRO_TRIAL_HOURS", 24)

BASE_DIR: str = "/app"
DATA_DIR: str = os.path.join(BASE_DIR, "data")
MEDIA_DIR: str = os.path.join(BASE_DIR, "media")
DB_PATH: str = os.path.join(DATA_DIR, "bot.sqlite")

if not BOT_TOKEN:
    raise RuntimeError("❌ В .env не заполнен BOT_TOKEN.")

# Выводим в лог значение модели (для отладки)
logger.info(f"🔧 WHISPER_MODEL = {WHISPER_MODEL}")

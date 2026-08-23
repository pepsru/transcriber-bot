"""Работа с аудио: проверка длительности и конвертация через ffmpeg."""
import asyncio
import os
from app import config


async def get_duration(file_path: str) -> float:
    """Возвращает длительность файла в секундах (через ffprobe).
    Если ffprobe не смог прочитать файл — вернёт 0.0.
    """
    if not os.path.exists(file_path):
        return 0.0
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return 0.0
        return float(stdout.decode().strip())
    except Exception:
        return 0.0


async def check_duration_limit(file_path: str, user_id: int):
    """Проверяет, не превышает ли длительность лимит.
    Возвращает (разрешено: bool, длительность_в_сек: float, причина_отказа: str | None).
    Админу всегда разрешено.
    """
    duration = await get_duration(file_path)
    duration_min = duration / 60.0

    if user_id == config.ADMIN_ID:
        return True, duration, None

    if duration_min > config.FREE_MAX_MINUTES:
        return False, duration, (
            f"🚫 Файл слишком длинный: {duration_min:.1f} мин.\n"
            f"Бесплатный лимит: до {config.FREE_MAX_MINUTES} мин.\n\n"
            f"🎁 С активным PRO ограничений по длительности нет."
        )

    return True, duration, None


async def convert_to_wav(input_path: str, output_path: str) -> bool:
    """Конвертирует файл в 16 кГц моно WAV (формат, который любит Whisper).
    Возвращает True при успехе, False при ошибке.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y",
            "-i", input_path,
            "-ar", "16000",      # 16 кГц
            "-ac", "1",          # моно
            "-c:a", "pcm_s16le", # 16-bit PCM
            output_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, _ = await proc.communicate()
        return proc.returncode == 0 and os.path.exists(output_path)
    except Exception:
        return False

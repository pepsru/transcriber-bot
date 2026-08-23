import asyncio
import logging
import os
import tempfile
from typing import Optional

from faster_whisper import WhisperModel

from app import config

logger = logging.getLogger(__name__)

# Глобальный объект модели (загружается один раз)
_model: Optional[WhisperModel] = None


def _load_model() -> WhisperModel:
    """
    Загружает модель Whisper с использованием параметров из config.
    """
    global _model
    if _model is not None:
        return _model

    logger.info(f"📥 Загружаю модель Whisper '{config.WHISPER_MODEL}'...")
    _model = WhisperModel(
        model_size_or_path=config.WHISPER_MODEL,
        device=config.WHISPER_DEVICE,
        compute_type="int8",          # оптимально для CPU
        cpu_threads=4,                # можно изменить под ваш сервер
        num_workers=1,
    )
    logger.info("✅ Модель загружена")
    return _model


async def transcribe(audio_path: str) -> str:
    """
    Асинхронно транскрибирует аудиофайл и возвращает текст.
    """
    loop = asyncio.get_event_loop()
    model = await loop.run_in_executor(None, _load_model)

    # Параметры транскрипции из конфига
    language = config.WHISPER_LANGUAGE if config.WHISPER_LANGUAGE != "auto" else None
    vad_filter = config.WHISPER_VAD_FILTER

    # Запускаем транскрипцию в потоке
    segments, info = await loop.run_in_executor(
        None,
        lambda: model.transcribe(
            audio_path,
            language=language,
            vad_filter=vad_filter,
            beam_size=5,
            best_of=5,
            temperature=0.0,
        ),
    )

    # Собираем текст из всех сегментов
    result_text = " ".join(segment.text for segment in segments)

    if not result_text.strip():
        logger.warning("⚠️ Транскрипция вернула пустой результат")
        return ""

    logger.info(f"✅ Транскрипция завершена. Длина текста: {len(result_text)} символов")
    return result_text.strip()

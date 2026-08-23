"""Распознавание речи через faster-whisper."""
import asyncio
import logging
import os

from app import config

log = logging.getLogger(__name__)

_model = None
_model_lock = asyncio.Lock()


def _load_model():
    global _model
    if _model is not None:
        return _model
    log.info("📥 Загружаю модель Whisper '%s'...", config.WHISPER_MODEL)
    from faster_whisper import WhisperModel
    _model = WhisperModel(
        config.WHISPER_MODEL,
        device=config.WHISPER_DEVICE,
        compute_type="int8",
    )
    log.info("✅ Модель загружена")
    return _model


def _do_transcribe(model, audio_path: str, use_vad: bool):
    """Синхронная функция распознавания."""
    language = config.WHISPER_LANGUAGE
    if language == "auto":
        language = None

    segments_iter, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=5,
        vad_filter=use_vad,
        vad_parameters=dict(
            min_silence_duration_ms=500,
            speech_pad_ms=300,
        ) if use_vad else None,
    )
    segments = []
    text_parts = []
    for seg in segments_iter:
        segments.append({
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
        })
        text_parts.append(seg.text.strip())
    return " ".join(text_parts), segments, info


async def transcribe(audio_path: str) -> dict:
    """Распознаёт речь. Умный fallback: если VAD удалил всё — пробуем без VAD."""
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Файл не найден: {audio_path}")

    async with _model_lock:
        model = await asyncio.to_thread(_load_model)

    # 1. Первая попытка: с VAD (если включён в конфиге)
    use_vad = config.WHISPER_VAD_FILTER
    text, segments, info = await asyncio.to_thread(_do_transcribe, model, audio_path, use_vad)

    # 2. Умный fallback: если VAD был включён, но текст пустой — пробуем без VAD
    if use_vad and not text.strip():
        log.info("⚠️ VAD удалил всё аудио, пробую без VAD...")
        text, segments, info = await asyncio.to_thread(_do_transcribe, model, audio_path, False)

    if not text.strip():
        return {"text": "[Речь не обнаружена]", "segments": []}

    return {"text": text, "segments": segments}

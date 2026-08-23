"""Озвучка текста через edge-tts (Microsoft, бесплатно, русский голос)."""
import logging
import os

log = logging.getLogger(__name__)

RU_VOICE = "ru-RU-SvetlanaNeural"


async def text_to_speech(text: str, output_path: str, max_chars: int = 3000) -> bool:
    """Генерирует mp3 из текста. Обрезает до max_chars.
    Возвращает True при успехе.
    """
    import edge_tts

    if not text or text == "[Речь не обнаружена]":
        return False

    if len(text) > max_chars:
        text = text[:max_chars] + " ... (текст обрезан для озвучки)"

    try:
        communicate = edge_tts.Communicate(text, RU_VOICE)
        await communicate.save(output_path)
        return os.path.exists(output_path)
    except Exception as e:
        log.error("Ошибка TTS: %s", e)
        return False

"""Генерация мыслей, конспекта, вопросов через LLM."""
import logging
from app.core import llm

log = logging.getLogger(__name__)


def _format_segments(segments: list, max_segments: int = 200) -> str:
    """Форматирует сегменты с таймкодами. Обрезает до max_segments."""
    if not segments:
        return "[Нет данных]"
    segments = segments[:max_segments]
    lines = []
    for seg in segments:
        minutes = int(seg["start"] // 60)
        seconds = int(seg["start"] % 60)
        timecode = f"{minutes:02d}:{seconds:02d}"
        lines.append(f"[{timecode}] {seg['text']}")
    return "\n".join(lines)


def _is_truncated(text: str) -> bool:
    """Проверяет, обрезан ли ответ (обрывается на цифре или слишком короткий)."""
    if not text or len(text) < 100:
        return True
    stripped = text.rstrip()
    # Ответ обрывается, если заканчивается на "N." или "N" без текста
    if stripped.endswith((".", ":")):
        last_line = stripped.split("\n")[-1].strip()
        # Если последняя строка — это просто цифра с точкой (например "4.")
        if last_line.replace(".", "").isdigit():
            return True
    return False


async def generate_thoughts(text: str) -> str:
    system = (
        "Ты — эксперт по анализу контента. Выдели 5-7 главных мыслей из текста. "
        "Каждую мысль оформи как маркированный список (•). "
        "Отвечай на русском языке, кратко и по существу. "
        "Отвечай полно, не сокращай ответ."
    )
    user = f"Текст для анализа:\n\n{text[:15000]}"
    result = await llm.ask_llm(system, user, max_tokens=1500)
    return f"📌 <b>Главные мысли:</b>\n\n{result}"


async def generate_summary(text: str) -> str:
    system = (
        "Ты — эксперт по конспектированию. Создай структурированный конспект текста. "
        "Разбей на логические разделы с заголовками (используй **жирный** для заголовков). "
        "Сохраняй ключевые детали и факты. Отвечай на русском языке. "
        "Отвечай полно, не сокращай ответ."
    )
    user = f"Текст для конспекта:\n\n{text[:15000]}"
    result = await llm.ask_llm(system, user, max_tokens=2500)
    return f"📝 <b>Конспект:</b>\n\n{result}"


async def generate_questions(segments: list) -> str:
    if not segments:
        return "❓ <b>Вопросы:</b>\n\n[Нет данных для анализа]"

    formatted = _format_segments(segments)
    system = (
        "Ты — эксперт по анализу интервью. Сгенерируй РОВНО 5-7 вопросов, "
        "которые можно задать спикеру для уточнения или углубления темы. "
        "К каждому вопросу добавь таймкод [MM:SS], к которому он относится. "
        "Формат:\n"
        "1. [02:15] Полный текст первого вопроса?\n"
        "2. [05:30] Полный текст второго вопроса?\n"
        "3. [08:45] Полный текст третьего вопроса?\n"
        "...\n"
        "ВАЖНО: Отвечай полно, дай все 5-7 вопросов, не сокращай ответ. "
        "Каждый вопрос должен быть развёрнутым (1-2 предложения). "
        "Отвечай на русском языке."
    )
    user = f"Транскрипт с таймкодами:\n\n{formatted}"
    result = await llm.ask_llm(system, user, max_tokens=2500)
    
    # Проверка на обрезанный ответ
    if _is_truncated(result):
        warning = (
            "\n\n⚠️ <i>Ответ был обрезан из-за ограничений бесплатной модели. "
            "Для полного ответа подключи платный LLM-провайдер в .env.</i>"
        )
        return f"❓ <b>Вопросы с таймкодами:</b>\n\n{result}{warning}"
    
    return f"❓ <b>Вопросы с таймкодами:</b>\n\n{result}"

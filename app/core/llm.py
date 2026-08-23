"""Универсальный интерфейс для LLM."""
import logging
from app import config

log = logging.getLogger(__name__)

BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "openrouter": "https://openrouter.ai/api/v1",
}

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "groq": "llama-3.3-70b-versatile",
    "gemini": "gemini-2.0-flash",
    "openrouter": "meta-llama/llama-3.1-8b-instruct:free",
}


def _get_client():
    if config.LLM_PROVIDER == "none" or not config.LLM_API_KEY:
        return None

    base_url = BASE_URLS.get(config.LLM_PROVIDER)
    if not base_url:
        log.warning("Неизвестный LLM_PROVIDER: %s", config.LLM_PROVIDER)
        return None

    from openai import AsyncOpenAI

    return AsyncOpenAI(
        api_key=config.LLM_API_KEY,
        base_url=base_url,
        timeout=180,
    )


async def ask_llm(system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> str:
    """Возвращает текст ответа или строку с описанием ошибки (НЕ None)."""
    client = _get_client()
    if not client:
        return "🤖 <b>Функция недоступна</b>\n\nНастрой LLM-ключ в .env"

    model = config.LLM_MODEL or DEFAULT_MODELS.get(config.LLM_PROVIDER, "gpt-4o-mini")

    try:
        MAX_PROMPT_CHARS = 50000
        if len(user_prompt) > MAX_PROMPT_CHARS:
            log.warning("⚠️ Prompt слишком длинный (%d), обрезаем до %d",
                        len(user_prompt), MAX_PROMPT_CHARS)
            user_prompt = user_prompt[:MAX_PROMPT_CHARS] + "\n\n[...текст обрезан...]"

        log.info("📤 Отправляю запрос в LLM (prompt: %d символов, max_tokens: %d)",
                 len(user_prompt), max_tokens)

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.7,
        )
        result = response.choices[0].message.content.strip()
        log.info("✅ Ответ получен (%d символов)", len(result))
        return result
    except Exception as e:
        error_text = str(e)
        log.error("❌ Ошибка LLM (%s): %s", config.LLM_PROVIDER, error_text)
        short_err = error_text[:200]
        return (
            f"⚠️ <b>Ошибка генерации</b>\n\n"
            f"Не удалось получить ответ от LLM.\n"
            f"<code>{short_err}</code>\n\n"
            f"Попробуй ещё раз или отправь более короткий файл."
        )

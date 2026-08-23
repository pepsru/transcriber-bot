"""Обработка callback-кнопок (inline keyboard) с прогресс-индикатором."""
import asyncio
import logging
import os
from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile

from app import config
from app.core import summarizer, tts

log = logging.getLogger(__name__)
router = Router()

_transcriptions = {}
# Защита от повторных нажатий: message_id -> задача
_active_tasks = {}


def save_transcription(message_id: int, text: str, segments: list):
    _transcriptions[message_id] = {"text": text, "segments": segments}


async def _update_progress(msg, title: str, started_at: datetime):
    """Обновляет сообщение статуса каждые 5 секунд."""
    dots = ""
    try:
        while True:
            await asyncio.sleep(5)
            elapsed = int((datetime.utcnow() - started_at).total_seconds())
            dots = (dots + ".") if len(dots) < 3 else ""
            new_text = f"{title}\n\n⏱️ Прошло: <b>{elapsed}</b> сек {dots}"
            try:
                await msg.edit_text(new_text, parse_mode="HTML")
            except Exception:
                # Сообщение могло быть удалено/изменено пользователем
                break
    except asyncio.CancelledError:
        pass


async def _with_progress(callback: CallbackQuery, title: str, action):
    """Запускает действие с отображением прогресса.
    action — async функция, возвращающая результат.
    Возвращает результат или None при отмене.
    """
    # Защита от повторных нажатий
    if callback.message.message_id in _active_tasks:
        await callback.answer("⏳ Уже обрабатываю предыдущий запрос", show_alert=True)
        return None

    await callback.answer()

    # Отправляем статус-сообщение
    status_msg = await callback.message.answer(f"{title}\n\n⏱️ Прошло: <b>0</b> сек", parse_mode="HTML")

    started_at = datetime.utcnow()
    progress_task = asyncio.create_task(_update_progress(status_msg, title, started_at))
    _active_tasks[callback.message.message_id] = progress_task

    try:
        # Запускаем само действие (LLM или TTS)
        result = await action()
        return result, status_msg
    except asyncio.CancelledError:
        return None, status_msg
    except Exception as e:
        log.error("Ошибка в действии %s: %s", title, e)
        return None, status_msg
    finally:
        progress_task.cancel()
        try:
            await progress_task
        except asyncio.CancelledError:
            pass
        _active_tasks.pop(callback.message.message_id, None)


@router.callback_query(F.data.startswith("action:"))
async def handle_action(callback: CallbackQuery):
    action = callback.data.split(":")[1]
    message_id = callback.message.message_id

    trans = _transcriptions.get(message_id)
    if not trans:
        await callback.answer("⚠️ Данные устарели. Отправь голосовое снова.", show_alert=True)
        return

    # Заголовки прогресса для каждого действия
    titles = {
        "thoughts": "📌 <b>Генерирую главные мысли...</b>",
        "summary": "📝 <b>Составляю конспект...</b>",
        "questions": "❓ <b>Формирую вопросы с таймкодами...</b>",
        "audio": "🎧 <b>Озвучиваю текст...</b>",
    }

    title = titles.get(action, "⏳ <b>Обрабатываю запрос...</b>")

    # Определяем действие
    if action == "thoughts":
        action_fn = lambda: summarizer.generate_thoughts(trans["text"])
    elif action == "summary":
        action_fn = lambda: summarizer.generate_summary(trans["text"])
    elif action == "questions":
        action_fn = lambda: summarizer.generate_questions(trans["segments"])
    elif action == "audio":
        action_fn = lambda: _generate_audio(callback, trans["text"])
    else:
        await callback.message.answer("❌ Неизвестное действие")
        return

    # Выполняем с прогрессом
    wrapper = _with_progress(callback, title, action_fn)
    result_data = await wrapper
    if result_data is None:
        return
    result, status_msg = result_data

    # Удаляем статус-сообщение
    try:
        await status_msg.delete()
    except Exception:
        pass

    # Отправляем результат
    if isinstance(result, dict) and result.get("type") == "audio":
        # Озвучка — отправляем аудиофайл
        await callback.message.answer_audio(
            FSInputFile(result["path"]),
            title="Озвучка транскрипции",
        )
        try:
            os.remove(result["path"])
        except OSError:
            pass
    elif isinstance(result, str):
        # Текстовый ответ
        await _send(callback, result)
    else:
        await callback.message.answer("❌ Не удалось получить результат")


async def _generate_audio(callback: CallbackQuery, text: str):
    """Генерирует аудиофайл и возвращает путь."""
    tts_path = os.path.join(config.MEDIA_DIR, f"tts_{callback.message.message_id}.mp3")
    ok = await tts.text_to_speech(text, tts_path)
    if ok:
        return {"type": "audio", "path": tts_path}
    else:
        return (
            "❌ Не удалось озвучить текст.\n"
            "Возможно, нет доступа к сервису TTS (нужен VPN/proxy)."
        )


async def _send(callback: CallbackQuery, result: str):
    """Отправляет текст, разбивая при необходимости."""
    if len(result) > 4000:
        chunks = [result[i:i+4000] for i in range(0, len(result), 4000)]
        for chunk in chunks:
            await callback.message.answer(chunk)
    else:
        await callback.message.answer(result)

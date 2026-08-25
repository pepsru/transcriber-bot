import asyncio
import logging
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from typing import List

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.exceptions import MessageNotModified

from app import config, texts
from app.bot import keyboards
from app.core import audio, downloader, stt, summarizer, tts
from app.db import database

logger = logging.getLogger(__name__)


async def _recognize_and_reply(
    message: Message,
    wav_path: str,
    duration: float,
    files_to_cleanup: List[str],
) -> None:
    """
    Распознаёт речь и отправляет результат.
    """
    try:
        # Распознаём речь
        result = await stt.transcribe(wav_path)

        # Если результат пустой или None
        if not result:
            await message.answer(texts.RECOGNITION_EMPTY)
            return

        # ✅ ИСПРАВЛЕНО: result — это строка, а не словарь
        transcription = result

        # Проверяем лимиты
        user_id = message.from_user.id
        is_pro = await database.is_pro(user_id)
        if not is_pro:
            # Считаем использование
            used = await database.get_usage(user_id)
            if used >= config.FREE_MONTHLY_LIMIT:
                await message.answer(texts.LIMIT_REACHED)
                return
            if duration > config.FREE_MAX_MINUTES * 60:
                await message.answer(texts.FILE_TOO_LONG)
                return

        # Отправляем транскрипцию
        await message.answer(f"📝 {transcription}")

        # Если включён LLM, генерируем краткое содержание
        if config.LLM_PROVIDER != "none" and config.LLM_API_KEY:
            await message.answer("🧠 Генерирую краткое содержание...")
            summary = await summarizer.summarize(transcription)
            if summary:
                await message.answer(f"📌 {summary}")

        # Обновляем лимиты
        if not is_pro:
            await database.increment_usage(user_id)

    except Exception as e:
        logger.error(f"Ошибка при распознавании: {e}", exc_info=True)
        await message.answer(texts.ERROR_OCCURRED)
    finally:
        # Удаляем временные файлы
        for path in files_to_cleanup:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass


async def _process_media(
    message: Message,
    file_id: str,
    ext: str,
) -> None:
    """
    Скачивает медиафайл, конвертирует и запускает распознавание.
    """
    temp_dir = tempfile.mkdtemp()
    try:
        # Скачиваем файл
        file_path = os.path.join(temp_dir, f"input{ext}")
        await downloader.download_file(file_id, file_path)

        # Конвертируем в WAV
        wav_path = os.path.join(temp_dir, "output.wav")
        duration = await audio.convert_to_wav(file_path, wav_path)

        # Запускаем распознавание
        await _recognize_and_reply(
            message,
            wav_path,
            duration,
            [file_path, wav_path],
        )
    except Exception as e:
        logger.error(f"Ошибка обработки медиа: {e}", exc_info=True)
        await message.answer(texts.ERROR_OCCURRED)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# -------- ОБРАБОТЧИКИ КОМАНД И СООБЩЕНИЙ --------


async def cmd_start(message: Message, state: FSMContext):
    """Команда /start"""
    await state.finish()
    await message.answer(
        texts.START_MESSAGE,
        reply_markup=keyboards.main_menu(),
    )


async def cmd_help(message: Message, state: FSMContext):
    """Команда /help"""
    await state.finish()
    await message.answer(texts.HELP_MESSAGE)


async def cmd_pro(message: Message, state: FSMContext):
    """Команда /pro (получить PRO)"""
    await state.finish()
    user_id = message.from_user.id
    is_pro = await database.is_pro(user_id)
    if is_pro:
        expiry = await database.get_pro_expiry(user_id)
        if expiry:
            delta = expiry - datetime.now()
            days = delta.days
            hours = delta.seconds // 3600
            await message.answer(
                f"✅ У вас уже есть PRO-доступ до {expiry.strftime('%d.%m.%Y %H:%M')}\n"
                f"Осталось: {days} дн. {hours} ч."
            )
        else:
            await message.answer("✅ У вас уже есть PRO-доступ (бессрочный).")
        return

    # Активируем пробный период (24 часа)
    expiry = datetime.now() + timedelta(hours=config.PRO_TRIAL_HOURS)
    await database.set_pro(user_id, expiry)
    await message.answer(
        f"🎉 Вам активирован PRO-доступ на {config.PRO_TRIAL_HOURS} часов!\n"
        f"Действует до {expiry.strftime('%d.%m.%Y %H:%M')}."
    )


async def handle_text(message: Message, state: FSMContext):
    """Обработка любого текстового сообщения (заглушка)"""
    await state.finish()
    await message.answer(texts.FALLBACK_TEXT)


async def handle_voice(message: Message, state: FSMContext):
    """Обработка голосового сообщения"""
    await state.finish()
    await _process_media(message, message.voice.file_id, ".ogg")


async def handle_audio(message: Message, state: FSMContext):
    """Обработка аудиофайла"""
    await state.finish()
    await _process_media(message, message.audio.file_id, ".mp3")


async def handle_document(message: Message, state: FSMContext):
    """Обработка документа (если это аудио/видео)"""
    await state.finish()
    doc = message.document
    if doc.mime_type and doc.mime_type.startswith("audio/"):
        await _process_media(message, doc.file_id, ".mp3")
    elif doc.mime_type and doc.mime_type.startswith("video/"):
        await _process_media(message, doc.file_id, ".mp4")
    else:
        await message.answer("❌ Пожалуйста, отправьте аудио- или видеофайл.")


async def handle_callback_query(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатий на кнопки (заглушка)"""
    await callback.answer("⏳ Функция в разработке")

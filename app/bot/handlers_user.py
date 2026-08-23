"""Хендлеры пользовательских сообщений (медиа, ссылки, текст)."""
import asyncio
import hashlib
import logging
import os

from aiogram import Router, F
from aiogram.types import Message

from app import config
from app.core import audio, stt, downloader
from app.utils import limits
from app.bot import texts, keyboards
from app.db import database

log = logging.getLogger(__name__)
router = Router()

MAX_MSG_LEN = 4000


def _split_text(text: str, max_len: int = MAX_MSG_LEN):
    if len(text) <= max_len:
        return [text]
    parts = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        split_at = text.rfind(" ", 0, max_len)
        if split_at == -1:
            split_at = max_len
        parts.append(text[:split_at])
        text = text[split_at:].lstrip()
    return parts


def _file_hash(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


async def _update_status_periodically(status_msg: Message, base_text: str, duration_sec: float):
    """Обновляет сообщение статуса каждые 10 секунд."""
    elapsed = 0
    try:
        while True:
            await asyncio.sleep(10)
            elapsed += 10
            progress = min(100, int((elapsed / max(duration_sec, 1)) * 100))
            new_text = f"{base_text}\n\n⏱️ Прошло: {elapsed} сек ({progress}%)"
            try:
                await status_msg.edit_text(new_text)
            except Exception:
                break
    except asyncio.CancelledError:
        pass


async def _recognize_and_reply(message: Message, wav_path: str, duration: float, cleanup_paths: list):
    """Общая логика: кэш -> распознавание с индикатором -> ответ с кнопками -> чистка."""
    from app.bot.handlers_callbacks import save_transcription

    user_id = message.from_user.id

    # Кэш по хэшу wav
    fhash = _file_hash(wav_path)
    cached = await database.get_cache(fhash)
    if cached:
        transcription = cached["transcription"]
        segments = cached["segments"]
        cache_note = "\n♻️ <i>Взято из кэша (повторное распознавание не требуется)</i>"
        log.info("♻️ Кэш найден: %s", fhash)
    else:
        # Создаём статус-сообщение с индикатором прогресса
        status_msg = await message.answer("🎙️ Распознаю речь, это может занять несколько минут...")
        
        # Запускаем задачу обновления статуса
        update_task = asyncio.create_task(
            _update_status_periodically(status_msg, "🎙️ Распознаю речь...", duration)
        )
        
        try:
            result = await stt.transcribe(wav_path)
            transcription = result["text"]
            segments = result["segments"]
            await database.set_cache(fhash, transcription, segments)
            cache_note = ""
        finally:
            update_task.cancel()
            try:
                await update_task
            except asyncio.CancelledError:
                pass
        
        # Удаляем статус-сообщение
        try:
            await status_msg.delete()
        except Exception:
            pass

    # Учёт транскрипции
    mode = await limits.on_transcription_success(user_id)
    duration_sec = int(duration)
    duration_str = (
        f"{duration_sec // 60}:{duration_sec % 60:02d}" if duration_sec >= 60
        else f"{duration_sec} сек"
    )

    trial_note = ""
    if mode == "trial":
        trial_note = f"\n\n🎁 <b>Ты получил {config.PRO_TRIAL_HOURS} часа PRO!</b>"

    chunks = _split_text(transcription)
    kb = keyboards.transcription_actions_kb()

    header = (
        f"✅ <b>Распознано!</b>\n"
        f"📏 Длительность: {duration_str}\n"
        f"👤 Режим: <code>{mode}</code>"
        f"{trial_note}{cache_note}\n\n"
    )

    reply_msg = None
    if len(chunks) == 1 and len(header + chunks[0]) <= MAX_MSG_LEN:
        reply_msg = await message.answer(header + chunks[0], reply_markup=kb)
    else:
        await message.answer(header + "<i>Текст ниже:</i>")
        for i, chunk in enumerate(chunks):
            if i == len(chunks) - 1:
                reply_msg = await message.answer(chunk, reply_markup=kb)
            else:
                await message.answer(chunk)

    if reply_msg:
        save_transcription(reply_msg.message_id, transcription, segments)

    # Чистка временных файлов
    for p in cleanup_paths:
        try:
            if os.path.exists(p):
                os.remove(p)
                log.info("🗑️ Удалён временный файл: %s", p)
        except OSError as e:
            log.warning("Не удалось удалить %s: %s", p, e)


async def _process_media(message: Message, file_id: str, file_ext: str):
    user_id = message.from_user.id

    allowed, reason = await limits.check_access(user_id)
    if not allowed:
        await message.answer(reason)
        return

    status_msg = await message.answer("⏳ Скачиваю файл...")
    os.makedirs(config.MEDIA_DIR, exist_ok=True)
    file_name = f"{user_id}_{message.message_id}{file_ext}"
    file_path = os.path.join(config.MEDIA_DIR, file_name)

    try:
        await message.bot.download(file_id, destination=file_path)
    except Exception as e:
        log.error("Не удалось скачать файл: %s", e)
        await status_msg.edit_text("❌ Не удалось скачать файл.")
        return

    allowed, duration, reason = await audio.check_duration_limit(file_path, user_id)
    if not allowed:
        await status_msg.edit_text(reason)
        try: os.remove(file_path)
        except OSError: pass
        return

    await status_msg.edit_text("🔄 Подготавливаю аудио...")
    wav_path = file_path + ".wav"
    if not await audio.convert_to_wav(file_path, wav_path):
        await status_msg.edit_text("❌ Не удалось обработать аудио.")
        try: os.remove(file_path)
        except OSError: pass
        return

    await status_msg.delete()
    await _recognize_and_reply(message, wav_path, duration, [file_path, wav_path])


async def _process_url(message: Message, url: str):
    user_id = message.from_user.id

    allowed, reason = await limits.check_access(user_id)
    if not allowed:
        await message.answer(reason)
        return

    status_msg = await message.answer("⏳ Скачиваю по ссылке (это может занять время)...")
    os.makedirs(config.MEDIA_DIR, exist_ok=True)
    base_path = os.path.join(config.MEDIA_DIR, f"{user_id}_{message.message_id}_link")

    result = await downloader.download_audio(url, base_path)
    if not result["ok"]:
        await status_msg.edit_text(
            "❌ Не удалось скачать по ссылке.\n"
            "Возможно, видео недоступно или платформа блокирует скачивание."
        )
        return

    downloaded = result["path"]
    allowed, duration, reason = await audio.check_duration_limit(downloaded, user_id)
    if not allowed:
        await status_msg.edit_text(reason)
        try: os.remove(downloaded)
        except OSError: pass
        return

    await status_msg.edit_text("🔄 Подготавливаю аудио...")
    wav_path = downloaded + ".wav"
    if not await audio.convert_to_wav(downloaded, wav_path):
        await status_msg.edit_text("❌ Не удалось обработать аудио из ссылки.")
        try: os.remove(downloaded)
        except OSError: pass
        return

    await status_msg.delete()
    await _recognize_and_reply(message, wav_path, duration, [downloaded, wav_path])


@router.message(F.voice)
async def handle_voice(message: Message):
    await _process_media(message, message.voice.file_id, ".ogg")


@router.message(F.audio)
async def handle_audio(message: Message):
    ext = ".mp3"
    if message.audio.file_name:
        ext = os.path.splitext(message.audio.file_name)[1] or ".mp3"
    await _process_media(message, message.audio.file_id, ext)


@router.message(F.video)
async def handle_video(message: Message):
    ext = ".mp4"
    if message.video.file_name:
        ext = os.path.splitext(message.video.file_name)[1] or ".mp4"
    await _process_media(message, message.video.file_id, ext)


@router.message(F.document)
async def handle_document(message: Message):
    ext = ".bin"
    if message.document.file_name:
        ext = os.path.splitext(message.document.file_name)[1] or ".bin"
    await _process_media(message, message.document.file_id, ext)


@router.message(F.text)
async def handle_text(message: Message):
    """Если текст — ссылка, скачиваем и распознаём. Иначе — заглушка."""
    if downloader.is_url(message.text):
        await _process_url(message, message.text.strip())
    else:
        await message.answer(texts.FALLBACK_TEXT)

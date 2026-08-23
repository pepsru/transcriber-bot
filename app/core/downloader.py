"""Скачивание аудио/видео по ссылкам через yt-dlp."""
import asyncio
import glob
import logging
import os
import re

log = logging.getLogger(__name__)

URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)


def is_url(text: str) -> bool:
    """Проверяет, является ли текст ссылкой."""
    if not text:
        return False
    return bool(URL_PATTERN.search(text))


async def download_audio(url: str, base_path: str) -> dict:
    """Скачивает аудио по ссылке.
    base_path — путь БЕЗ расширения (yt-dlp добавит его сам).
    Возвращает {"ok", "path", "error", "title"}.
    """
    import yt_dlp

    def _do_download():
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": base_path,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 30,
            "retries": 3,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info

    try:
        info = await asyncio.to_thread(_do_download)
        # yt-dlp добавил расширение — ищем реальный файл
        files = glob.glob(base_path + ".*")
        if not files and os.path.exists(base_path):
            files = [base_path]
        if not files:
            return {"ok": False, "path": None, "error": "Файл не найден", "title": None}
        return {
            "ok": True,
            "path": files[0],
            "error": None,
            "title": info.get("title"),
        }
    except Exception as e:
        log.error("Ошибка скачивания %s: %s", url, e)
        return {"ok": False, "path": None, "error": str(e), "title": None}

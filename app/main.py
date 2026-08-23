"""Точка входа бота. Поддержка прокси + БД + админка."""
import asyncio
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

from app import config
from app.bot import texts, handlers_user, handlers_callbacks, handlers_admin
from app.db import database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger(__name__)

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    await database.get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    await message.answer(texts.START_TEXT)


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(texts.HELP_TEXT)


def create_bot() -> Bot:
    session = AiohttpSession()
    if config.PROXY_URL:
        from aiohttp_socks import ProxyConnector
        session._connector = ProxyConnector.from_url(config.PROXY_URL)
        log.info("🔌 Использую прокси: %s", config.PROXY_URL)
    else:
        log.info("🌐 Прямое подключение (прокси не задан)")
    return Bot(
        token=config.BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


async def main():
    await database.init_db()
    log.info("🗃️  База данных готова")

    bot = create_bot()
    dp = Dispatcher(storage=MemoryStorage())

    # ПОРЯДОК ПОДКЛЮЧЕНИЯ РОУТЕРОВ (очень важно!):
    # 1. admin — ловит секретное слово и callback-кнопки админки + FSM-состояния
    # 2. callbacks — ловит callback-кнопки транскрипций
    # 3. handlers_user — ловит медиа + текст (fallback)
    # 4. router — команды /start, /help
    dp.include_router(handlers_admin.router)
    dp.include_router(handlers_callbacks.router)
    dp.include_router(handlers_user.router)
    dp.include_router(router)

    log.info("🚀 Бот запущен (polling — порты не заняты)")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

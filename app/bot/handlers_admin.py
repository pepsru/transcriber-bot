"""Секретная админ-панель."""
import logging

from aiogram import Router, F
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from app import config
from app.bot import keyboards
from app.db import database

log = logging.getLogger(__name__)
router = Router()


class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_pro_days = State()


class AdminSecretFilter(BaseFilter):
    """Пропускает сообщение ТОЛЬКО если это секретное слово от админа.
    Иначе событие идёт дальше (fallback / ссылки)."""
    async def __call__(self, message: Message) -> bool:
        if not config.ADMIN_SECRET:
            return False
        if not message.text:
            return False
        if message.text.strip() != config.ADMIN_SECRET.strip():
            return False
        return message.from_user.id == config.ADMIN_ID


@router.message(AdminSecretFilter())
async def admin_login(message: Message):
    log.info("👑 Админ вошёл в админ-панель (user_id=%s)", message.from_user.id)
    await message.answer(
        "👑 <b>Добро пожаловать в админ-панель!</b>\n\nВыбери действие:",
        reply_markup=keyboards.admin_menu_kb(),
    )


@router.callback_query(F.data == "admin:menu")
async def admin_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "👑 <b>Админ-панель</b>\n\nВыбери действие:",
        reply_markup=keyboards.admin_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:exit")
async def admin_exit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "👋 Вышел из админки.\n\n"
        "Теперь бот работает в обычном режиме. "
        "Для повторного входа отправь секретное слово."
    )
    await callback.answer("Выход выполнен")


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery):
    stats = await database.get_stats()
    text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Пользователей: <b>{stats['users']}</b>\n"
        f"🎙️ Транскрипций: <b>{stats['transcriptions']}</b>\n"
        f"💾 Записей в кэше: <b>{stats['cache']}</b>\n\n"
        f"🆔 Твой ID: <code>{config.ADMIN_ID}</code>"
    )
    await callback.message.edit_text(text, reply_markup=keyboards.admin_back_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:limits")
async def admin_limits(callback: CallbackQuery):
    text = (
        "⚙️ <b>Текущие лимиты</b>\n\n"
        f"📅 Транскрипций в месяц: <b>{config.FREE_MONTHLY_LIMIT}</b>\n"
        f"⏱️ Макс. длительность: <b>{config.FREE_MAX_MINUTES}</b> мин\n"
        f"🎁 Trial PRO: <b>{config.PRO_TRIAL_HOURS}</b> ч\n\n"
        f"🧠 Whisper модель: <code>{config.WHISPER_MODEL}</code>\n"
        f"💻 Устройство: <code>{config.WHISPER_DEVICE}</code>\n"
        f"🌍 Язык: <code>{config.WHISPER_LANGUAGE}</code>\n\n"
        f"🤖 LLM провайдер: <code>{config.LLM_PROVIDER}</code>\n"
        f"🤖 LLM модель: <code>{config.LLM_MODEL or '—'}</code>\n\n"
        f"<i>Для изменения — отредактируй .env и перезапусти бота.</i>"
    )
    await callback.message.edit_text(text, reply_markup=keyboards.admin_back_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:grant_pro")
async def admin_grant_pro_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "👑 <b>Выдача PRO</b>\n\n"
        "Отправь Telegram-ID пользователя (числом).\n\n"
        "<i>Узнать ID можно через @userinfobot</i>",
        reply_markup=keyboards.admin_back_kb(),
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await callback.answer()


@router.message(AdminStates.waiting_for_user_id)
async def admin_grant_pro_get_id(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ Нужно отправить число. Попробуй ещё раз:",
            reply_markup=keyboards.admin_back_kb(),
        )
        return

    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminStates.waiting_for_pro_days)
    await message.answer(
        f"🎯 Пользователь: <code>{user_id}</code>\n\nВыбери срок PRO:",
        reply_markup=keyboards.admin_pro_days_kb(),
    )


@router.callback_query(F.data.startswith("admin:pro_days:"))
async def admin_grant_pro_confirm(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state != AdminStates.waiting_for_pro_days.state:
        await callback.answer()
        return

    days = int(callback.data.split(":")[2])
    data = await state.get_data()
    user_id = data.get("target_user_id")

    pro_until = await database.grant_pro(user_id, days)
    await state.clear()

    await callback.message.edit_text(
        f"✅ <b>PRO выдан!</b>\n\n"
        f"🎯 Пользователь: <code>{user_id}</code>\n"
        f"📅 Срок: <b>{days}</b> дней\n"
        f"⏰ Действует до: <code>{pro_until.strftime('%Y-%m-%d %H:%M')}</code> UTC",
        reply_markup=keyboards.admin_back_kb(),
    )
    await callback.answer("PRO выдан")

"""Инлайн-клавиатуры бота."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def transcription_actions_kb() -> InlineKeyboardMarkup:
    """Клавиатура после успешной транскрипции (4 кнопки из референса)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📌 Главные мысли",
                callback_data="action:thoughts",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📝 Конспект",
                callback_data="action:summary",
            ),
        ],
        [
            InlineKeyboardButton(
                text="❓ Вопросы с таймкодами",
                callback_data="action:questions",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🎧 Озвучка",
                callback_data="action:audio",
            ),
        ],
    ])


def admin_menu_kb() -> InlineKeyboardMarkup:
    """Главное меню админки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="👑 Выдать PRO", callback_data="admin:grant_pro")],
        [InlineKeyboardButton(text="⚙️ Текущие лимиты", callback_data="admin:limits")],
        [InlineKeyboardButton(text="🚪 Выход из админки", callback_data="admin:exit")],
    ])


def admin_back_kb() -> InlineKeyboardMarkup:
    """Кнопка 'Назад' в админке."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="admin:menu")],
    ])


def admin_pro_days_kb() -> InlineKeyboardMarkup:
    """Выбор срока PRO при выдаче."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="7 дней", callback_data="admin:pro_days:7"),
            InlineKeyboardButton(text="30 дней", callback_data="admin:pro_days:30"),
        ],
        [
            InlineKeyboardButton(text="90 дней", callback_data="admin:pro_days:90"),
            InlineKeyboardButton(text="365 дней", callback_data="admin:pro_days:365"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:menu")],
    ])

"""Логика лимитов: проверка доступа и учёт транскрипций."""
from datetime import datetime, timedelta
from app import config
from app.db import database


async def check_access(user_id):
    """Проверяет, может ли пользователь делать транскрипцию.
    Возвращает (разрешено: bool, причина_отказа: str | None).
    """
    # ── 1. Админ: безлимит без проверок ──
    if user_id == config.ADMIN_ID:
        return True, None

    user = await database.get_or_create_user(user_id)
    now = datetime.utcnow()

    # ── 2. Активен PRO (trial или выданный вручную) ──
    pro_until = user.get("pro_until")
    if pro_until:
        pro_until_dt = datetime.fromisoformat(pro_until)
        if pro_until_dt > now:
            return True, None

    # ── 3. Первая транскрипция — получит trial PRO (24 часа) ──
    if not user.get("first_transcription_at"):
        return True, None

    # ── 4. Проверка месячного лимита ──
    count = await database.get_usage_count_this_month(user_id)
    if count >= config.FREE_MONTHLY_LIMIT:
        return False, (
            f"🚫 Лимит на этот месяц исчерпан "
            f"({count}/{config.FREE_MONTHLY_LIMIT}).\n\n"
            f"Следующая бесплатная транскрипция: 1 числа следующего месяца.\n"
            f"🎁 Новый PRO-период можно получить по подписке."
        )

    return True, None


async def on_transcription_success(user_id):
    """Вызывается после УСПЕШНОЙ транскрипции.
    Обновляет лимиты и возвращает тип доступа ('trial' / 'free' / 'admin').
    """
    if user_id == config.ADMIN_ID:
        return "admin"

    user = await database.get_or_create_user(user_id)
    now = datetime.utcnow()

    # Первая транскрипция — выдаём trial PRO на 24 часа
    if not user.get("first_transcription_at"):
        pro_until = now + timedelta(hours=config.PRO_TRIAL_HOURS)
        await database.update_user(
            user_id,
            first_transcription_at=now.isoformat(),
            pro_until=pro_until.isoformat(),
        )
        return "trial"

    # Обычная транскрипция — считаем в месячный лимит
    await database.add_usage(user_id, file_id=None)
    return "free"

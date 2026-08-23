"""Работа с SQLite: создание таблиц и CRUD операции."""
import json
import aiosqlite
from datetime import datetime, timedelta
from app import config


async def init_db():
    """Создаёт таблицы при первом запуске."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                first_transcription_at TIMESTAMP,
                pro_until TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                file_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                file_hash TEXT PRIMARY KEY,
                transcription TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Миграция: добавляем колонку segments, если её нет
        try:
            await db.execute("ALTER TABLE cache ADD COLUMN segments TEXT")
        except Exception:
            pass
        await db.commit()


def _row_to_dict(cursor, row):
    if not row:
        return None
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


async def get_or_create_user(user_id, username=None, first_name=None):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name) "
            "VALUES (?, ?, ?)",
            (user_id, username, first_name),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return _row_to_dict(cursor, row)


async def update_user(user_id, **fields):
    if not fields:
        return
    async with aiosqlite.connect(config.DB_PATH) as db:
        set_parts = []
        values = []
        for key, value in fields.items():
            set_parts.append(f"{key} = ?")
            values.append(value)
        values.append(user_id)
        sql = f"UPDATE users SET {', '.join(set_parts)} WHERE user_id = ?"
        await db.execute(sql, values)
        await db.commit()


async def add_usage(user_id, file_id=None):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO usage (user_id, file_id) VALUES (?, ?)",
            (user_id, file_id),
        )
        await db.commit()


async def get_usage_count_this_month(user_id):
    async with aiosqlite.connect(config.DB_PATH) as db:
        now = datetime.utcnow()
        month_start = datetime(now.year, now.month, 1).isoformat()
        async with db.execute(
            "SELECT COUNT(*) FROM usage WHERE user_id = ? AND created_at >= ?",
            (user_id, month_start),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_stats():
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            users_count = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM usage") as c:
            transcriptions_count = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM cache") as c:
            cache_count = (await c.fetchone())[0]
    return {
        "users": users_count,
        "transcriptions": transcriptions_count,
        "cache": cache_count,
    }


async def grant_pro(user_id: int, days: int = 30):
    await get_or_create_user(user_id)
    now = datetime.utcnow()
    pro_until = now + timedelta(days=days)
    await update_user(user_id, pro_until=pro_until.isoformat())
    return pro_until


async def get_user_info(user_id: int):
    return await get_or_create_user(user_id)


async def get_cache(file_hash: str):
    """Возвращает кэш {"transcription", "segments"} или None."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT transcription, segments FROM cache WHERE file_hash = ?",
            (file_hash,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "transcription": row[0],
                "segments": json.loads(row[1] or "[]"),
            }


async def set_cache(file_hash: str, transcription: str, segments: list):
    """Сохраняет результат распознавания в кэш."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO cache (file_hash, transcription, segments) "
            "VALUES (?, ?, ?)",
            (file_hash, transcription, json.dumps(segments)),
        )
        await db.commit()

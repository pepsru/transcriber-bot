#!/usr/bin/env bash
set -euo pipefail

echo "🔧 Создаю структуру проекта..."

# ── Папки ──
mkdir -p app/bot app/core app/db app/utils
mkdir -p data media models

# ── Пустые файлы (содержимое дам следующими шагами) ──
touch Dockerfile docker-compose.yml README.md
touch app/__init__.py app/main.py app/config.py
touch app/bot/__init__.py app/bot/handlers_user.py app/bot/handlers_admin.py
touch app/bot/keyboards.py app/bot/texts.py
touch app/core/__init__.py app/core/downloader.py app/core/audio.py
touch app/core/stt.py app/core/cleaner.py app/core/summarizer.py
touch app/db/__init__.py app/db/database.py
touch app/utils/__init__.py app/utils/limits.py

# ── .env.example (шаблон настроек) ──
cat > .env.example << 'EOF'
# ─────────── Telegram ───────────
# Токен бота от @BotFather (формат: 123456789:AA...)
BOT_TOKEN=

# ─────────── АДМИН (никому не показывай!) ───────────
# Твой числовой Telegram-ID (узнал через @userinfobot)
ADMIN_ID=

# Секретное кодовое слово входа в админку.
# Пришли его боту личным сообщением — откроется админ-панель.
# Замени на СВОЁ слово!
ADMIN_SECRET=замени-меня-сразу

# ─────────── Распознавание ───────────
# Модель Whisper: tiny / base / small / medium / large-v3
WHISPER_MODEL=small
# Устройство: cpu (или cuda, если есть GPU)
WHISPER_DEVICE=cpu
# Язык: auto или код (ru, en, ...)
WHISPER_LANGUAGE=auto

# ─────────── ИИ-фичи (мысли/конспект/вопросы) ───────────
# none / openai / groq / gemini   (none = работает без ИИ-ключа)
LLM_PROVIDER=none
LLM_API_KEY=
LLM_MODEL=

# ─────────── Лимиты ОБЫЧНЫХ пользователей ───────────
# Бесплатных транскрипций в месяц
FREE_MONTHLY_LIMIT=3
# Максимальная длительность файла, минут
FREE_MAX_MINUTES=15
# Сколько часов длится trial-PRO после первой транскрипции
PRO_TRIAL_HOURS=24
EOF

# ── .gitignore ──
cat > .gitignore << 'EOF'
.env
data/
media/
models/
__pycache__/
*.pyc
.venv/
EOF

# ── .env из шаблона, если ещё нет ──
if [ ! -f .env ]; then
  cp .env.example .env
  echo "📄 Создан .env — ОБЯЗАТЕЛЬНО заполни его!"
else
  echo "ℹ️  .env уже существует, не трогаю."
fi

echo ""
echo "✅ Готово! Структура:"
find . -type f | sort

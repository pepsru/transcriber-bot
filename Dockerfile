FROM python:3.11-slim

# Устанавливаем системные пакеты
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Обновляем сертификаты
RUN update-ca-certificates

WORKDIR /app

# Отключаем проверку SSL на уровне системы и pip
ENV PYTHONHTTPSVERIFY=0
ENV CURL_CA_BUNDLE=""
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Увеличиваем таймауты
RUN pip config set global.timeout 600 \
    && pip config set global.retries 10 \
    && pip config set global.trusted-host "pypi.org files.pythonhosted.org pypi.tuna.tsinghua.edu.cn mirrors.aliyun.com"

# Копируем requirements
COPY requirements.txt .

# Устанавливаем пакеты с полным обходом SSL
RUN pip install \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    --trusted-host mirrors.aliyun.com \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r requirements.txt

# Копируем код проекта
COPY . .

# Модели Whisper храним в /app/models (это том — не скачиваются повторно)
ENV HF_HOME=/app/models
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "app.main"]

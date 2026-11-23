#!/bin/bash
set -e

echo "=== Telegram Chat Analyzer ==="

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Создание виртуального окружения..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install requirements
echo "Установка зависимостей..."
pip install -r backend/requirements.txt

# Run server
echo "Запуск сервера..."
echo "Приложение доступно по адресу: http://localhost:8000"
export PYTHONPATH=$(pwd)
uvicorn backend.main:app --host 127.0.0.1 --port 8000

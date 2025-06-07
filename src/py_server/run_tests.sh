#!/bin/bash
# Скрипт для запуска тестов HTTP-сервиса 1С MCP API

set -e  # Выход при ошибке

echo "🚀 Запуск тестов HTTP-сервиса 1С MCP API"
echo "========================================="

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден. Установите Python 3.7+"
    exit 1
fi

# Проверяем наличие файла тестов
if [ ! -f "test_onec_service.py" ]; then
    echo "❌ Файл test_onec_service.py не найден"
    exit 1
fi

# Проверяем наличие виртуального окружения (опционально)
if [ -d "venv" ]; then
    echo "🔧 Активируем виртуальное окружение..."
    source venv/bin/activate
fi

# Устанавливаем зависимости если нужно
if [ ! -z "$1" ] && [ "$1" = "--install" ]; then
    echo "📦 Устанавливаем зависимости..."
    pip install -r requirements.txt
fi

# Запускаем тесты
echo "🧪 Запускаем тесты..."
python3 test_onec_service.py

# Проверяем результат
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Тестирование завершено успешно!"
    
    # Показываем результаты если есть файл
    if [ -f "test_results.json" ]; then
        echo "📄 Результаты сохранены в test_results.json"
        echo "📊 Краткая сводка:"
        
        # Попытаемся показать краткую статистику
        if command -v jq &> /dev/null; then
            echo "   $(jq -r 'to_entries | map(select(.value.status == "success")) | length' test_results.json) успешных из $(jq -r 'keys | length' test_results.json) тестов"
        fi
    fi
else
    echo ""
    echo "❌ Тестирование завершилось с ошибками!"
    exit 1
fi 
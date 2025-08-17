#!/usr/bin/env python3
"""
Тестовый скрипт для проверки MCP эндпоинта в 1С
"""

import requests
import json

# Базовый URL сервера (замените на актуальный)
BASE_URL = "http://localhost/ВАША_БАЗА/hs/mcp"

def test_initialize():
    """Тестирует метод initialize"""
    print("=== Тест initialize ===")
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {
                "roots": {
                    "listChanged": False
                }
            },
            "clientInfo": {
                "name": "Test Client",
                "version": "1.0.0"
            }
        }
    }
    
    try:
        response = requests.post(f"{BASE_URL}", json=payload)
        print(f"Статус: {response.status_code}")
        print(f"Заголовки: {dict(response.headers)}")
        print(f"Ответ: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"Ошибка: {e}")

def test_notifications_initialized():
    """Тестирует notification initialized"""
    print("\n=== Тест notifications/initialized ===")
    
    payload = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {}
        # Обратите внимание: нет поля "id" - это notification
    }
    
    try:
        response = requests.post(f"{BASE_URL}", json=payload)
        print(f"Статус: {response.status_code}")
        print(f"Заголовки: {dict(response.headers)}")
        print(f"Тело ответа: '{response.text}'")
        print(f"Длина тела: {len(response.text)}")
    except Exception as e:
        print(f"Ошибка: {e}")

def test_tools_list():
    """Тестирует получение списка инструментов"""
    print("\n=== Тест tools/list ===")
    
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    
    try:
        response = requests.post(f"{BASE_URL}", json=payload)
        print(f"Статус: {response.status_code}")
        print(f"Ответ: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"Ошибка: {e}")

def test_unknown_notification():
    """Тестирует неизвестную notification"""
    print("\n=== Тест неизвестной notification ===")
    
    payload = {
        "jsonrpc": "2.0",
        "method": "unknown/notification",
        "params": {}
        # Нет "id" - это notification
    }
    
    try:
        response = requests.post(f"{BASE_URL}", json=payload)
        print(f"Статус: {response.status_code}")
        print(f"Тело ответа: '{response.text}'")
        print(f"Длина тела: {len(response.text)}")
    except Exception as e:
        print(f"Ошибка: {e}")

def test_unknown_method():
    """Тестирует неизвестный метод с ID"""
    print("\n=== Тест неизвестного метода ===")
    
    payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "unknown/method",
        "params": {}
    }
    
    try:
        response = requests.post(f"{BASE_URL}", json=payload)
        print(f"Статус: {response.status_code}")
        print(f"Ответ: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"Ошибка: {e}")

def test_mcp_get():
    """Тестирует GET запрос к /mcp (должен вернуть 405)"""
    print("\n=== Тест GET /mcp ===")
    
    try:
        response = requests.get(f"{BASE_URL}")
        print(f"Статус: {response.status_code}")
        print(f"Заголовки: {dict(response.headers)}")
        print(f"Тело ответа: '{response.text}'")
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    print("Тестирование MCP эндпоинта в 1С")
    print("Не забудьте изменить BASE_URL на актуальный адрес вашего сервера!")
    print()
    
    test_initialize()
    test_notifications_initialized()
    test_tools_list()
    test_unknown_notification()
    test_unknown_method()
    test_mcp_get()
    
    print("\n=== Тесты завершены ===") 
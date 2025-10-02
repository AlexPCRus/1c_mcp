# OAuth2 авторизация в MCP-прокси - Быстрый старт

## Что реализовано

Добавлена опциональная OAuth2 авторизация (Authorization Code + PKCE S256) для HTTP-режима Python-прокси. Прокси транслирует Bearer токены в Basic-авторизацию к 1С.

## Режимы работы

- `AUTH_MODE=none` (по умолчанию) - без авторизации, как раньше
- `AUTH_MODE=oauth2` - включена OAuth2 авторизация

## Быстрый старт

### 1. Настройка конфигурации

Создайте или обновите `.env` файл:

```bash
# Основные настройки 1С (обязательно)
MCP_ONEC_URL=http://localhost/your_base
MCP_ONEC_USERNAME=admin
MCP_ONEC_PASSWORD=password
MCP_ONEC_SERVICE_ROOT=mcp

# OAuth2 настройки
MCP_AUTH_MODE=oauth2
MCP_PUBLIC_URL=http://localhost:8000

# TTL токенов (опционально, значения по умолчанию)
MCP_OAUTH2_CODE_TTL=120
MCP_OAUTH2_ACCESS_TTL=3600
MCP_OAUTH2_REFRESH_TTL=1209600
```

### 2. Запуск сервера

```bash
# Активируйте виртуальное окружение
venv\Scripts\activate  # Windows
# или
source venv/bin/activate  # Linux/Mac

# Запустите HTTP-сервер с OAuth2
python -m src.py_server http --auth-mode oauth2 --public-url http://localhost:8000
```

### 3. Проверка работы

#### Получение метаданных (PRM):
```bash
curl http://localhost:8000/.well-known/oauth-protected-resource
```

Ответ:
```json
{
  "resource": "http://localhost:8000",
  "authorization_servers": ["http://localhost:8000"],
  "authorization_endpoint": "http://localhost:8000/authorize",
  "token_endpoint": "http://localhost:8000/token",
  "code_challenge_methods_supported": ["S256"]
}
```

#### Процесс авторизации (через браузер):

1. Откройте в браузере (с вашими параметрами PKCE):
```
http://localhost:8000/authorize?response_type=code&client_id=test&redirect_uri=http://localhost/callback&code_challenge=YOUR_CHALLENGE&code_challenge_method=S256&state=xyz
```

2. Введите логин и пароль пользователя 1С в HTML форме

3. После успешной авторизации вы будете перенаправлены на:
```
http://localhost/callback?code=AUTHORIZATION_CODE&state=xyz
```

#### Обмен кода на токены:
```bash
curl -X POST http://localhost:8000/token \
  -d "grant_type=authorization_code" \
  -d "code=AUTHORIZATION_CODE" \
  -d "redirect_uri=http://localhost/callback" \
  -d "code_verifier=YOUR_VERIFIER"
```

Ответ:
```json
{
  "access_token": "...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "...",
  "scope": "mcp"
}
```

#### Использование access token:
```bash
curl http://localhost:8000/mcp/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

#### Обновление токенов:
```bash
curl -X POST http://localhost:8000/token \
  -d "grant_type=refresh_token" \
  -d "refresh_token=YOUR_REFRESH_TOKEN"
```

## Генерация PKCE (Python пример)

```python
import secrets
import hashlib
import base64

# Генерация code_verifier (43-128 символов)
code_verifier = secrets.token_urlsafe(32)

# Генерация code_challenge (SHA256 + base64url)
verifier_hash = hashlib.sha256(code_verifier.encode('ascii')).digest()
code_challenge = base64.urlsafe_b64encode(verifier_hash).decode('ascii').rstrip('=')

print(f"Code verifier: {code_verifier}")
print(f"Code challenge: {code_challenge}")
```

## Защищённые endpoints

При `AUTH_MODE=oauth2` следующие пути требуют Bearer токен:
- `/mcp/` - Streamable HTTP транспорт MCP
- `/sse` - SSE транспорт MCP
- `/sse/messages/` - отправка сообщений через SSE

Незащищённые (доступны всегда):
- `/.well-known/oauth-protected-resource` - PRM документ
- `/authorize` - форма авторизации
- `/token` - обмен кодов и refresh
- `/health` - проверка состояния
- `/info` - информация о сервере
- `/` - корневой endpoint

## Интеграция с MCP-клиентами

MCP-клиенты, поддерживающие OAuth2 (согласно спецификации MCP Authorization), автоматически:
1. Прочитают PRM документ
2. Выполнят Authorization Code + PKCE flow
3. Будут использовать Bearer токены для всех запросов

## Безопасность

### Рекомендации для продакшна:
- ✅ Используйте HTTPS (разместите прокси за nginx/caddy с TLS)
- ✅ Установите строгий `MCP_PUBLIC_URL` с https://
- ✅ Ограничьте `MCP_CORS_ORIGINS` конкретными доменами
- ✅ Используйте сильные пароли для пользователей 1С
- ✅ Настройте файрвол для ограничения доступа

### Что хранится в памяти:
- Authorization codes (TTL: 2 минуты)
- Access tokens с привязанными логин/пароль 1С (TTL: 1 час)
- Refresh tokens с привязанными логин/пароль 1С (TTL: 14 дней)

При рестарте сервера все токены сбрасываются (by design для простоты).

## Отключение OAuth2

Для возврата к режиму без авторизации:

```bash
# В .env
MCP_AUTH_MODE=none

# Или при запуске
python -m src.py_server http --auth-mode none
```

## Тестирование

Запустите базовый тест функциональности:
```bash
python src/py_server/test_oauth2_basic.py
```

## Структура реализации

```
src/py_server/
├── auth/
│   ├── __init__.py
│   └── oauth2.py           # OAuth2 сервис и хранилище
├── config.py               # Конфигурация (добавлены OAuth2 параметры)
├── mcp_server.py           # Context vars для per-session кредов
├── http_server.py          # OAuth2 endpoints и middleware
├── main.py                 # CLI параметры для OAuth2
└── env.example             # Примеры конфигурации

Документация:
├── OAUTH2_QUICKSTART.md    # Этот файл
└── src/py_server/
    ├── OAUTH2_DESIGN.md           # Проектная документация
    └── OAUTH2_IMPLEMENTATION.md   # Детали реализации
```

## Дополнительная информация

- Детальная архитектура: `src/py_server/OAUTH2_DESIGN.md`
- Технические детали реализации: `src/py_server/OAUTH2_IMPLEMENTATION.md`
- Спецификация MCP Authorization: https://modelcontextprotocol.io/docs/specification/authorization
- RFC 9728 (Protected Resource Metadata): https://datatracker.ietf.org/doc/html/rfc9728
- RFC 7636 (PKCE): https://datatracker.ietf.org/doc/html/rfc7636


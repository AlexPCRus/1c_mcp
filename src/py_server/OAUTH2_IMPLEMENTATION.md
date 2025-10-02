# Реализация OAuth2 авторизации в MCP-прокси

## Обзор изменений

Реализована опциональная OAuth2 авторизация (Authorization Code + PKCE S256) для HTTP-режима MCP-прокси. В режиме `AUTH_MODE=none` поведение остаётся прежним.

## Реализованные файлы

### 1. `config.py`
Добавлены параметры конфигурации:
- `auth_mode` - режим авторизации ("none" или "oauth2")
- `public_url` - публичный URL прокси для OAuth2
- `oauth2_code_ttl` - TTL authorization code (по умолчанию 120 сек)
- `oauth2_access_ttl` - TTL access token (по умолчанию 3600 сек)
- `oauth2_refresh_ttl` - TTL refresh token (по умолчанию 14 дней)

### 2. `auth/oauth2.py`
Новый модуль, содержащий:
- `OAuth2Store` - in-memory хранилище токенов с автоматической очисткой по TTL
- `OAuth2Service` - бизнес-логика OAuth2:
  - Генерация/валидация authorization code
  - PKCE S256 валидация
  - Выпуск и ротация access/refresh токенов
  - Генерация PRM документа

### 3. `mcp_server.py`
Добавлено:
- `current_onec_credentials` - context var для per-session креденшилов
- Логика в `_lifespan` для выбора креденшилов в зависимости от режима авторизации

### 4. `http_server.py`
Добавлено:
- `OAuth2BearerMiddleware` - middleware для проверки Bearer токенов
- `_register_oauth2_routes()` - регистрация OAuth2 endpoints:
  - `GET /.well-known/oauth-protected-resource` - PRM документ
  - `GET /authorize` - форма авторизации
  - `POST /authorize` - обработка логина и выдача кода
  - `POST /token` - обмен кода на токены / refresh
- Интеграция OAuth2Store в lifespan для запуска задачи очистки

### 5. `main.py`
Добавлены CLI параметры:
- `--auth-mode` - выбор режима авторизации
- `--public-url` - публичный URL для OAuth2

### 6. `env.example`
Добавлены примеры новых переменных окружения с комментариями.

## Использование

### Режим без авторизации (по умолчанию)
```bash
python -m src.py_server http
```

### Режим с OAuth2
```bash
# В .env файле или через переменные окружения
export MCP_AUTH_MODE=oauth2
export MCP_PUBLIC_URL=https://your-proxy.example.com

python -m src.py_server http
```

Или через CLI:
```bash
python -m src.py_server http --auth-mode oauth2 --public-url https://your-proxy.example.com
```

## Поток авторизации

1. **Discovery**: Клиент читает `GET /.well-known/oauth-protected-resource`
2. **Authorization**: 
   - Клиент переходит на `/authorize` с параметрами (code_challenge, redirect_uri, etc.)
   - Пользователь вводит логин/пароль 1С в HTML форме
   - Прокси валидирует креденшилы через вызов к 1С health endpoint
   - Выдаётся authorization code с редиректом
3. **Token exchange**: 
   - Клиент отправляет `POST /token` с code и code_verifier
   - Прокси валидирует PKCE и выдаёт access/refresh токены
4. **Access**: 
   - Клиент обращается к `/mcp/` или `/sse` с `Authorization: Bearer <token>`
   - Middleware валидирует токен и устанавливает креденшилы в context var
   - MCPProxy использует эти креденшилы для создания OneCClient
5. **Refresh**: 
   - Клиент отправляет `POST /token` с grant_type=refresh_token
   - Прокси ротирует токены (старый refresh инвалидируется)

## Безопасность

- Пароли 1С хранятся только в оперативной памяти в составе токенов
- Обязательна поддержка PKCE S256 (без plain)
- Короткие TTL для кодов (2 минуты) и access токенов (1 час)
- Ротация refresh токенов при каждом обновлении
- Рекомендуется запуск за HTTPS-терминатором для продакшна

## Ограничения

- Только HTTP-режим (stdio остаётся без изменений)
- In-memory хранилище (при рестарте все токены сбрасываются)
- Только Authorization Code + PKCE S256
- Валидация креденшилов через health endpoint 1С

## Тестирование

Для smoke-теста можно использовать curl:

```bash
# 1. Получить PRM
curl http://localhost:8000/.well-known/oauth-protected-resource

# 2. Сгенерировать PKCE локально
# code_verifier = random 43-128 символов
# code_challenge = base64url(sha256(code_verifier))

# 3. Открыть в браузере
# http://localhost:8000/authorize?response_type=code&client_id=test&redirect_uri=http://localhost/callback&code_challenge=CHALLENGE&code_challenge_method=S256&state=STATE

# 4. Обменять код на токены
curl -X POST http://localhost:8000/token \
  -d "grant_type=authorization_code" \
  -d "code=CODE" \
  -d "redirect_uri=http://localhost/callback" \
  -d "code_verifier=VERIFIER"

# 5. Использовать access token
curl http://localhost:8000/mcp/ \
  -H "Authorization: Bearer ACCESS_TOKEN"
```


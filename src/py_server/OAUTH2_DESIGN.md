## OAuth2 → Basic для Python‑прокси MCP (проект 1C MCP)

Цель: добавить опциональную авторизацию через OAuth 2.1 (Authorization Code + PKCE) в HTTP‑режиме Python‑прокси. После получения `Bearer` токена прокси автоматически транслирует его в Basic‑авторизацию к 1С (логин/пароль), не меняя бизнес‑логику. В режиме `AUTH_MODE=none` поведение остаётся прежним.

Ниже — краткая, но проработанная архитектура и перечень изменений по файлам.


## Режимы

- `AUTH_MODE=none` — как сейчас; все HTTP эндпоинты доступны без OAuth2.
- `AUTH_MODE=oauth2` — включается OAuth 2.1 Code+PKCE. Защищаются MCP‑транспорты (`/mcp/`, `/sse`, `/sse/messages/`).
- Применимо только к HTTP‑режиму. Stdio‑режим остаётся без изменений.


## Обзор потоков

1) Discovery (PRM, RFC 9728)
- Клиент читает `GET /.well-known/oauth-protected-resource` и получает метаданные:
  - `resource` — публичный базовый URL прокси (напр. `https://mcp-proxy.local`)
  - `authorization_servers` — список AS (в этом варианте сам прокси)
  - `authorization_endpoint`, `token_endpoint`
  - `code_challenge_methods_supported=["S256"]`

2) Авторизация (Authorization Code + PKCE)
- `GET /authorize` с query: `response_type=code`, `client_id`, `redirect_uri`, `state`, `code_challenge`, `code_challenge_method=S256`.
- Прокси показывает HTML форму логин/пароль 1С, валидирует их пробным Basic‑запросом к безопасному эндпоинту 1С (health).
- Генерируется короткоживущий `authorization_code` и выполняется `302` на `redirect_uri?code=...&state=...`.

3) Обмен код → токены
- `POST /token` с `grant_type=authorization_code`, `code`, `redirect_uri`, `code_verifier`.
- Проверка кода, совпадения `redirect_uri`, валидация PKCE (S256): `base64url(sha256(code_verifier)) == code_challenge`.
- Ответ JSON: `access_token`, `token_type=Bearer`, `expires_in`, `refresh_token`.

4) Обновление по `refresh_token`
- `POST /token` с `grant_type=refresh_token`, `refresh_token`.
- Валидация, ротация refresh‑токена (старый инвалидируется), выдача нового пары токенов.

5) Доступ к защищённым MCP ресурсам
- Клиент вызывает `/mcp/` (Streamable HTTP) и/или `/sse` с заголовком `Authorization: Bearer <access_token>`.
- Прокси валидирует токен, достаёт `{login,password}` и для всех запросов в 1С ставит `Authorization: Basic <base64(login:password)>`.


## Хранилище (in‑memory, процесс)

- `auth_codes[code] = { login, password, redirect_uri, code_challenge, exp }`
- `access_tokens[token] = { login, password, exp }`
- `refresh_tokens[token] = { login, password, exp, rotation_counter }`
- Очистка по TTL периодической задачей. Ничего не пишем на диск; при рестарте — обнуление.
- Рекомендуемые TTL по умолчанию (из .env): `CODE_TTL=120s`, `ACCESS_TTL=3600s`, `REFRESH_TTL=14d`.


## Точки интеграции в текущий код

Важно: в HTTP‑режиме MCP‑транспорты монтируются как ASGI‑приложения (`/mcp/`, `/sse`). Для защиты их трафика потребуется прослойка ASGI‑middleware, которая:
1) Проверяет `Authorization: Bearer` и валидирует токен (при `AUTH_MODE=oauth2`).
2) Кладает в контекст выполнения текущие 1С‑креды (`login`, `password`).
3) Делегирует управление в существующие транспорты.

Чтобы передать креды в `MCPProxy` на уровне каждой MCP‑сессии, используем `contextvars`:
- В HTTP прослойке устанавливаем `current_auth_ctx.set({login,password})`.
- В `MCPProxy._lifespan` читаем этот контекст и создаём `OneCClient` с кредами из токена (или дефолтными из конфигурации, если `AUTH_MODE=none`). Так обеспечивается per‑session привязка MCP к учётке 1С.


## Изменения по файлам (без кода)

### 1) `src/py_server/config.py`
- Добавить поля:
  - `auth_mode: Literal["none","oauth2"] = "none"`
  - `public_url: str | None` — публичный URL прокси для PRM/redirect ссылок.
  - `oauth2_code_ttl_s: int = 120`
  - `oauth2_access_ttl_s: int = 3600`
  - `oauth2_refresh_ttl_s: int = 1209600` (14 дней)
- Обновить описание `.env`/префикс `MCP_` и валидацию.

### 2) `src/py_server/http_server.py`
- Регистрация открытых эндпоинтов (работают всегда):
  - `GET /.well-known/oauth-protected-resource` — PRM документ (RFC 9728) с полями `resource`, `authorization_servers`, `authorization_endpoint`, `token_endpoint`, `code_challenge_methods_supported=["S256"]`. Брать `public_url` из конфигурации (если не задан, формировать из текущего запроса: схема+хост).
  - `GET /authorize` — принимает параметры, отдаёт HTML форму логина/пароля 1С; обрабатывает submit: валидирует креды через безопасный вызов к 1С (health), создаёт `authorization_code`, делает `302` на `redirect_uri` с `code` и `state`.
  - `POST /token` — поддержать `grant_type=authorization_code` и `grant_type=refresh_token`; PKCE S256, ротация refresh.
- Защита существующих транспортов при `auth_mode=oauth2`:
  - Добавить ASGI‑middleware уровня приложения, которое перехватывает запросы к путям `/mcp/`, `/sse`, `/sse/messages/`.
  - Валидация заголовка `Authorization: Bearer` → извлечение `{login,password}` из in‑memory хранилища.
  - Установка `contextvars` с кредами перед делегированием в `StreamableHTTPSessionManager` и `SseServerTransport`.
- `GET /health` оставить незашищённым (для мониторинга). Опционально добавить поле `auth: { mode: "none"|"oauth2" }` в ответ.

### 3) Новый модуль `src/py_server/auth/`
- `__init__.py` — пустой.
- `models.py` — структуры данных для `AuthCodeData`, `AccessTokenData`, `RefreshTokenData` (с exp и служебными полями).
- `store.py` — in‑memory хранилище с TTL и периодической очисткой (асинхронная задача на старте HTTP‑сервера).
- `service.py` — бизнес‑логика OAuth2:
  - генерация/валидация authorization code
  - PKCE (только S256)
  - выпуск/валидация access/refresh токенов
  - ротация refresh
  - выдача PRM документа на основании конфигурации

Примечание: допускается упростить и разместить `store` и `service` в одном `oauth2.py`, если не нужен разнос по файлам.

### 4) `src/py_server/mcp_server.py`
- В начале файла завести `contextvars.ContextVar[tuple[str,str] | None]` (напр., `current_onec_credentials`).
- В `_lifespan(...)`:
  - При `auth_mode=oauth2` пытаться прочитать креды из `current_onec_credentials`.
  - Если они есть — создать `OneCClient(base_url, login, password, service_root)`.
  - Иначе — использовать дефолтные креды из конфигурации (совместимость и режим `none`).
- Остальная логика без изменений. Клиент закрывается в `finally` как сейчас.

### 5) `src/py_server/onec_client.py`
- Без изменений бизнес‑логики. Важно, что клиент и так принимает логин/пароль в конструкторе.

### 6) `src/py_server/main.py`
- CLI/окружение:
  - добавить параметры: `--auth-mode`, `--public-url` и TTL’ы (опционально).
  - загрузка в `os.environ` перед созданием `Config`, как уже сделано для прочих флагов.

### 7) Документация
- Обновить `src/py_server/README.md` и корневой `README.md`:
  - новый раздел "Опциональная авторизация (OAuth2)"
  - переменные окружения: `MCP_AUTH_MODE`, `MCP_PUBLIC_URL`, TTL’ы
  - пример потока авторизации, ограничения и рекомендации

### 8) Тесты (минимум, без реализации сейчас)
- `test_http_oauth2_flow.py` (новый):
  - PRM доступен
  - полный happy‑path Code+PKCE → токены
  - refresh с ротацией
  - доступ к `/mcp/` без токена → 401; с токеном → 200 ( smoke )


## Форматы ответов и ошибки (суммарно)

- PRM (`/.well-known/oauth-protected-resource`): JSON как в RFC 9728 (см. примеры в задаче).
- `/token` (оба `grant_type`):
  - 200 JSON: `{ access_token, token_type: "Bearer", expires_in, refresh_token, scope? }`
  - 400 JSON: `{ "error": "invalid_grant" | "unsupported_grant_type" | "invalid_request" }`
- Защищённые ресурсы:
  - 401 + `WWW-Authenticate: Bearer error="invalid_token"` при отсутствии/некорректности токена.


## Конфигурация (.env, примеры)

- `MCP_AUTH_MODE=oauth2 | none` (по умолчанию `none`)
- `MCP_PUBLIC_URL=https://mcp-proxy.local` (обязательно в бою, иначе собираем из входящего запроса)
- `MCP_OAUTH2_CODE_TTL=120`
- `MCP_OAUTH2_ACCESS_TTL=3600`
- `MCP_OAUTH2_REFRESH_TTL=1209600`


## Безопасность и эксплуатация простыми словами

- Вариант рассчитан на доверенную сеть или запуск за HTTPS‑терминатором (например, реверс‑прокси с TLS). Если нужен доступ из‑вне, обязательно используйте HTTPS.
- Пароли 1С никуда не сохраняются, только находятся в оперативной памяти, привязаны к токенам и очищаются по тайм‑аутам.
- Сами токены — "непрозрачные" строки (opaque), этого достаточно; JWT не требуется.


## Совместимость и откат

- В `AUTH_MODE=none` поведение полностью прежнее.
- Переключение режимов не требует миграций; при рестарте in‑memory хранилище очищается (ожидаемо).


## План внедрения (пошагово)

1) Добавить конфигурацию (`config.py`) и CLI флаги (`main.py`).
2) Реализовать in‑memory OAuth2 сервис и хранилище (`auth/`).
3) Добавить PRM, `/authorize`, `/token` в `http_server.py`.
4) Ввести ASGI‑middleware для `/mcp/` и `/sse` и контекст `contextvars`.
5) Обновить `MCPProxy._lifespan` (пер‑сессийные креды).
6) Обновить документацию; smoke‑тесты потока.


## Ограничения (осознанно)

- Только Authorization Code + PKCE (S256). Упрощённые варианты (без PKCE/"plain") не поддерживаются.
- Нет постоянного хранилища. При рестарте все коды/токены забываются.
- Авторизация применяется только к HTTP транспорту; stdio без изменений.



# Добавление поддержки Streamable HTTP транспорта в Python MCP‑прокси

## Кратко
- Сейчас прокси поддерживает два транспорта MCP: `stdio` и `HTTP + SSE` (см. `src/py_server/stdio_server.py`, `src/py_server/http_server.py`).
- Предлагается добавить третий вариант — Streamable HTTP (потоковый HTTP), сохранив обратную совместимость с SSE.
- Скорее всего потребуется обновление зависимости `mcp` до версии, в которой есть серверный транспорт Streamable HTTP.

## Текущее состояние
- Используется библиотека `mcp` (см. `src/py_server/requirements.txt`: `mcp>=1.0.0`).
- SSE реализован через `mcp.server.sse.SseServerTransport` и монтируется в `FastAPI` как под‑приложение Starlette внутри `src/py_server/http_server.py`:
  - `GET /mcp/sse` — подписка SSE
  - `POST /mcp/messages` — входящие сообщения
- `stdio` режим запускается через `mcp.server.stdio.stdio_server()`.

## Что такое Streamable HTTP в контексте MCP
- Двунаправленное взаимодействие поверх одного HTTP‑запроса за счёт потоковой передачи (chunked transfer): клиент отправляет запрос, сервер стримит ответы/уведомления в теле ответа без SSE.
- Заменяет связку `GET(SSE)+POST(messages)` более простым единым эндпоинтом, лучше работает через прокси/файрволы и упрощает клиентскую часть.

## Изменения по зависимостям
- Обновить `mcp` до версии, в которой присутствует серверный транспорт Streamable HTTP. Указать верхнеуровневую рекомендацию:
  - В `src/py_server/requirements.txt` заменить строку
    - c: `mcp>=1.0.0`
    - на: `mcp>=<актуальная_версия_со_streamable_http>`
  - Точный номер зависит от доступности транспорта в вашей среде. Проверьте документацию релиза вашей версии `mcp` и импорты вида `mcp.server.http` или аналогичные.

## Предлагаемая архитектура
- Сосуществование транспортов:
  - Сохранить SSE для обратной совместимости (старые клиенты).
  - Добавить Streamable HTTP как основной для новых клиентов.
- HTTP‑слой FastAPI/Starlette монтирует оба транспорта на разные пути:
  - SSE: `GET /mcp/sse`, `POST /mcp/messages`
  - Streamable HTTP: `POST /mcp/stream`
- Инициализация MCP‑сервера (`MCPProxy`) не меняется; меняется только способ подключения транспортных потоков к `server.run(read, write, init_opts)`.

## Изменения в коде (пошагово)

1) `requirements.txt`
- Обновить зависимость `mcp` до версии со Streamable HTTP (см. раздел «Изменения по зависимостям»).

2) `src/py_server/http_server.py`
- Добавить монтирование Streamable HTTP транспорта рядом с существующим SSE.
- Примерный шаблон (имена классов/методов могут отличаться в вашей версии SDK; сверяйтесь с документацией `mcp`):

```python
# Новые импорты (примерные, актуализируйте по своей версии SDK)
from mcp.server.http import StreamableHTTPServerTransport  # или похожий класс

class MCPHttpServer:
    def __init__(self, config: Config):
        # ... существующий код ...
        self._mount_sse_app()
        self._mount_streamable_http_app()  # новый вызов
        self._register_routes()

    def _mount_streamable_http_app(self):
        """Монтирование Streamable HTTP транспорта MCP."""
        http_transport = StreamableHTTPServerTransport()

        async def handle_streamable_http(request):
            # Аналогично SSE: получаем Read/Write потоки от транспорта и запускаем MCP
            async with http_transport.connect(
                request.scope,
                request.receive,
                request._send,
            ) as (read_stream, write_stream):
                await self.mcp_proxy.server.run(
                    read_stream,
                    write_stream,
                    self.mcp_proxy.get_initialization_options(),
                )

        # Единая точка входа Streamable HTTP
        self.app.add_api_route(
            "/mcp/stream",
            endpoint=handle_streamable_http,
            methods=["POST"],
        )
```

- Если в вашей версии `mcp` транспорт предоставляет готовое ASGI‑приложение/роуты (например, `http_transport.asgi_app()` или `http_transport.create_starlette_routes()`), то вместо ручного обработчика предпочтительно смонтировать его напрямую и просто обернуть запуск `server.run(...)`:

```python
http_app = http_transport.asgi_app(lambda read, write: self.mcp_proxy.server.run(
    read, write, self.mcp_proxy.get_initialization_options()
))
self.app.mount("/mcp", http_app)  # тогда внутренняя точка будет чем‑то вроде /mcp/stream
```

- Если в вашей версии SDK класс и методы называются иначе, сохраните общий шаблон: транспорт отдаёт пару потоков `(read, write)` для `Server.run(...)`.

3) `src/py_server/main.py`
- Ничего менять не обязательно. HTTP‑режим будет обслуживать и SSE, и Streamable HTTP одновременно.
- Опционально добавить флаг/переменную окружения для выбора транспорта:
  - Env: `MCP_HTTP_TRANSPORT=both|sse|streamable` (по умолчанию `both`).
  - В `http_server.py` условно вызывать `_mount_sse_app()` / `_mount_streamable_http_app()`.

4) `src/py_server/README.md`
- Добавить описание нового эндпоинта `POST /mcp/stream` и краткий раздел «Streamable HTTP vs SSE».

5) Скрипты запуска/подсказки
- Обновить `start_http_server.bat` и любые подсказки в консоли, чтобы показывать ссылку на новый эндпоинт:
  - `🔌 Streamable HTTP для MCP: http://127.0.0.1:8000/mcp/stream`

## Совместимость и миграция
- Ничего не удаляем: SSE остаётся доступным, новые клиенты могут переходить на Streamable HTTP, старые продолжают работать через SSE.
- Настройки безопасности (CORS, проверка заголовков) остаются активными на уровне FastAPI/Starlette. Рекомендуется дополнительно проверять `Origin`/`Host` и ограничивать привязку по умолчанию к `127.0.0.1`.

## Тестирование
- Базовый «дымовый» тест HTTP‑сервера: `GET /health` (как сейчас).
- Интеграционный тест Streamable HTTP (псевдокод, зависит от клиента):
  1. Подключиться к `POST /mcp/stream`.
  2. Отправить `initialize`/аналог MCP‑инициализации.
  3. Запросить `tools/list` и проверить успешный ответ.
- Для ручной проверки используйте клиент, поддерживающий Streamable HTTP (Cursor/Claude в версиях с поддержкой нового транспорта), направив его на `http://127.0.0.1:8000/mcp/stream`.

## Потенциальные подводные камни
- Несоответствие имён классов/методов транспорта в разных версиях `mcp`. Обязательно проверьте API вашей установленной версии (модуль `mcp.server.http` или аналогичный).
- Буферизация/таймауты на обратных прокси при chunked‑передаче (настройки `nginx`, `traefik`, `cloudflare`). Рекомендуется тестировать локально без прокси, затем с целевой инфраструктурой.
- Корректная передача бинарных частей/ресурсов: придерживайтесь рекомендаций MCP SDK (обычно — JSON‑сообщения, большие бинарные данные — отдельные URI/ресурсы).

## Резюме изменений
- Добавляем Streamable HTTP как основной современный транспорт, монтируем его рядом с уже существующим SSE без ломки обратной совместимости.
- Обновляем `mcp` до версии со Streamable HTTP.
- В `http_server.py` добавляем `_mount_streamable_http_app()` и роут `POST /mcp/stream`, который подключает пары потоков `(read, write)` к `MCPProxy.server.run(...)`.
- Документацию и подсказки обновляем, тесты дополняем интеграционным сценарием для нового транспорта.
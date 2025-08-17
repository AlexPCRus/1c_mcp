"""HTTP-сервер с поддержкой SSE и Streamable HTTP для MCP."""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.models import InitializationOptions
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.types import Scope, Receive, Send

from .mcp_server import MCPProxy
from .config import Config


logger = logging.getLogger(__name__)


class MCPHttpServer:
	"""HTTP-сервер для MCP с поддержкой SSE и Streamable HTTP."""
	
	def __init__(self, config: Config):
		"""Инициализация HTTP-сервера.
		
		Args:
			config: Конфигурация сервера
		"""
		self.config = config
		self.mcp_proxy = MCPProxy(config)
		
		# Создаем session manager для Streamable HTTP после создания MCP прокси
		self.streamable_session_manager = StreamableHTTPSessionManager(self.mcp_proxy.server)
		
		self.app = FastAPI(
			title="1C MCP Proxy",
			description="MCP-прокси для взаимодействия с 1С",
			version=config.server_version,
			lifespan=self._lifespan
		)
		
		# Настройка CORS
		self.app.add_middleware(
			CORSMiddleware,
			allow_origins=config.cors_origins,
			allow_credentials=True,
			allow_methods=["*"],
			allow_headers=["*"],
		)
		
		# Монтируем транспорты
		self._mount_transports()
		
		# Регистрация основных маршрутов
		self._register_routes()
	
	@asynccontextmanager
	async def _lifespan(self, app: FastAPI):
		"""Управление жизненным циклом приложения."""
		logger.debug("Запуск HTTP-сервера MCP")
		
		# Запускаем session manager для Streamable HTTP
		async with self.streamable_session_manager.run():
			yield
		
		logger.debug("Остановка HTTP-сервера MCP")
	
	def _create_sse_starlette_app(self) -> Starlette:
		"""Создание Starlette приложения для обработки SSE."""
		# Создаем SSE транспорт для обработки сообщений
		sse_transport = SseServerTransport("/messages/")
		
		async def handle_sse(request):
			"""Обработчик SSE подключений."""
			logger.debug("Новое SSE подключение")
			
			try:
				# Подключаем SSE с использованием транспорта
				async with sse_transport.connect_sse(
					request.scope, 
					request.receive, 
					request._send
				) as streams:
					# Запускаем MCP сервер с потоками
					await self.mcp_proxy.server.run(
						streams[0], 
						streams[1], 
						self.mcp_proxy.get_initialization_options()
					)
			except Exception as e:
				logger.error(f"Ошибка в SSE обработчике: {e}")
				raise
			finally:
				logger.debug("SSE подключение закрыто")
		
		# Создаем маршруты для Starlette приложения
		# Когда это приложение монтируется на /sse:
		# - Route("/", ...) становится GET /sse (SSE подключение)
		# - Mount("/messages/", ...) становится POST /sse/messages/ (отправка сообщений)
		routes = [
			Route("/", endpoint=handle_sse),  # SSE endpoint: GET /sse
			Mount("/messages/", app=sse_transport.handle_post_message),  # Messages: POST /sse/messages/
		]
		
		return Starlette(routes=routes)
	
	def _create_streamable_http_asgi(self):
		"""Создание ASGI обработчика для Streamable HTTP."""
		
		async def asgi(scope: Scope, receive: Receive, send: Send) -> None:
			"""ASGI обработчик для Streamable HTTP соединений."""
			logger.debug("Новое Streamable HTTP подключение")
			
			try:
				# Используем правильный API handle_request для ASGI
				await self.streamable_session_manager.handle_request(scope, receive, send)
			except Exception as e:
				logger.error(f"Ошибка в Streamable HTTP обработчике: {e}")
				raise
			finally:
				logger.debug("Streamable HTTP подключение закрыто")
		
		return asgi
	
	def _mount_transports(self):
		"""Монтирование транспортов MCP."""
		
		# Монтируем SSE транспорт на /sse
		sse_app = self._create_sse_starlette_app()
		self.app.mount("/sse", sse_app)
		
		# Монтируем Streamable HTTP транспорт на /mcp/ (с trailing slash для устранения 307 редиректов)
		streamable_app = self._create_streamable_http_asgi()
		self.app.mount("/mcp/", streamable_app)
	
	def _register_routes(self):
		"""Регистрация основных маршрутов."""
		
		@self.app.get("/")
		async def root():
			"""Корневой маршрут - перенаправляет на info."""
			return {
				"message": "1C MCP Proxy Server",
				"endpoints": {
					"info": "/info",
					"health": "/health",
					"sse": "/sse",
					"streamable_http": "/mcp/"
				}
			}
		
		@self.app.get("/info")
		async def info():
			"""Информационный маршрут."""
			return {
				"name": self.config.server_name,
				"version": self.config.server_version,
				"description": "MCP-прокси для взаимодействия с 1С",
				"endpoints": {
					"sse": "/sse",
					"messages": "/sse/messages/",
					"streamable_http": "/mcp/",
					"health": "/health",
					"info": "/info"
				},
				"transports": {
					"sse": {
						"endpoint": "/sse",
						"messages": "/sse/messages/"
					},
					"streamable_http": {
						"endpoint": "/mcp/"
					}
				}
			}
		
		@self.app.get("/health")
		async def health():
			"""Проверка здоровья сервера."""
			try:
				# Проверяем подключение к 1С через прокси
				if hasattr(self.mcp_proxy, 'onec_client') and self.mcp_proxy.onec_client:
					await self.mcp_proxy.onec_client.check_health()
					return {"status": "healthy", "onec_connection": "ok"}
				else:
					return {"status": "starting", "onec_connection": "not_initialized"}
			except Exception as e:
				logger.error(f"Ошибка проверки здоровья: {e}")
				return {"status": "unhealthy", "onec_connection": "error", "error_details": str(e)}
	
	async def start(self):
		"""Запуск HTTP-сервера."""
		config = uvicorn.Config(
			app=self.app,
			host=self.config.host,
			port=self.config.port,
			log_level=self.config.log_level.lower(),
			access_log=True
		)
		
		server = uvicorn.Server(config)
		logger.debug(f"Запуск HTTP-сервера на {self.config.host}:{self.config.port}")
		await server.serve()


async def run_http_server(config: Config):
	"""Запуск HTTP-сервера.
	
	Args:
		config: Конфигурация сервера
	"""
	server = MCPHttpServer(config)
	await server.start() 
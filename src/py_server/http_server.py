"""HTTP-сервер с поддержкой SSE для MCP."""

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
from mcp.server.models import InitializationOptions
from starlette.applications import Starlette
from starlette.routing import Mount, Route

from .mcp_server import MCPProxy
from .config import Config


logger = logging.getLogger(__name__)


class MCPHttpServer:
	"""HTTP-сервер для MCP с поддержкой SSE."""
	
	def __init__(self, config: Config):
		"""Инициализация HTTP-сервера.
		
		Args:
			config: Конфигурация сервера
		"""
		self.config = config
		self.mcp_proxy = MCPProxy(config)
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
		
		# Создаем и монтируем Starlette приложение для SSE
		self._mount_sse_app()
		
		# Регистрация основных маршрутов
		self._register_routes()
	
	@asynccontextmanager
	async def _lifespan(self, app: FastAPI):
		"""Управление жизненным циклом приложения."""
		logger.info("Запуск HTTP-сервера MCP")
		yield
		logger.info("Остановка HTTP-сервера MCP")
	
	def _create_sse_starlette_app(self) -> Starlette:
		"""Создание Starlette приложения для обработки SSE."""
		# Создаем SSE транспорт для обработки сообщений
		sse_transport = SseServerTransport("/messages/")
		
		async def handle_sse(request):
			"""Обработчик SSE подключений."""
			logger.info("Новое SSE подключение")
			
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
				logger.info("SSE подключение закрыто")
		
		# Создаем маршруты для Starlette приложения
		routes = [
			Route("/sse", endpoint=handle_sse),
			Mount("/messages/", app=sse_transport.handle_post_message),
		]
		
		return Starlette(routes=routes)
	
	def _mount_sse_app(self):
		"""Монтирование Starlette приложения для SSE."""
		sse_app = self._create_sse_starlette_app()
		# Монтируем SSE приложение НЕ на корневой путь, чтобы не конфликтовало с FastAPI маршрутами
		self.app.mount("/mcp", sse_app)
	
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
					"sse": "/mcp/sse"
				}
			}
		
		@self.app.get("/info")
		async def info():
			"""Информационный маршрут (не конфликтует с SSE)."""
			return {
				"name": self.config.server_name,
				"version": self.config.server_version,
				"description": "MCP-прокси для взаимодействия с 1С",
				"endpoints": {
					"sse": "/mcp/sse",
					"messages": "/mcp/messages/",
					"health": "/health",
					"info": "/info"
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
		logger.info(f"Запуск HTTP-сервера на {self.config.host}:{self.config.port}")
		await server.serve()


async def run_http_server(config: Config):
	"""Запуск HTTP-сервера.
	
	Args:
		config: Конфигурация сервера
	"""
	server = MCPHttpServer(config)
	await server.start() 
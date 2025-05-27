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
		
		# Регистрация маршрутов
		self._register_routes()
		
		# Хранилище SSE транспортов
		self.sse_transports: Dict[str, SseServerTransport] = {}
	
	@asynccontextmanager
	async def _lifespan(self, app: FastAPI):
		"""Управление жизненным циклом приложения."""
		logger.info("Запуск HTTP-сервера MCP")
		yield
		logger.info("Остановка HTTP-сервера MCP")
	
	def _register_routes(self):
		"""Регистрация маршрутов."""
		
		@self.app.get("/")
		async def root():
			"""Корневой маршрут."""
			return {
				"name": self.config.server_name,
				"version": self.config.server_version,
				"description": "MCP-прокси для взаимодействия с 1С",
				"endpoints": {
					"sse": "/sse",
					"messages": "/messages"
				}
			}
		
		@self.app.get("/health")
		async def health():
			"""Проверка здоровья сервера."""
			try:
				# Проверяем подключение к 1С через прокси
				if hasattr(self.mcp_proxy, 'onec_client') and self.mcp_proxy.onec_client:
					await self.mcp_proxy.onec_client.get_manifest()
					return {"status": "healthy", "onec_connection": "ok"}
				else:
					return {"status": "starting", "onec_connection": "not_initialized"}
			except Exception as e:
				logger.error(f"Ошибка проверки здоровья: {e}")
				return {"status": "unhealthy", "error": str(e)}
		
		@self.app.get("/sse")
		async def handle_sse(request: Request):
			"""Обработка SSE подключений."""
			client_id = request.headers.get("x-client-id", "default")
			
			logger.info(f"Новое SSE подключение: {client_id}")
			
			# Создаем SSE транспорт
			sse_transport = SseServerTransport("/messages")
			self.sse_transports[client_id] = sse_transport
			
			async def event_stream():
				try:
					async with sse_transport.connect_sse(
						request.scope, 
						request.receive, 
						None  # send будет установлен через StreamingResponse
					) as streams:
						# Запускаем MCP сервер с SSE транспортом
						await self.mcp_proxy.server.run(
							streams[0], 
							streams[1], 
							self.mcp_proxy.get_initialization_options()
						)
				except Exception as e:
					logger.error(f"Ошибка в SSE потоке для клиента {client_id}: {e}")
				finally:
					# Удаляем транспорт при отключении
					if client_id in self.sse_transports:
						del self.sse_transports[client_id]
					logger.info(f"SSE подключение закрыто: {client_id}")
			
			return StreamingResponse(
				event_stream(),
				media_type="text/event-stream",
				headers={
					"Cache-Control": "no-cache",
					"Connection": "keep-alive",
					"Access-Control-Allow-Origin": "*",
					"Access-Control-Allow-Headers": "*",
				}
			)
		
		@self.app.post("/messages")
		async def handle_messages(request: Request):
			"""Обработка POST сообщений от клиентов."""
			client_id = request.headers.get("x-client-id", "default")
			
			if client_id not in self.sse_transports:
				raise HTTPException(
					status_code=404, 
					detail=f"SSE транспорт для клиента {client_id} не найден"
				)
			
			try:
				# Получаем JSON данные
				data = await request.json()
				logger.debug(f"Получено сообщение от клиента {client_id}: {data}")
				
				# Передаем сообщение в SSE транспорт
				sse_transport = self.sse_transports[client_id]
				await sse_transport.handle_post_message(
					request.scope,
					request.receive,
					None  # send не используется для POST
				)
				
				return {"status": "ok"}
				
			except json.JSONDecodeError as e:
				logger.error(f"Ошибка парсинга JSON от клиента {client_id}: {e}")
				raise HTTPException(status_code=400, detail="Неверный JSON")
			except Exception as e:
				logger.error(f"Ошибка обработки сообщения от клиента {client_id}: {e}")
				raise HTTPException(status_code=500, detail=str(e))
	
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
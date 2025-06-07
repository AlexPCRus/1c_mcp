"""Основной MCP-сервер, который проксирует запросы в 1С."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, AsyncIterator

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.lowlevel import NotificationOptions
from mcp import types

from onec_client import OneCClient
from config import Config


logger = logging.getLogger(__name__)


class MCPProxy:
	"""MCP-прокси сервер для взаимодействия с 1С."""
	
	def __init__(self, config: Config):
		"""Инициализация прокси.
		
		Args:
			config: Конфигурация сервера
		"""
		self.config = config
		self.onec_client: Optional[OneCClient] = None
		
		# Создаем MCP сервер
		self.server = Server(
			name=config.server_name,
			lifespan=self._lifespan
		)
		
		# Регистрируем обработчики
		self._register_handlers()
	
	@asynccontextmanager
	async def _lifespan(self, server: Server) -> AsyncIterator[Dict[str, Any]]:
		"""Управление жизненным циклом сервера."""
		# Инициализация при запуске
		self.onec_client = OneCClient(
			base_url=self.config.onec_url,
			username=self.config.onec_username,
			password=self.config.onec_password,
			service_root=self.config.onec_service_root
		)
		
		logger.info(f"Подключение к 1С: {self.config.onec_url}")
		logger.info(f"HTTP-сервис: {self.config.onec_service_root}")
		
		try:
			# Проверяем подключение к 1С
			await self.onec_client.check_health()
			logger.info("Успешное подключение к 1С (проверка health)")
			
			yield {"onec_client": self.onec_client}
		finally:
			# Очистка при завершении
			if self.onec_client:
				await self.onec_client.close()
				logger.info("Соединение с 1С закрыто")
	
	def _register_handlers(self):
		"""Регистрация обработчиков MCP."""
		
		@self.server.list_tools()
		async def handle_list_tools() -> List[types.Tool]:
			"""Получить список доступных инструментов."""
			ctx = self.server.request_context
			onec_client: OneCClient = ctx.lifespan_context["onec_client"]
			
			try:
				tools = await onec_client.list_tools()
				logger.debug(f"Получено инструментов: {len(tools)}")
				return tools
			except Exception as e:
				logger.error(f"Ошибка при получении списка инструментов: {e}")
				return []
		
		@self.server.call_tool()
		async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
			"""Вызвать инструмент."""
			ctx = self.server.request_context
			onec_client: OneCClient = ctx.lifespan_context["onec_client"]
			
			try:
				logger.info(f"Вызов инструмента: {name} с аргументами: {arguments}")
				result = await onec_client.call_tool(name, arguments)
				
				if result.isError:
					logger.error(f"Ошибка выполнения инструмента {name}")
				
				return result.content
			except Exception as e:
				logger.error(f"Ошибка при вызове инструмента {name}: {e}")
				return [types.TextContent(
					type="text",
					text=f"Ошибка выполнения инструмента: {str(e)}"
				)]
		
		@self.server.list_resources()
		async def handle_list_resources() -> List[types.Resource]:
			"""Получить список доступных ресурсов."""
			ctx = self.server.request_context
			onec_client: OneCClient = ctx.lifespan_context["onec_client"]
			
			try:
				resources = await onec_client.list_resources()
				logger.debug(f"Получено ресурсов: {len(resources)}")
				return resources
			except Exception as e:
				logger.error(f"Ошибка при получении списка ресурсов: {e}")
				return []
		
		@self.server.read_resource()
		async def handle_read_resource(uri: str) -> types.ReadResourceResult:
			"""Прочитать ресурс."""
			ctx = self.server.request_context
			onec_client: OneCClient = ctx.lifespan_context["onec_client"]
			
			try:
				logger.info(f"Чтение ресурса: {uri}")
				result = await onec_client.read_resource(uri)
				return result
			except Exception as e:
				logger.error(f"Ошибка при чтении ресурса {uri}: {e}")
				# Возвращаем ReadResourceResult с ошибкой
				return types.ReadResourceResult(
					contents=[
						types.TextResourceContents(
							uri=uri,
							mimeType="text/plain",
							text=f"Ошибка чтения ресурса: {str(e)}"
						)
					]
				)
		
		@self.server.list_prompts()
		async def handle_list_prompts() -> List[types.Prompt]:
			"""Получить список доступных промптов."""
			ctx = self.server.request_context
			onec_client: OneCClient = ctx.lifespan_context["onec_client"]
			
			try:
				prompts = await onec_client.list_prompts()
				logger.debug(f"Получено промптов: {len(prompts)}")
				return prompts
			except Exception as e:
				logger.error(f"Ошибка при получении списка промптов: {e}")
				return []
		
		@self.server.get_prompt()
		async def handle_get_prompt(name: str, arguments: Optional[Dict[str, str]] = None) -> types.GetPromptResult:
			"""Получить промпт."""
			ctx = self.server.request_context
			onec_client: OneCClient = ctx.lifespan_context["onec_client"]
			
			try:
				logger.info(f"Получение промпта: {name} с аргументами: {arguments}")
				result = await onec_client.get_prompt(name, arguments)
				return result
			except Exception as e:
				logger.error(f"Ошибка при получении промпта {name}: {e}")
				return types.GetPromptResult(
					description=f"Ошибка получения промпта: {str(e)}",
					messages=[]
				)
	
	def get_capabilities(self) -> Dict[str, Any]:
		"""Получить capabilities сервера."""
		return {
			"tools": {"listChanged": True},
			"resources": {"subscribe": True, "listChanged": True},
			"prompts": {"listChanged": True},
			"logging": {}
		}
	
	def get_initialization_options(self) -> InitializationOptions:
		"""Получить опции инициализации."""
		return InitializationOptions(
			server_name=self.config.server_name,
			server_version=self.config.server_version,
			capabilities=self.server.get_capabilities(
				notification_options=NotificationOptions(),
				experimental_capabilities={}
			)
		) 
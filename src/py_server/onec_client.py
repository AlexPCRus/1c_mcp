"""Клиент для взаимодействия с 1С."""

import json
import logging
from typing import Any, Dict, List, Optional
import httpx
from mcp import types


logger = logging.getLogger(__name__)


class OneCClient:
	"""Клиент для взаимодействия с HTTP-сервисом 1С."""
	
	def __init__(self, base_url: str, username: str, password: str, service_root: str = "mcp"):
		"""Инициализация клиента.
		
		Args:
			base_url: Базовый URL 1С (например, http://localhost/base)
			username: Имя пользователя
			password: Пароль
			service_root: Корневой URL HTTP-сервиса (по умолчанию "mcp")
		"""
		self.base_url = base_url.rstrip('/')
		self.service_root = service_root.strip('/')
		self.auth = httpx.BasicAuth(username, password)
		self.client = httpx.AsyncClient(
			auth=self.auth,
			timeout=30.0,
			headers={"Content-Type": "application/json"}
		)
		
		# Формируем базовый URL для HTTP-сервиса
		self.service_base_url = f"{self.base_url}/hs/{self.service_root}"
		logger.debug(f"Базовый URL HTTP-сервиса: {self.service_base_url}")
	
	async def check_health(self) -> bool:
		"""Проверить состояние HTTP-сервиса 1С.

		Returns:
			True, если сервис доступен и здоров, иначе вызывает исключение.
		"""
		try:
			url = f"{self.service_base_url}/health"
			logger.debug(f"Запрос состояния здоровья: {url}")

			response = await self.client.get(url)
			response.raise_for_status()

			# Проверяем JSON ответ от 1C healthGET
			try:
				response_json = response.json()
				if response_json.get("status") == "ok":
					logger.debug("Сервис 1С доступен и здоров (статус OK).")
					return True
				else:
					logger.warning(f"1C health check вернул неожиданный статус: {response_json}")
					raise httpx.HTTPStatusError(f"1C service reported not healthy: {response_json}", request=response.request, response=response)
			except json.JSONDecodeError as e:
				logger.error(f"Ошибка парсинга JSON ответа health-check 1С: {response.text}")
				raise httpx.HTTPStatusError(f"Invalid JSON response from 1C health check: {e}", request=response.request, response=response)

		except httpx.HTTPError as e:
			logger.error(f"Ошибка HTTP при проверке состояния 1С: {e}")
			raise
	
	async def call_rpc(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		"""Выполнить JSON-RPC запрос к 1С.
		
		Args:
			method: Имя метода
			params: Параметры метода
			
		Returns:
			Результат выполнения метода
		"""
		try:
			url = f"{self.service_base_url}/rpc"
			
			# Формируем JSON-RPC запрос
			rpc_request = {
				"jsonrpc": "2.0",
				"id": 1,
				"method": method,
				"params": params or {}
			}
			
			logger.debug(f"JSON-RPC запрос: {rpc_request}")
			
			response = await self.client.post(url, json=rpc_request)
			response.raise_for_status()
			
			rpc_response = response.json()
			logger.debug(f"JSON-RPC ответ: {rpc_response}")
			
			# Проверяем на ошибки JSON-RPC
			if "error" in rpc_response:
				error = rpc_response["error"]
				raise Exception(f"JSON-RPC ошибка {error.get('code', 'unknown')}: {error.get('message', 'Unknown error')}")
			
			return rpc_response.get("result", {})
			
		except httpx.HTTPError as e:
			logger.error(f"Ошибка HTTP при вызове RPC: {e}")
			raise
		except json.JSONDecodeError as e:
			logger.error(f"Ошибка парсинга JSON ответа RPC: {e}")
			raise
	
	async def list_tools(self) -> List[types.Tool]:
		"""Получить список доступных инструментов.
		
		Returns:
			Список инструментов MCP
		"""
		result = await self.call_rpc("tools/list")
		tools_data = result.get("tools", [])
		
		tools = []
		for tool_data in tools_data:
			tool = types.Tool(
				name=tool_data["name"],
				description=tool_data.get("description", ""),
				inputSchema=tool_data.get("inputSchema", {})
			)
			tools.append(tool)
		
		return tools
	
	async def call_tool(self, name: str, arguments: Dict[str, Any]) -> types.CallToolResult:
		"""Вызвать инструмент.
		
		Args:
			name: Имя инструмента
			arguments: Аргументы инструмента
			
		Returns:
			Результат выполнения инструмента
		"""
		result = await self.call_rpc("tools/call", {
			"name": name,
			"arguments": arguments
		})
		
		# Преобразуем результат в формат MCP
		content = []
		if "content" in result:
			for item in result["content"]:
				content_type = item.get("type")
				
				if content_type == "text":
					content.append(types.TextContent(
						type="text",
						text=item.get("text", "")
					))
				
				elif content_type == "image":
					content.append(types.ImageContent(
						type="image",
						data=item.get("data", ""),
						mimeType=item.get("mimeType", "image/png")
					))
				
				else:
					# Неизвестный тип - логируем предупреждение и обрабатываем как текст
					logger.warning(f"Неизвестный тип контента: {content_type}, обрабатываем как текст")
					content.append(types.TextContent(
						type="text",
						text=str(item.get("text", item))
					))
		
		return types.CallToolResult(
			content=content,
			isError=result.get("isError", False)
		)
	
	async def list_resources(self) -> List[types.Resource]:
		"""Получить список доступных ресурсов.
		
		Returns:
			Список ресурсов MCP
		"""
		result = await self.call_rpc("resources/list")
		resources_data = result.get("resources", [])
		
		resources = []
		for resource_data in resources_data:
			resource = types.Resource(
				uri=resource_data["uri"],
				name=resource_data.get("name", ""),
				description=resource_data.get("description", ""),
				mimeType=resource_data.get("mimeType")
			)
			resources.append(resource)
		
		return resources
	
	async def read_resource(self, uri: str) -> types.ReadResourceResult:
		"""Прочитать ресурс.
		
		Args:
			uri: URI ресурса
			
		Returns:
			Содержимое ресурса
		"""
		result = await self.call_rpc("resources/read", {"uri": uri})
		
		# Преобразуем результат в формат MCP
		contents = []
		if "contents" in result:
			for item in result["contents"]:
				content_type = item.get("type")
				
				if content_type == "text":
					contents.append(types.TextResourceContents(
						uri=uri,
						mimeType=item.get("mimeType", "text/plain"),
						text=item.get("text", "")
					))
				
				elif content_type == "blob":
					contents.append(types.BlobResourceContents(
						uri=uri,
						mimeType=item.get("mimeType", "application/octet-stream"),
						blob=item.get("blob", "")
					))
				
				else:
					# Неизвестный тип - логируем предупреждение и обрабатываем как текст
					logger.warning(f"Неизвестный тип ресурса: {content_type}, обрабатываем как текст")
					
					# Пытаемся извлечь текст разными способами
					text_content = ""
					if "text" in item:
						text_content = str(item["text"])
					elif "data" in item:
						text_content = str(item["data"])
					elif "content" in item:
						text_content = str(item["content"])
					else:
						# Если ничего подходящего нет, используем JSON представление
						text_content = f"Неизвестный тип ресурса '{content_type}': {json.dumps(item, ensure_ascii=False)}"
					
					contents.append(types.TextResourceContents(
						uri=uri,
						mimeType=item.get("mimeType", "text/plain"),
						text=text_content
					))
		
		return types.ReadResourceResult(contents=contents)
	
	async def list_prompts(self) -> List[types.Prompt]:
		"""Получить список доступных промптов.
		
		Returns:
			Список промптов MCP
		"""
		result = await self.call_rpc("prompts/list")
		prompts_data = result.get("prompts", [])
		
		prompts = []
		for prompt_data in prompts_data:
			arguments = []
			if "arguments" in prompt_data:
				for arg_data in prompt_data["arguments"]:
					arguments.append(types.PromptArgument(
						name=arg_data["name"],
						description=arg_data.get("description", ""),
						required=arg_data.get("required", False)
					))
			
			prompt = types.Prompt(
				name=prompt_data["name"],
				description=prompt_data.get("description", ""),
				arguments=arguments
			)
			prompts.append(prompt)
		
		return prompts
	
	async def get_prompt(self, name: str, arguments: Optional[Dict[str, str]] = None) -> types.GetPromptResult:
		"""Получить промпт.
		
		Args:
			name: Имя промпта
			arguments: Аргументы промпта
			
		Returns:
			Результат промпта
		"""
		result = await self.call_rpc("prompts/get", {
			"name": name,
			"arguments": arguments or {}
		})
		
		# Преобразуем результат в формат MCP
		messages = []
		if "messages" in result:
			for msg_data in result["messages"]:
				content = types.TextContent(
					type="text",
					text=msg_data.get("content", {}).get("text", "")
				)
				
				message = types.PromptMessage(
					role=msg_data.get("role", "user"),
					content=content
				)
				messages.append(message)
		
		return types.GetPromptResult(
			description=result.get("description", ""),
			messages=messages
		)
	
	async def close(self):
		"""Закрыть клиент."""
		await self.client.aclose() 
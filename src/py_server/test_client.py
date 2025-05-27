"""Простой тестовый клиент для проверки MCP-прокси."""

import asyncio
import json
import logging
from typing import Dict, Any

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .config import get_config


logger = logging.getLogger(__name__)


async def test_onec_connection(config):
	"""Тест прямого подключения к 1С."""
	print("=== Тест подключения к 1С ===")
	
	try:
		async with httpx.AsyncClient(
			auth=httpx.BasicAuth(config.onec_username, config.onec_password),
			timeout=10.0
		) as client:
			# Тест манифеста
			manifest_url = f"{config.onec_url}/mcp/manifest"
			print(f"Запрос манифеста: {manifest_url}")
			
			response = await client.get(manifest_url)
			response.raise_for_status()
			
			manifest = response.json()
			print(f"✅ Манифест получен: {json.dumps(manifest, indent=2, ensure_ascii=False)}")
			
			# Тест RPC
			rpc_url = f"{config.onec_url}/mcp/rpc"
			rpc_request = {
				"jsonrpc": "2.0",
				"id": 1,
				"method": "tools/list",
				"params": {}
			}
			
			print(f"Запрос RPC: {rpc_url}")
			print(f"Данные: {json.dumps(rpc_request, ensure_ascii=False)}")
			
			response = await client.post(rpc_url, json=rpc_request)
			response.raise_for_status()
			
			rpc_response = response.json()
			print(f"✅ RPC ответ: {json.dumps(rpc_response, indent=2, ensure_ascii=False)}")
			
	except Exception as e:
		print(f"❌ Ошибка подключения к 1С: {e}")
		return False
	
	return True


async def test_mcp_stdio():
	"""Тест MCP-прокси через stdio."""
	print("\n=== Тест MCP-прокси (stdio) ===")
	
	try:
		# Параметры для запуска прокси
		server_params = StdioServerParameters(
			command="python",
			args=["-m", "src.py_server", "stdio"],
			env={
				"MCP_ONEC_URL": "http://localhost/your_base",
				"MCP_ONEC_USERNAME": "username", 
				"MCP_ONEC_PASSWORD": "password"
			}
		)
		
		print("Запуск MCP-прокси...")
		
		async with stdio_client(server_params) as (read, write):
			async with ClientSession(read, write) as session:
				print("✅ Подключение к MCP-прокси установлено")
				
				# Инициализация
				await session.initialize()
				print("✅ Инициализация завершена")
				
				# Список инструментов
				tools = await session.list_tools()
				print(f"✅ Получено инструментов: {len(tools.tools)}")
				for tool in tools.tools:
					print(f"  - {tool.name}: {tool.description}")
				
				# Список ресурсов
				resources = await session.list_resources()
				print(f"✅ Получено ресурсов: {len(resources.resources)}")
				for resource in resources.resources:
					print(f"  - {resource.uri}: {resource.name}")
				
				# Список промптов
				prompts = await session.list_prompts()
				print(f"✅ Получено промптов: {len(prompts.prompts)}")
				for prompt in prompts.prompts:
					print(f"  - {prompt.name}: {prompt.description}")
				
	except Exception as e:
		print(f"❌ Ошибка тестирования MCP-прокси: {e}")
		return False
	
	return True


async def test_http_server():
	"""Тест HTTP-сервера."""
	print("\n=== Тест HTTP-сервера ===")
	
	try:
		async with httpx.AsyncClient(timeout=10.0) as client:
			# Тест корневого endpoint
			response = await client.get("http://localhost:8000/")
			response.raise_for_status()
			
			info = response.json()
			print(f"✅ Информация о сервере: {json.dumps(info, indent=2, ensure_ascii=False)}")
			
			# Тест health check
			response = await client.get("http://localhost:8000/health")
			response.raise_for_status()
			
			health = response.json()
			print(f"✅ Состояние сервера: {json.dumps(health, indent=2, ensure_ascii=False)}")
			
	except Exception as e:
		print(f"❌ Ошибка тестирования HTTP-сервера: {e}")
		return False
	
	return True


async def main():
	"""Основная функция тестирования."""
	logging.basicConfig(level=logging.INFO)
	
	print("🧪 Запуск тестов MCP-прокси")
	
	try:
		config = get_config()
		print(f"Конфигурация загружена: {config.onec_url}")
	except Exception as e:
		print(f"❌ Ошибка загрузки конфигурации: {e}")
		print("Создайте .env файл с настройками или установите переменные окружения")
		return
	
	# Тест подключения к 1С
	if not await test_onec_connection(config):
		print("❌ Тесты остановлены из-за ошибки подключения к 1С")
		return
	
	# Тест MCP-прокси (требует запущенного прокси)
	print("\n⚠️  Для тестирования MCP-прокси запустите его в отдельном терминале:")
	print("   python -m src.py_server stdio")
	print("   или")
	print("   python -m src.py_server http")
	
	# Тест HTTP-сервера (если запущен)
	try:
		await test_http_server()
	except:
		print("⚠️  HTTP-сервер не запущен или недоступен")
	
	print("\n✅ Тестирование завершено")


if __name__ == "__main__":
	asyncio.run(main()) 
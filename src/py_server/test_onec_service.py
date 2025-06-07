#!/usr/bin/env python3
"""Тестирование HTTP-сервиса 1С MCP API.

Этот модуль тестирует функциональность HTTP-сервиса 1С через onec_client.
Проверяет health endpoint и получает списки инструментов, ресурсов и промптов.
"""

import asyncio
import json
import logging
from typing import Dict, Any
import sys
from pathlib import Path

# Добавляем текущую директорию в путь для импорта onec_client
sys.path.insert(0, str(Path(__file__).parent))

from onec_client import OneCClient

# Настройка логирования
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestOneCService:
	"""Класс для тестирования HTTP-сервиса 1С."""
	
	def __init__(self, base_url: str, username: str, password: str):
		"""Инициализация тестера.
		
		Args:
			base_url: Базовый URL 1С (например, http://localhost/base)
			username: Имя пользователя
			password: Пароль
		"""
		self.client = OneCClient(base_url, username, password)
		self.results = {}
	
	async def test_health(self) -> bool:
		"""Тестирует health endpoint."""
		print("🏥 Тестирование Health endpoint...")
		try:
			result = await self.client.check_health()
			if result:
				print("✅ Health check успешен - сервис доступен")
				self.results['health'] = {'status': 'success', 'message': 'Сервис доступен'}
				return True
			else:
				print("❌ Health check неуспешен")
				self.results['health'] = {'status': 'error', 'message': 'Health check вернул False'}
				return False
		except Exception as e:
			print(f"❌ Ошибка Health check: {e}")
			self.results['health'] = {'status': 'error', 'message': str(e)}
			return False
	
	async def test_list_tools(self) -> bool:
		"""Тестирует получение списка инструментов."""
		print("\n🔧 Тестирование списка инструментов...")
		try:
			tools = await self.client.list_tools()
			print(f"✅ Получено {len(tools)} инструментов:")
			
			for i, tool in enumerate(tools, 1):
				print(f"  {i}. {tool.name}")
				print(f"     Описание: {tool.description}")
				if hasattr(tool, 'inputSchema') and tool.inputSchema:
					schema_str = json.dumps(tool.inputSchema, ensure_ascii=False, indent=6)
					print(f"     Схема параметров:\n{schema_str}")
				print()
			
			self.results['tools'] = {
				'status': 'success', 
				'count': len(tools),
				'tools': [{'name': t.name, 'description': t.description} for t in tools]
			}
			return True
			
		except Exception as e:
			print(f"❌ Ошибка получения списка инструментов: {e}")
			self.results['tools'] = {'status': 'error', 'message': str(e)}
			return False
	
	async def test_list_resources(self) -> bool:
		"""Тестирует получение списка ресурсов."""
		print("\n📁 Тестирование списка ресурсов...")
		try:
			resources = await self.client.list_resources()
			print(f"✅ Получено {len(resources)} ресурсов:")
			
			for i, resource in enumerate(resources, 1):
				print(f"  {i}. {resource.name}")
				print(f"     URI: {resource.uri}")
				print(f"     Описание: {resource.description}")
				if hasattr(resource, 'mimeType') and resource.mimeType:
					print(f"     MIME-тип: {resource.mimeType}")
				print()
			
			self.results['resources'] = {
				'status': 'success',
				'count': len(resources),
				'resources': [{'name': r.name, 'uri': r.uri, 'description': r.description} for r in resources]
			}
			return True
			
		except Exception as e:
			print(f"❌ Ошибка получения списка ресурсов: {e}")
			self.results['resources'] = {'status': 'error', 'message': str(e)}
			return False
	
	async def test_list_prompts(self) -> bool:
		"""Тестирует получение списка промптов."""
		print("\n💬 Тестирование списка промптов...")
		try:
			prompts = await self.client.list_prompts()
			print(f"✅ Получено {len(prompts)} промптов:")
			
			for i, prompt in enumerate(prompts, 1):
				print(f"  {i}. {prompt.name}")
				print(f"     Описание: {prompt.description}")
				if hasattr(prompt, 'arguments') and prompt.arguments:
					print(f"     Аргументы ({len(prompt.arguments)}):")
					for arg in prompt.arguments:
						required_mark = "обязательный" if arg.required else "опциональный"
						print(f"       - {arg.name} ({required_mark}): {arg.description}")
				print()
			
			self.results['prompts'] = {
				'status': 'success',
				'count': len(prompts),
				'prompts': [{'name': p.name, 'description': p.description} for p in prompts]
			}
			return True
			
		except Exception as e:
			print(f"❌ Ошибка получения списка промптов: {e}")
			self.results['prompts'] = {'status': 'error', 'message': str(e)}
			return False
	
	async def test_call_tool_example(self) -> bool:
		"""Тестирует вызов примера инструмента (если есть)."""
		print("\n⚡ Тестирование вызова инструмента...")
		try:
			tools = await self.client.list_tools()
			if not tools:
				print("⚠️  Нет доступных инструментов для тестирования")
				return True
			
			# Берем первый инструмент для тестирования
			first_tool = tools[0]
			print(f"Тестируем инструмент: {first_tool.name}")
			
			# Вызываем с пустыми аргументами для тестирования
			result = await self.client.call_tool(first_tool.name, {})
			
			print("✅ Инструмент вызван успешно:")
			for content in result.content:
				if hasattr(content, 'text'):
					print(f"  Результат: {content.text}")
				elif hasattr(content, 'data'):
					print(f"  Изображение: {len(content.data)} символов данных")
			
			if result.isError:
				print("⚠️  Результат содержит ошибку")
			
			self.results['tool_call'] = {'status': 'success', 'tool': first_tool.name}
			return True
			
		except Exception as e:
			print(f"❌ Ошибка вызова инструмента: {e}")
			self.results['tool_call'] = {'status': 'error', 'message': str(e)}
			return False
	
	async def print_summary(self):
		"""Выводит итоговую сводку тестирования."""
		print("\n" + "="*60)
		print("📊 ИТОГОВАЯ СВОДКА ТЕСТИРОВАНИЯ")
		print("="*60)
		
		total_tests = len(self.results)
		successful_tests = sum(1 for r in self.results.values() if r['status'] == 'success')
		
		print(f"Всего тестов: {total_tests}")
		print(f"Успешных: {successful_tests}")
		print(f"Неуспешных: {total_tests - successful_tests}")
		print()
		
		for test_name, result in self.results.items():
			status_icon = "✅" if result['status'] == 'success' else "❌"
			print(f"{status_icon} {test_name.replace('_', ' ').title()}")
			
			if result['status'] == 'success':
				if 'count' in result:
					print(f"   Получено элементов: {result['count']}")
			else:
				print(f"   Ошибка: {result['message']}")
		
		print("\n" + "="*60)
		
		# Сохраняем результаты в JSON файл
		try:
			with open('test_results.json', 'w', encoding='utf-8') as f:
				json.dump(self.results, f, ensure_ascii=False, indent=2)
			print("📄 Результаты сохранены в test_results.json")
		except Exception as e:
			print(f"⚠️  Не удалось сохранить результаты: {e}")
	
	async def run_all_tests(self):
		"""Запускает все тесты."""
		print("🚀 Запуск тестирования HTTP-сервиса 1С MCP API")
		print("="*60)
		
		tests = [
			self.test_health(),
			self.test_list_tools(),
			self.test_list_resources(),
			self.test_list_prompts(),
			self.test_call_tool_example(),
		]
		
		# Выполняем тесты последовательно
		for test in tests:
			await test
		
		await self.print_summary()
		await self.client.close()


async def main():
	"""Главная функция."""
	# Конфигурация подключения к 1С
	# ВНИМАНИЕ: Измените эти параметры в соответствии с вашей конфигурацией!
	config = {
		'base_url': 'http://localhost/cg',  # Замените на ваш URL базы 1С
		'username': 'Администратор',  # Замените на ваше имя пользователя
		'password': ''  # Замените на ваш пароль
	}
	
	print("🔧 Конфигурация:")
	print(f"   URL: {config['base_url']}")
	print(f"   Пользователь: {config['username']}")
	print(f"   Пароль: {'*' * len(config['password'])}")
	print()
	
	# Создаем и запускаем тестер
	tester = TestOneCService(
		config['base_url'],
		config['username'],
		config['password']
	)
	
	await tester.run_all_tests()


if __name__ == '__main__':
	try:
		asyncio.run(main())
	except KeyboardInterrupt:
		print("\n⏹️  Тестирование прервано пользователем")
	except Exception as e:
		print(f"\n💥 Критическая ошибка: {e}")
		logger.exception("Критическая ошибка в main()") 
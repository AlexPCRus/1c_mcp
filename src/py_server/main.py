"""Основной файл запуска MCP-прокси сервера."""

import asyncio
import logging
import sys
from typing import Optional
import argparse
from pathlib import Path

from dotenv import load_dotenv

from .config import get_config
from .http_server import run_http_server
from .stdio_server import run_stdio_server


def setup_logging(level: str = "INFO"):
	"""Настройка логирования.
	
	Args:
		level: Уровень логирования
	"""
	logging.basicConfig(
		level=getattr(logging, level.upper()),
		format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
		handlers=[
			logging.StreamHandler(sys.stdout)
		]
	)


def create_parser() -> argparse.ArgumentParser:
	"""Создание парсера аргументов командной строки."""
	parser = argparse.ArgumentParser(
		description="MCP-прокси сервер для взаимодействия с 1С",
		formatter_class=argparse.RawDescriptionHelpFormatter,
		epilog="""
Примеры использования:

  # Запуск в режиме stdio (для использования с MCP клиентами)
  python -m src.py_server stdio

  # Запуск HTTP-сервера на порту 8000
  python -m src.py_server http --port 8000

  # Запуск с конфигурацией из .env файла
  python -m src.py_server http --env-file .env

Переменные окружения:
  MCP_ONEC_URL           - URL базы 1С (обязательно)
  MCP_ONEC_USERNAME      - Имя пользователя 1С (обязательно)
  MCP_ONEC_PASSWORD      - Пароль пользователя 1С (обязательно)
  MCP_ONEC_SERVICE_ROOT  - Корневой URL HTTP-сервиса (по умолчанию: mcp)
  MCP_HOST               - Хост HTTP-сервера (по умолчанию: 127.0.0.1)
  MCP_PORT               - Порт HTTP-сервера (по умолчанию: 8000)
  MCP_LOG_LEVEL          - Уровень логирования (по умолчанию: INFO)
		"""
	)
	
	# Подкоманды
	subparsers = parser.add_subparsers(dest="mode", help="Режим работы сервера")
	
	# Stdio режим
	stdio_parser = subparsers.add_parser(
		"stdio", 
		help="Запуск в режиме stdio (для MCP клиентов)"
	)
	
	# HTTP режим
	http_parser = subparsers.add_parser(
		"http", 
		help="Запуск HTTP-сервера с поддержкой SSE"
	)
	http_parser.add_argument(
		"--host", 
		type=str, 
		help="Хост для HTTP-сервера"
	)
	http_parser.add_argument(
		"--port", 
		type=int, 
		help="Порт для HTTP-сервера"
	)
	
	# Общие параметры
	for subparser in [stdio_parser, http_parser]:
		subparser.add_argument(
			"--env-file",
			type=str,
			help="Путь к .env файлу с конфигурацией"
		)
		subparser.add_argument(
			"--onec-url",
			type=str,
			help="URL базы 1С"
		)
		subparser.add_argument(
			"--onec-username",
			type=str,
			help="Имя пользователя 1С"
		)
		subparser.add_argument(
			"--onec-password",
			type=str,
			help="Пароль пользователя 1С"
		)
		subparser.add_argument(
			"--onec-service-root",
			type=str,
			help="Корневой URL HTTP-сервиса в 1С"
		)
		subparser.add_argument(
			"--log-level",
			type=str,
			choices=["DEBUG", "INFO", "WARNING", "ERROR"],
			help="Уровень логирования"
		)
	
	return parser


async def main():
	"""Основная функция."""
	parser = create_parser()
	args = parser.parse_args()
	
	if not args.mode:
		parser.print_help()
		sys.exit(1)
	
	# Загружаем .env файл если указан
	if hasattr(args, 'env_file') and args.env_file:
		env_path = Path(args.env_file)
		if env_path.exists():
			load_dotenv(env_path)
		else:
			print(f"Предупреждение: файл {args.env_file} не найден")
	else:
		# Пытаемся загрузить .env из текущей директории
		load_dotenv()
	
	# Получаем конфигурацию
	try:
		config = get_config()
		
		# Переопределяем параметры из командной строки
		if hasattr(args, 'host') and args.host:
			config.host = args.host
		if hasattr(args, 'port') and args.port:
			config.port = args.port
		if args.onec_url:
			config.onec_url = args.onec_url
		if args.onec_username:
			config.onec_username = args.onec_username
		if args.onec_password:
			config.onec_password = args.onec_password
		if args.onec_service_root:
			config.onec_service_root = args.onec_service_root
		if args.log_level:
			config.log_level = args.log_level
			
	except Exception as e:
		print(f"Ошибка конфигурации: {e}")
		print("\nПроверьте, что указаны все обязательные параметры:")
		print("- MCP_ONEC_URL (URL базы 1С)")
		print("- MCP_ONEC_USERNAME (имя пользователя)")
		print("- MCP_ONEC_PASSWORD (пароль)")
		sys.exit(1)
	
	# Настройка логирования
	setup_logging(config.log_level)
	logger = logging.getLogger(__name__)
	
	logger.info(f"Запуск MCP-прокси сервера в режиме: {args.mode}")
	logger.info(f"Подключение к 1С: {config.onec_url}")
	logger.info(f"Пользователь: {config.onec_username}")
	
	try:
		if args.mode == "stdio":
			await run_stdio_server(config)
		elif args.mode == "http":
			logger.info(f"HTTP-сервер будет запущен на {config.host}:{config.port}")
			await run_http_server(config)
		else:
			logger.error(f"Неизвестный режим: {args.mode}")
			sys.exit(1)
			
	except KeyboardInterrupt:
		logger.info("Получен сигнал прерывания, завершение работы...")
	except Exception as e:
		logger.error(f"Критическая ошибка: {e}")
		sys.exit(1)


if __name__ == "__main__":
	asyncio.run(main()) 
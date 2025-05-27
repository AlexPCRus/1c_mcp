"""Тест работы аргументов командной строки без .env файла."""

import subprocess
import sys
import os
from pathlib import Path


def test_cli_args():
	"""Тестирование аргументов командной строки."""
	
	print("🧪 Тестирование аргументов командной строки")
	print("=" * 60)
	
	# Убеждаемся, что нет .env файла в текущей директории
	env_file = Path(".env")
	env_backup = None
	if env_file.exists():
		env_backup = env_file.read_text()
		env_file.unlink()
		print("📁 Временно удален .env файл для чистого теста")
	
	# Очищаем переменные окружения MCP_*
	mcp_vars = [key for key in os.environ.keys() if key.startswith("MCP_")]
	saved_vars = {}
	for var in mcp_vars:
		saved_vars[var] = os.environ[var]
		del os.environ[var]
	
	print("🧹 Очищены переменные окружения MCP_*")
	
	try:
		# Тест 1: Только обязательные параметры
		print("\n📋 Тест 1: Минимальные обязательные параметры")
		cmd = [
			sys.executable, "-m", "src.py_server", "stdio",
			"--onec-url", "http://localhost/test_base",
			"--onec-username", "test_user", 
			"--onec-password", "test_password"
		]
		
		print(f"Команда: {' '.join(cmd)}")
		
		# Запускаем с таймаутом, так как сервер будет пытаться подключиться к 1С
		try:
			result = subprocess.run(
				cmd, 
				capture_output=True, 
				text=True, 
				timeout=5,
				cwd=Path.cwd()
			)
		except subprocess.TimeoutExpired:
			print("✅ Сервер запустился (остановлен по таймауту)")
			print("   Это означает, что валидация прошла успешно!")
		except Exception as e:
			print(f"❌ Ошибка запуска: {e}")
		
		# Тест 2: Все параметры
		print("\n📋 Тест 2: Все параметры через CLI")
		cmd = [
			sys.executable, "-m", "src.py_server", "http",
			"--onec-url", "http://server:8080/erp_base",
			"--onec-username", "admin",
			"--onec-password", "secret123",
			"--onec-service-root", "custom_mcp",
			"--host", "0.0.0.0",
			"--port", "9000",
			"--log-level", "DEBUG"
		]
		
		print(f"Команда: {' '.join(cmd)}")
		
		try:
			result = subprocess.run(
				cmd,
				capture_output=True,
				text=True,
				timeout=5,
				cwd=Path.cwd()
			)
		except subprocess.TimeoutExpired:
			print("✅ HTTP-сервер запустился (остановлен по таймауту)")
			print("   Все параметры переданы корректно!")
		except Exception as e:
			print(f"❌ Ошибка запуска: {e}")
		
		# Тест 3: Отсутствует обязательный параметр
		print("\n📋 Тест 3: Отсутствует обязательный параметр (должна быть ошибка)")
		cmd = [
			sys.executable, "-m", "src.py_server", "stdio",
			"--onec-url", "http://localhost/test_base",
			# Намеренно не указываем username и password
		]
		
		print(f"Команда: {' '.join(cmd)}")
		
		try:
			result = subprocess.run(
				cmd,
				capture_output=True,
				text=True,
				timeout=5,
				cwd=Path.cwd()
			)
			
			if result.returncode != 0:
				print("✅ Ожидаемая ошибка валидации:")
				print(f"   {result.stderr.strip()}")
			else:
				print("❌ Неожиданно: сервер запустился без обязательных параметров")
				
		except subprocess.TimeoutExpired:
			print("❌ Неожиданно: сервер запустился без обязательных параметров")
		except Exception as e:
			print(f"❌ Ошибка: {e}")
	
	finally:
		# Восстанавливаем переменные окружения
		for var, value in saved_vars.items():
			os.environ[var] = value
		
		# Восстанавливаем .env файл
		if env_backup:
			env_file.write_text(env_backup)
			print("\n📁 Восстановлен .env файл")
		
		print("\n✅ Тестирование завершено")


if __name__ == "__main__":
	test_cli_args() 
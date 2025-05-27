"""Конфигурация MCP-прокси сервера."""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Config(BaseSettings):
	"""Настройки MCP-прокси сервера."""
	
	# Настройки сервера
	host: str = Field(default="127.0.0.1", description="Хост для HTTP-сервера")
	port: int = Field(default=8000, description="Порт для HTTP-сервера")
	
	# Настройки подключения к 1С
	onec_url: str = Field(..., description="URL базы 1С")
	onec_username: str = Field(..., description="Имя пользователя 1С")
	onec_password: str = Field(..., description="Пароль пользователя 1С")
	
	# Настройки MCP
	server_name: str = Field(default="1C-MCP-Proxy", description="Имя MCP-сервера")
	server_version: str = Field(default="1.0.0", description="Версия MCP-сервера")
	
	# Настройки логирования
	log_level: str = Field(default="INFO", description="Уровень логирования")
	
	# Настройки безопасности
	cors_origins: list[str] = Field(default=["*"], description="Разрешенные CORS origins")
	
	class Config:
		env_file = ".env"
		env_prefix = "MCP_"


def get_config() -> Config:
	"""Получить конфигурацию."""
	return Config() 
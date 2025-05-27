"""Демонстрация формирования URL для различных конфигураций."""

from .config import Config


def demo_url_formation():
	"""Демонстрация формирования URL для разных конфигураций."""
	
	print("🔗 Демонстрация формирования URL для HTTP-сервисов 1С")
	print("=" * 60)
	
	# Примеры конфигураций
	configs = [
		{
			"name": "Стандартная конфигурация",
			"onec_url": "http://localhost/accounting",
			"service_root": "mcp"
		},
		{
			"name": "Несколько расширений",
			"onec_url": "http://server:8080/erp_base",
			"service_root": "mcp_crm"
		},
		{
			"name": "Кастомный сервис",
			"onec_url": "https://cloud.company.com/1c/production",
			"service_root": "ai_tools"
		}
	]
	
	for config in configs:
		print(f"\n📋 {config['name']}")
		print(f"   База 1С: {config['onec_url']}")
		print(f"   Сервис: {config['service_root']}")
		
		# Формируем URL как в OneCClient
		base_url = config['onec_url'].rstrip('/')
		service_root = config['service_root'].strip('/')
		service_base_url = f"{base_url}/hs/{service_root}"
		
		print(f"   📡 Манифест: {service_base_url}/manifest")
		print(f"   🔧 RPC: {service_base_url}/rpc")
	
	print("\n" + "=" * 60)
	print("💡 Преимущества:")
	print("   • Можно подключить несколько MCP-расширений к одной базе")
	print("   • Стандартная схема URL HTTP-сервисов 1С")
	print("   • Гибкая настройка через переменные окружения")
	
	print("\n🔧 Примеры переменных окружения:")
	print("   MCP_ONEC_URL=http://localhost/base")
	print("   MCP_ONEC_SERVICE_ROOT=mcp          # основной сервис")
	print("   MCP_ONEC_SERVICE_ROOT=mcp_crm      # CRM расширение")
	print("   MCP_ONEC_SERVICE_ROOT=mcp_finance  # финансовое расширение")


if __name__ == "__main__":
	demo_url_formation() 
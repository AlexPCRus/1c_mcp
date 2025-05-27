"""Демонстрация поддержки изображений в MCP-прокси."""

import base64
import json
from typing import Dict, Any
from mcp import types


def create_sample_image_base64() -> str:
	"""Создает простое тестовое изображение в формате base64.
	
	Это минимальный PNG (1x1 пиксель, прозрачный).
	"""
	# Минимальный PNG файл (1x1 прозрачный пиксель)
	png_data = bytes([
		0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
		0x00, 0x00, 0x00, 0x0D,  # IHDR chunk length
		0x49, 0x48, 0x44, 0x52,  # IHDR
		0x00, 0x00, 0x00, 0x01,  # width = 1
		0x00, 0x00, 0x00, 0x01,  # height = 1
		0x08, 0x06, 0x00, 0x00, 0x00,  # bit depth, color type, compression, filter, interlace
		0x1F, 0x15, 0xC4, 0x89,  # CRC
		0x00, 0x00, 0x00, 0x0A,  # IDAT chunk length
		0x49, 0x44, 0x41, 0x54,  # IDAT
		0x78, 0x9C, 0x62, 0x00, 0x00, 0x00, 0x02, 0x00, 0x01,  # compressed data
		0xE2, 0x21, 0xBC, 0x33,  # CRC
		0x00, 0x00, 0x00, 0x00,  # IEND chunk length
		0x49, 0x45, 0x4E, 0x44,  # IEND
		0xAE, 0x42, 0x60, 0x82   # CRC
	])
	
	return base64.b64encode(png_data).decode('utf-8')


def demo_response_parsing():
	"""Демонстрация парсинга ответов с изображениями."""
	
	print("🖼️  Демонстрация поддержки изображений в MCP-прокси")
	print("=" * 60)
	
	# Создаем тестовое изображение
	sample_image = create_sample_image_base64()
	
	# Примеры ответов от 1С
	test_responses = [
		{
			"name": "Только текст",
			"response": {
				"content": [
					{
						"type": "text",
						"text": "Простой текстовый ответ"
					}
				],
				"isError": False
			}
		},
		{
			"name": "Текст + изображение",
			"response": {
				"content": [
					{
						"type": "text",
						"text": "График продаж за месяц:"
					},
					{
						"type": "image",
						"data": sample_image,
						"mimeType": "image/png"
					}
				],
				"isError": False
			}
		},
		{
			"name": "Несколько изображений",
			"response": {
				"content": [
					{
						"type": "text",
						"text": "Сравнительные графики:"
					},
					{
						"type": "image",
						"data": sample_image,
						"mimeType": "image/png"
					},
					{
						"type": "text",
						"text": "Второй график:"
					},
					{
						"type": "image",
						"data": sample_image,
						"mimeType": "image/jpeg"
					}
				],
				"isError": False
			}
		},
		{
			"name": "Неизвестный тип",
			"response": {
				"content": [
					{
						"type": "unknown_type",
						"text": "Этот тип не поддерживается"
					}
				],
				"isError": False
			}
		}
	]
	
	# Симулируем обработку ответов
	for test in test_responses:
		print(f"\n📋 Тест: {test['name']}")
		response = test['response']
		
		# Симулируем логику из OneCClient.call_tool
		content = []
		if "content" in response:
			for item in response["content"]:
				content_type = item.get("type")
				
				if content_type == "text":
					content.append({
						"type": "TextContent",
						"text": item.get("text", "")
					})
					print(f"   ✅ Текст: {item.get('text', '')[:50]}...")
				
				elif content_type == "image":
					content.append({
						"type": "ImageContent", 
						"mimeType": item.get("mimeType", "image/png"),
						"data_length": len(item.get("data", ""))
					})
					print(f"   🖼️  Изображение: {item.get('mimeType', 'image/png')}, размер: {len(item.get('data', ''))} символов")
				
				else:
					content.append({
						"type": "TextContent (fallback)",
						"text": str(item.get("text", item))
					})
					print(f"   ⚠️  Неизвестный тип '{content_type}', обработан как текст")
		
		print(f"   📊 Всего элементов контента: {len(content)}")
	
	print("\n" + "=" * 60)
	print("💡 Поддерживаемые типы контента:")
	print("   • text - обычный текст")
	print("   • image - изображения в base64 (PNG, JPEG, GIF, WebP)")
	print("   • unknown - любой неизвестный тип обрабатывается как текст")
	
	print("\n🔧 Пример ответа от 1С с изображением:")
	example_response = {
		"jsonrpc": "2.0",
		"id": 1,
		"result": {
			"content": [
				{
					"type": "text",
					"text": "График построен:"
				},
				{
					"type": "image",
					"data": "iVBORw0KGgoAAAANSUhEUgAA...",
					"mimeType": "image/png"
				}
			],
			"isError": False
		}
	}
	
	print(json.dumps(example_response, indent=2, ensure_ascii=False))


if __name__ == "__main__":
	demo_response_parsing() 
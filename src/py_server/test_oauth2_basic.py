"""Базовый тест OAuth2 функциональности (без реального запуска сервера)."""

import asyncio
import hashlib
import base64
from auth.oauth2 import OAuth2Store, OAuth2Service


async def test_oauth2_flow():
	"""Тест базового OAuth2 потока."""
	print("=== Тест OAuth2 функциональности ===\n")
	
	# Инициализация
	store = OAuth2Store()
	service = OAuth2Service(store, code_ttl=120, access_ttl=3600, refresh_ttl=14*24*3600)
	
	# 1. Генерация PRM документа
	print("1. Генерация PRM документа...")
	prm = service.generate_prm_document("https://test-proxy.local")
	print(f"   ✓ PRM: {prm}")
	assert prm["resource"] == "https://test-proxy.local"
	assert "S256" in prm["code_challenge_methods_supported"]
	print()
	
	# 2. Генерация PKCE
	print("2. Генерация PKCE...")
	code_verifier = "test_verifier_" + "a" * 30  # Минимум 43 символа
	verifier_hash = hashlib.sha256(code_verifier.encode('ascii')).digest()
	code_challenge = base64.urlsafe_b64encode(verifier_hash).decode('ascii').rstrip('=')
	print(f"   Code verifier: {code_verifier[:20]}...")
	print(f"   Code challenge: {code_challenge[:20]}...")
	print()
	
	# 3. Генерация authorization code
	print("3. Генерация authorization code...")
	auth_code = service.generate_authorization_code(
		login="test_user",
		password="test_password",
		redirect_uri="http://localhost/callback",
		code_challenge=code_challenge
	)
	print(f"   ✓ Authorization code: {auth_code[:16]}...")
	print()
	
	# 4. Обмен кода на токены
	print("4. Обмен authorization code на токены...")
	tokens = service.exchange_code_for_tokens(
		code=auth_code,
		redirect_uri="http://localhost/callback",
		code_verifier=code_verifier
	)
	assert tokens is not None, "Не удалось обменять код на токены"
	
	access_token, token_type, expires_in, refresh_token = tokens
	print(f"   ✓ Access token: {access_token[:16]}...")
	print(f"   ✓ Token type: {token_type}")
	print(f"   ✓ Expires in: {expires_in}s")
	print(f"   ✓ Refresh token: {refresh_token[:16]}...")
	print()
	
	# 5. Валидация access token
	print("5. Валидация access token...")
	creds = service.validate_access_token(access_token)
	assert creds is not None, "Access token не валиден"
	login, password = creds
	print(f"   ✓ Login: {login}")
	print(f"   ✓ Password: {'*' * len(password)}")
	assert login == "test_user"
	assert password == "test_password"
	print()
	
	# 6. Refresh токенов
	print("6. Обновление токенов...")
	new_tokens = service.refresh_tokens(refresh_token)
	assert new_tokens is not None, "Не удалось обновить токены"
	
	new_access, new_type, new_expires, new_refresh = new_tokens
	print(f"   ✓ New access token: {new_access[:16]}...")
	print(f"   ✓ New refresh token: {new_refresh[:16]}...")
	print()
	
	# 7. Проверка, что старый refresh больше не работает
	print("7. Проверка ротации refresh token...")
	old_refresh_result = service.refresh_tokens(refresh_token)
	assert old_refresh_result is None, "Старый refresh token не должен работать"
	print(f"   ✓ Старый refresh token инвалидирован (ротация работает)")
	print()
	
	# 8. Проверка нового access token
	print("8. Валидация нового access token...")
	new_creds = service.validate_access_token(new_access)
	assert new_creds is not None, "Новый access token не валиден"
	assert new_creds[0] == "test_user"
	print(f"   ✓ Новый access token работает")
	print()
	
	# 9. Проверка PKCE валидации
	print("9. Проверка PKCE валидации...")
	wrong_verifier = "wrong_verifier_" + "b" * 30
	assert not service.validate_pkce(wrong_verifier, code_challenge), "PKCE должен провалиться на неверном verifier"
	print(f"   ✓ Неверный verifier отклонён")
	print()
	
	print("=== ✓ Все тесты пройдены успешно! ===")


if __name__ == "__main__":
	asyncio.run(test_oauth2_flow())


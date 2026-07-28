"""
Утилиты шифрования.

Мастер-пароль пользователя никогда не хранится напрямую. При первом запуске
генерируется случайная "соль" (salt), которая сохраняется в базе в открытом
виде (это нормально — соль не секрет). Из мастер-пароля и соли с помощью
PBKDF2-HMAC-SHA256 (100 000 итераций) выводится 32-байтный ключ, который
используется для симметричного шифрования Fernet (AES-128 в режиме CBC +
HMAC для проверки целостности).

Чтобы проверить, что введённый пользователем мастер-пароль верен, при
создании базы шифруется контрольная строка ("check_token"). При следующих
запусках мы пытаемся её расшифровать — если не получилось, пароль неверный.
"""

import base64
import os
import secrets
import hmac

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Минимальная длина мастер-пароля для безопасности
MIN_PASSWORD_LENGTH = 8
# Максимальное количество попыток ввода мастер-пароля
MAX_LOGIN_ATTEMPTS = 3
# Количество итераций PBKDF2 для защиты от brute-force
PBKDF2_ITERATIONS = 100_000
SALT_SIZE = 32  # Увеличено с 16 до 32 байт для лучшей безопасности
CHECK_PLAINTEXT = b"mailclient-master-password-check"


class MasterPasswordError(Exception):
    """Исключение для ошибок мастер-пароля."""
    pass


class WeakPasswordError(MasterPasswordError):
    """Исключение для слабых паролей."""
    pass


def generate_salt() -> bytes:
    """Генерирует новую случайную соль используя cryptographically secure генератор."""
    return secrets.token_bytes(SALT_SIZE)


def validate_master_password(password: str) -> None:
    """
    Проверяет сложность мастер-пароля.
    
    Args:
        password: Мастер-пароль для проверки
        
    Raises:
        WeakPasswordError: Если пароль слишком слабый
        ValueError: Если пароль пустой
    """
    if not password:
        raise ValueError("Мастер-пароль не может быть пустым")
    
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(
            f"Мастер-пароль должен содержать минимум {MIN_PASSWORD_LENGTH} символов"
        )
    
    # Проверка на наличие хотя бы одной цифры и одной буквы
    has_digit = any(c.isdigit() for c in password)
    has_alpha = any(c.isalpha() for c in password)
    
    if not (has_digit and has_alpha):
        raise WeakPasswordError(
            "Мастер-пароль должен содержать как минимум одну букву и одну цифру"
        )


def derive_key(master_password: str, salt: bytes) -> bytes:
    """Выводит ключ Fernet (base64-строка) из мастер-пароля и соли."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    raw_key = kdf.derive(master_password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw_key)


class Cipher:
    """Обёртка над Fernet для шифрования/расшифровки строк."""

    def __init__(self, master_password: str, salt: bytes):
        key = derive_key(master_password, salt)
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, token: str) -> str:
        data = self._fernet.decrypt(token.encode("utf-8"))
        return data.decode("utf-8")

    def make_check_token(self) -> str:
        """Создаёт контрольный токен для проверки мастер-пароля."""
        return self._fernet.encrypt(CHECK_PLAINTEXT).decode("utf-8")

    def verify_check_token(self, token: str) -> bool:
        """Проверяет, что мастер-пароль подходит к сохранённому токену."""
        try:
            data = self._fernet.decrypt(token.encode("utf-8"))
            return data == CHECK_PLAINTEXT
        except InvalidToken:
            return False

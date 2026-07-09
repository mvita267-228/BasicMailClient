"""
Автоопределение параметров IMAP/SMTP по домену email-адреса.

Пользователь вводит только email и пароль — хост/порт серверов подставляются
автоматически на основе домена.

Провайдеры Яндекс и Mail.ru (и все домены их почтовых групп) сознательно
заблокированы: попытка добавить такой аккаунт завершается исключением
UnsupportedProviderError, и GUI показывает отказ.
"""

from __future__ import annotations


class UnsupportedProviderError(Exception):
    """Почтовый провайдер не поддерживается (заблокирован сознательно)."""


class UnknownProviderError(Exception):
    """Домен не найден в списке известных провайдеров."""


# Домены, для которых сервис работать не будет ни при каких условиях.
BLOCKED_DOMAINS = {
    "yandex.ru",
    "yandex.com",
    "yandex.by",
    "yandex.kz",
    "yandex.ua",
    "ya.ru",
    "mail.ru",
    "bk.ru",
    "inbox.ru",
    "list.ru",
    "internet.ru",
}

# Известные провайдеры: домен -> настройки серверов.
# smtp_mode: "ssl" (порт 465, неявный TLS) или "starttls" (порт 587).
KNOWN_PROVIDERS = {
    "gmail.com": {
        "imap_host": "imap.gmail.com", "imap_port": 993,
        "smtp_host": "smtp.gmail.com", "smtp_port": 465, "smtp_mode": "ssl",
    },
    "googlemail.com": {
        "imap_host": "imap.gmail.com", "imap_port": 993,
        "smtp_host": "smtp.gmail.com", "smtp_port": 465, "smtp_mode": "ssl",
    },
    "outlook.com": {
        "imap_host": "outlook.office365.com", "imap_port": 993,
        "smtp_host": "smtp.office365.com", "smtp_port": 587, "smtp_mode": "starttls",
    },
    "hotmail.com": {
        "imap_host": "outlook.office365.com", "imap_port": 993,
        "smtp_host": "smtp.office365.com", "smtp_port": 587, "smtp_mode": "starttls",
    },
    "live.com": {
        "imap_host": "outlook.office365.com", "imap_port": 993,
        "smtp_host": "smtp.office365.com", "smtp_port": 587, "smtp_mode": "starttls",
    },
    "yahoo.com": {
        "imap_host": "imap.mail.yahoo.com", "imap_port": 993,
        "smtp_host": "smtp.mail.yahoo.com", "smtp_port": 465, "smtp_mode": "ssl",
    },
    "icloud.com": {
        "imap_host": "imap.mail.me.com", "imap_port": 993,
        "smtp_host": "smtp.mail.me.com", "smtp_port": 587, "smtp_mode": "starttls",
    },
    "me.com": {
        "imap_host": "imap.mail.me.com", "imap_port": 993,
        "smtp_host": "smtp.mail.me.com", "smtp_port": 587, "smtp_mode": "starttls",
    },
    "gmx.com": {
        "imap_host": "imap.gmx.com", "imap_port": 993,
        "smtp_host": "mail.gmx.com", "smtp_port": 465, "smtp_mode": "ssl",
    },
    "proton.me": {
        # ProtonMail требует локальный Bridge-клиент, IMAP/SMTP через него на localhost.
        "imap_host": "127.0.0.1", "imap_port": 1143,
        "smtp_host": "127.0.0.1", "smtp_port": 1025, "smtp_mode": "starttls",
    },
}


def extract_domain(email_address: str) -> str:
    if "@" not in email_address:
        raise ValueError("Некорректный email-адрес")
    return email_address.strip().lower().split("@", 1)[1]


def get_provider_settings(email_address: str) -> dict:
    """
    Возвращает словарь с ключами imap_host, imap_port, smtp_host, smtp_port,
    smtp_mode для данного email-адреса.

    Бросает UnsupportedProviderError, если домен в списке заблокированных
    (Яндекс, Mail.ru), и UnknownProviderError, если домен неизвестен.
    """
    domain = extract_domain(email_address)

    if domain in BLOCKED_DOMAINS:
        raise UnsupportedProviderError(
            f"Почта на домене '{domain}' не поддерживается этим приложением."
        )

    if domain not in KNOWN_PROVIDERS:
        raise UnknownProviderError(
            f"Домен '{domain}' не распознан. Поддерживаются: "
            + ", ".join(sorted(KNOWN_PROVIDERS.keys()))
        )

    return dict(KNOWN_PROVIDERS[domain])

"""
Работа непосредственно с почтовыми протоколами.

fetch_recent_emails() — подключается по IMAP (SSL) и возвращает список
последних писем (from, subject, date, body) из папки INBOX.

send_email() — подключается по SMTP (SSL) и отправляет письмо.

Все функции принимают уже расшифрованные данные аккаунта (login/password),
которые GUI получает из database.AccountStore.get_account().
"""

import imaplib
import smtplib
import email
import logging
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Настройка логирования для отладки (не логируем чувствительные данные)
logger = logging.getLogger(__name__)


def _decode_mime_words(raw: str) -> str:
    """Декодирует MIME-заголовки (Subject, From), которые могут быть в кодировках типа =?UTF-8?..."""
    if raw is None:
        return ""
    parts = decode_header(raw)
    decoded = []
    for text, charset in parts:
        if isinstance(text, bytes):
            # Безопасное декодирование с заменой некорректных символов
            decoded.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(text)
    return "".join(decoded)


def _extract_body_parts(msg) -> tuple[str | None, str | None]:
    """
    Извлекает тело письма отдельно как (text_body, html_body).
    Любое из значений может быть None, если такой части не было.
    Используется, чтобы GUI мог сам решить, как показать ссылки:
    отрендерить оригинальный HTML или сделать линкификацию простого текста.
    """
    text_body = None
    html_body = None

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition") or "")
            if "attachment" in disposition:
                continue
            charset = part.get_content_charset() or "utf-8"
            if content_type == "text/plain" and text_body is None:
                payload = part.get_payload(decode=True)
                if payload:
                    text_body = payload.decode(charset, errors="replace")
            elif content_type == "text/html" and html_body is None:
                payload = part.get_payload(decode=True)
                if payload:
                    html_body = payload.decode(charset, errors="replace")
    else:
        charset = msg.get_content_charset() or "utf-8"
        payload = msg.get_payload(decode=True)
        content = payload.decode(charset, errors="replace") if payload else ""
        if msg.get_content_type() == "text/html":
            html_body = content
        else:
            text_body = content

    return text_body, html_body


def fetch_recent_emails(account: dict, folder: str = "INBOX", limit: int = 20) -> list[dict]:
    """
    Подключается к IMAP-серверу и возвращает список последних `limit` писем,
    отсортированных от новых к старым. Каждое письмо — словарь с ключами
    from, subject, date, body_text, body_html (последний может быть None).
    
    Args:
        account: Словарь с учётными данными (imap_host, imap_port, login, password)
        folder: Папка IMAP для получения писем
        limit: Максимальное количество писем для получения
        
    Returns:
        Список словарей с информацией о письмах
        
    Raises:
        imaplib.IMAP4.error: При ошибках подключения к серверу
        Exception: При других ошибках во время получения писем
    """
    messages = []
    imap = None
    
    try:
        # Валидация входных данных
        required_fields = ["imap_host", "imap_port", "login", "password"]
        for field in required_fields:
            if field not in account:
                raise ValueError(f"Отсутствует обязательное поле аккаунта: {field}")
        
        # Проверка на инъекцию в имени папки (базовая защита)
        if not folder or not isinstance(folder, str):
            raise ValueError("Некорректное имя папки")
        
        # Ограничение на длину имени папки
        if len(folder) > 255:
            raise ValueError("Имя папки слишком длинное")
        
        imap = imaplib.IMAP4_SSL(account["imap_host"], account["imap_port"])
        imap.login(account["login"], account["password"])
        imap.select(folder)

        status, data = imap.search(None, "ALL")
        if status != "OK":
            logger.warning("Не удалось получить список писем из папки %s", folder)
            return messages

        all_ids = data[0].split()
        recent_ids = all_ids[-limit:] if len(all_ids) > limit else all_ids
        recent_ids.reverse()  # от новых к старым

        for msg_id in recent_ids:
            try:
                status, msg_data = imap.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    continue
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                text_body, html_body = _extract_body_parts(msg)
                messages.append(
                    {
                        "from": _decode_mime_words(msg.get("From")),
                        "subject": _decode_mime_words(msg.get("Subject")),
                        "date": msg.get("Date", ""),
                        "body_text": text_body,
                        "body_html": html_body,
                    }
                )
            except Exception as e:
                logger.warning("Ошибка при обработке письма %s: %s", msg_id, e)
                continue
                
    except Exception as e:
        logger.error("Ошибка при получении писем: %s", e)
        raise
    finally:
        if imap:
            try:
                imap.close()
            except Exception:
                pass
            try:
                imap.logout()
            except Exception:
                pass

    return messages


def send_email(account: dict, to_addr: str, subject: str, body: str) -> None:
    """
    Подключается по SMTP и отправляет письмо от имени аккаунта.

    Режим подключения берётся из account["smtp_mode"]:
      - "ssl"      — неявный TLS с самого начала соединения (обычно порт 465);
      - "starttls" — сначала обычное соединение, потом апгрейд до TLS
                     командой STARTTLS (обычно порт 587).
    
    Args:
        account: Словарь с учётными данными (smtp_host, smtp_port, login, password, smtp_mode)
        to_addr: Адрес получателя
        subject: Тема письма
        body: Тело письма
        
    Raises:
        ValueError: При некорректных входных данных
        smtplib.SMTPException: При ошибках отправки почты
    """
    # Валидация входных данных
    if not to_addr or not isinstance(to_addr, str):
        raise ValueError("Некорректный адрес получателя")
    
    if not subject or not isinstance(subject, str):
        raise ValueError("Некорректная тема письма")
    
    # Ограничение на длину адреса получателя для защиты от переполнения
    if len(to_addr) > 254:
        raise ValueError("Адрес получателя слишком длинный")
    
    # Базовая валидация формата email
    if "@" not in to_addr or "." not in to_addr.split("@")[-1]:
        raise ValueError("Некорректный формат email адреса получателя")
    
    required_fields = ["smtp_host", "smtp_port", "login", "password"]
    for field in required_fields:
        if field not in account:
            raise ValueError(f"Отсутствует обязательное поле аккаунта: {field}")
    
    msg = MIMEMultipart()
    msg["From"] = account["login"]
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    smtp_mode = account.get("smtp_mode", "ssl")
    smtp = None

    try:
        if smtp_mode == "starttls":
            smtp = smtplib.SMTP(account["smtp_host"], account["smtp_port"])
            try:
                smtp.starttls()
            except smtplib.SMTPException as e:
                logger.error("Ошибка при установке TLS соединения: %s", e)
                raise
            smtp.login(account["login"], account["password"])
            smtp.sendmail(account["login"], [to_addr], msg.as_string())
        else:
            smtp = smtplib.SMTP_SSL(account["smtp_host"], account["smtp_port"])
            try:
                smtp.login(account["login"], account["password"])
                smtp.sendmail(account["login"], [to_addr], msg.as_string())
            except smtplib.SMTPAuthenticationError as e:
                logger.error("Ошибка аутентификации SMTP: %s", e)
                raise
            except smtplib.SMTPException as e:
                logger.error("SMTP ошибка при отправке: %s", e)
                raise
    finally:
        if smtp:
            try:
                smtp.quit()
            except Exception:
                pass

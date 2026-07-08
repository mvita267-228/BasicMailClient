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
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def _decode_mime_words(raw: str) -> str:
    """Декодирует MIME-заголовки (Subject, From), которые могут быть в кодировках типа =?UTF-8?..."""
    if raw is None:
        return ""
    parts = decode_header(raw)
    decoded = []
    for text, charset in parts:
        if isinstance(text, bytes):
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
    """
    messages = []
    imap = imaplib.IMAP4_SSL(account["imap_host"], account["imap_port"])
    try:
        imap.login(account["login"], account["password"])
        imap.select(folder)

        status, data = imap.search(None, "ALL")
        if status != "OK":
            return messages

        all_ids = data[0].split()
        recent_ids = all_ids[-limit:] if len(all_ids) > limit else all_ids
        recent_ids.reverse()  # от новых к старым

        for msg_id in recent_ids:
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
    finally:
        try:
            imap.close()
        except Exception:
            pass
        imap.logout()

    return messages


def send_email(account: dict, to_addr: str, subject: str, body: str) -> None:
    """
    Подключается по SMTP и отправляет письмо от имени аккаунта.

    Режим подключения берётся из account["smtp_mode"]:
      - "ssl"      — неявный TLS с самого начала соединения (обычно порт 465);
      - "starttls" — сначала обычное соединение, потом апгрейд до TLS
                     командой STARTTLS (обычно порт 587).
    """
    msg = MIMEMultipart()
    msg["From"] = account["login"]
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    smtp_mode = account.get("smtp_mode", "ssl")

    if smtp_mode == "starttls":
        smtp = smtplib.SMTP(account["smtp_host"], account["smtp_port"])
        try:
            smtp.starttls()
            smtp.login(account["login"], account["password"])
            smtp.sendmail(account["login"], [to_addr], msg.as_string())
        finally:
            smtp.quit()
    else:
        smtp = smtplib.SMTP_SSL(account["smtp_host"], account["smtp_port"])
        try:
            smtp.login(account["login"], account["password"])
            smtp.sendmail(account["login"], [to_addr], msg.as_string())
        finally:
            smtp.quit()

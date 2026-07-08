"""
Вспомогательные функции для отображения тела письма с превью ссылок.

linkify(text) — берёт обычный текст письма, экранирует HTML-спецсимволы и
оборачивает найденные в тексте URL (http://, https://, www.) в теги <a>,
чтобы они отображались как кликабельные ссылки в QTextBrowser.

sanitize_html(raw_html) — очень простая "санитизация" HTML-писем: вырезает
<script>/<style>/<iframe>/<object>/<embed>, обработчики on*="..." и
javascript:-ссылки. Это НЕ полноценная защита от XSS промышленного уровня —
для этого стоило бы использовать специализированную библиотеку (например,
bleach) — но для превью писем в личном desktop-клиенте достаточно.
"""

import html
import re

URL_PATTERN = re.compile(
    r"(https?://[^\s<>\"']+|www\.[^\s<>\"']+)",
    re.IGNORECASE,
)


def linkify(text: str) -> str:
    """Преобразует обычный текст в HTML с кликабельными ссылками."""
    if not text:
        return ""

    chunks = []
    last_end = 0
    for match in URL_PATTERN.finditer(text):
        chunks.append(html.escape(text[last_end:match.start()]))

        url = match.group(0)
        # убираем висящую пунктуацию в конце URL, например точку в конце предложения
        trailing = ""
        while url and url[-1] in ".,!?;:)":
            trailing = url[-1] + trailing
            url = url[:-1]

        href = url if url.lower().startswith("http") else "http://" + url
        display_text = html.escape(url)
        escaped_href = html.escape(href, quote=True)

        chunks.append(f'<a href="{escaped_href}">{display_text}</a>')
        chunks.append(html.escape(trailing))

        last_end = match.end()

    chunks.append(html.escape(text[last_end:]))
    joined = "".join(chunks)
    return joined.replace("\n", "<br>")


_STRIP_TAG_RE = re.compile(r"(?is)<(script|style|iframe|object|embed)\b[^>]*>.*?</\1\s*>")
_ON_ATTR_RE_DQ = re.compile(r'(?i)\son\w+\s*=\s*"[^"]*"')
_ON_ATTR_RE_SQ = re.compile(r"(?i)\son\w+\s*=\s*'[^']*'")
_JS_HREF_RE = re.compile(r'(?i)href\s*=\s*"javascript:[^"]*"')


def sanitize_html(raw_html: str) -> str:
    """Базовая очистка HTML-письма перед показом в QTextBrowser."""
    if not raw_html:
        return ""
    cleaned = _STRIP_TAG_RE.sub("", raw_html)
    cleaned = _ON_ATTR_RE_DQ.sub("", cleaned)
    cleaned = _ON_ATTR_RE_SQ.sub("", cleaned)
    cleaned = _JS_HREF_RE.sub('href="#"', cleaned)
    return cleaned

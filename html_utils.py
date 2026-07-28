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

# Регулярное выражение для URL с улучшенной защитой
URL_PATTERN = re.compile(
    r"(https?://[^\s<>\"']+|www\.[^\s<>\"']+)",
    re.IGNORECASE,
)

# Опасные схемы для ссылок
DANGEROUS_SCHEMES = re.compile(r'(?i)^(javascript|vbscript|data|file):', re.IGNORECASE)


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
        
        # Проверка на опасные схемы
        if DANGEROUS_SCHEMES.match(href):
            # Заменяем опасные ссылки на безопасный текст
            chunks.append(html.escape(url))
        else:
            display_text = html.escape(url)
            escaped_href = html.escape(href, quote=True)
            chunks.append(f'<a href="{escaped_href}">{display_text}</a>')
        
        chunks.append(html.escape(trailing))

        last_end = match.end()

    chunks.append(html.escape(text[last_end:]))
    joined = "".join(chunks)
    return joined.replace("\n", "<br>")


_STRIP_TAG_RE = re.compile(r"(?is)<(script|style|iframe|object|embed|form|input|button)\b[^>]*>.*?</\1\s*>")
_ON_ATTR_RE_DQ = re.compile(r'(?i)\son\w+\s*=\s*"[^"]*"')
_ON_ATTR_RE_SQ = re.compile(r"(?i)\son\w+\s*=\s*'[^']*'")
_JS_HREF_RE = re.compile(r'(?i)href\s*=\s*"javascript:[^"]*"')
_DATA_HREF_RE = re.compile(r'(?i)href\s*=\s*"data:[^"]*"')
_STYLE_ATTR_RE = re.compile(r'(?i)\bstyle\s*=\s*"[^"]*"')


def sanitize_html(raw_html: str) -> str:
    """
    Базовая очистка HTML-письма перед показом в QTextBrowser.
    
    Удаляет:
    - Теги script, style, iframe, object, embed, form, input, button
    - Обработчики событий on* (onclick, onload и т.д.)
    - javascript: и data: ссылки
    - inline стили
    
    Args:
        raw_html: Исходный HTML для очистки
        
    Returns:
        Очищенный HTML
    """
    if not raw_html:
        return ""
    
    cleaned = _STRIP_TAG_RE.sub("", raw_html)
    cleaned = _ON_ATTR_RE_DQ.sub("", cleaned)
    cleaned = _ON_ATTR_RE_SQ.sub("", cleaned)
    cleaned = _JS_HREF_RE.sub('href="#"', cleaned)
    cleaned = _DATA_HREF_RE.sub('href="#"', cleaned)
    cleaned = _STYLE_ATTR_RE.sub('', cleaned)
    
    return cleaned

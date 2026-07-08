"""
Простой модуль интернационализации интерфейса.

Все строки интерфейса лежат в словаре TRANSLATIONS[lang][key]. Функция tr()
возвращает перевод по ключу для текущего языка, с откатом на английский,
если ключ не найден, и на сам ключ, если перевода нет вообще.
"""

TRANSLATIONS = {
    "en": {
        "window_title": "Mail Client (TinyDB, encrypted)",
        "accounts": "Accounts",
        "add": "Add",
        "delete": "Delete",
        "refresh_inbox": "Refresh inbox",
        "compose": "Compose",
        "col_from": "From",
        "col_subject": "Subject",
        "col_date": "Date",
        "body_label": "Message body:",
        "loading_emails": "Loading emails...",
        "emails_loaded": "Emails loaded: {count}",
        "error_status": "Error",
        "fetch_error_title": "Error fetching emails",
        "select_account_first": "Please select an account on the left first",
        "select_account_for_compose": "Please select an account to compose from first",
        "confirm_title": "Confirm",
        "confirm_delete": "Delete account '{name}'?",
        "yes": "Yes",
        "no": "No",
        "warning_title": "Warning",
        "info_title": "Info",
        "error_title": "Error",
        "refusal_title": "Refused",
        "unknown_provider_title": "Unknown provider",
        # master password dialog
        "master_create_title": "Create master password",
        "master_enter_title": "Enter master password",
        "master_create_hint": "Choose a master password.\nIt will be used to encrypt your mail logins and passwords.",
        "master_enter_hint": "Enter your master password to unlock the storage.",
        "password_label": "Password:",
        "repeat_label": "Repeat:",
        "ok": "OK",
        "cancel": "Cancel",
        "password_empty": "Password cannot be empty",
        "password_mismatch": "Passwords do not match",
        "wrong_master_password": "Wrong master password",
        # add account dialog
        "add_account_title": "Add account",
        "name_label": "Name:",
        "email_label": "Email:",
        "provider_info": (
            "IMAP and SMTP servers are detected automatically from the email domain.\n"
            "Yandex (yandex.*) and Mail.ru (mail.ru, bk.ru, inbox.ru, list.ru) are not supported."
        ),
        "fill_all_fields": "Please fill in all fields",
        "invalid_email": "Invalid email address",
        # compose dialog
        "compose_title": "New message — from {login}",
        "to_label": "To:",
        "subject_label": "Subject:",
        "send": "Send",
        "sending": "Sending...",
        "sent_success": "Message sent",
        "send_error_title": "Send error",
        "recipient_required": "Please specify a recipient",
        "no_text_content": "(no text content)",
        # language selection
        "language_dialog_title": "Language / Язык",
        "language_prompt": "Choose interface language:",
        "language_english": "English",
        "language_russian": "Русский",
        "menu_settings": "Settings",
        "menu_language": "Language",
        "restart_note": "The interface language will fully update after restarting the app.",
    },
    "ru": {
        "window_title": "Почтовый клиент (TinyDB, зашифровано)",
        "accounts": "Аккаунты",
        "add": "Добавить",
        "delete": "Удалить",
        "refresh_inbox": "Обновить входящие",
        "compose": "Написать письмо",
        "col_from": "От кого",
        "col_subject": "Тема",
        "col_date": "Дата",
        "body_label": "Текст письма:",
        "loading_emails": "Загрузка писем...",
        "emails_loaded": "Писем загружено: {count}",
        "error_status": "Ошибка",
        "fetch_error_title": "Ошибка получения писем",
        "select_account_first": "Сначала выберите аккаунт слева",
        "select_account_for_compose": "Сначала выберите аккаунт, от которого писать письмо",
        "confirm_title": "Подтверждение",
        "confirm_delete": "Удалить аккаунт '{name}'?",
        "yes": "Да",
        "no": "Нет",
        "warning_title": "Внимание",
        "info_title": "Инфо",
        "error_title": "Ошибка",
        "refusal_title": "Отказ",
        "unknown_provider_title": "Провайдер не распознан",
        # master password dialog
        "master_create_title": "Создать мастер-пароль",
        "master_enter_title": "Введите мастер-пароль",
        "master_create_hint": "Придумайте мастер-пароль.\nОн будет использоваться для шифрования логинов и паролей от почты.",
        "master_enter_hint": "Введите мастер-пароль для разблокировки хранилища.",
        "password_label": "Пароль:",
        "repeat_label": "Повтор:",
        "ok": "OK",
        "cancel": "Отмена",
        "password_empty": "Пароль не может быть пустым",
        "password_mismatch": "Пароли не совпадают",
        "wrong_master_password": "Неверный мастер-пароль",
        # add account dialog
        "add_account_title": "Добавить аккаунт",
        "name_label": "Название:",
        "email_label": "Email:",
        "provider_info": (
            "IMAP и SMTP серверы определяются автоматически по домену почты.\n"
            "Яндекс (yandex.*) и Mail.ru (mail.ru, bk.ru, inbox.ru, list.ru) не поддерживаются."
        ),
        "fill_all_fields": "Заполните все поля",
        "invalid_email": "Некорректный email-адрес",
        # compose dialog
        "compose_title": "Новое письмо — от {login}",
        "to_label": "Кому:",
        "subject_label": "Тема:",
        "send": "Отправить",
        "sending": "Отправка...",
        "sent_success": "Письмо отправлено",
        "send_error_title": "Ошибка отправки",
        "recipient_required": "Укажите получателя",
        "no_text_content": "(нет текстового содержимого)",
        # language selection
        "language_dialog_title": "Язык / Language",
        "language_prompt": "Выберите язык интерфейса:",
        "language_english": "English",
        "language_russian": "Русский",
        "menu_settings": "Настройки",
        "menu_language": "Язык",
        "restart_note": "Язык интерфейса полностью обновится после перезапуска приложения.",
    },
}

DEFAULT_LANGUAGE = "en"


def tr(key: str, lang: str, **kwargs) -> str:
    table = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANGUAGE])
    text = table.get(key) or TRANSLATIONS[DEFAULT_LANGUAGE].get(key) or key
    if kwargs:
        return text.format(**kwargs)
    return text

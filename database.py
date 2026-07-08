"""
Слой хранения данных на TinyDB.

Все данные хранятся в единственном файле data.db (по умолчанию, в текущей
рабочей директории). Внутри это по-прежнему TinyDB со своим JSON-based
хранилищем (JSONStorage) — TinyDB не поддерживает "бинарный" формат из
коробки, поэтому меняется именно имя/расширение файла на диске, а не
внутренний формат сериализации.

Таблицы в data.db:
  - "meta": одна запись с солью (в base64) и контрольным токеном
    мастер-пароля, нужным для проверки правильности ввода пароля.
  - "settings": некритичные настройки приложения (например, выбранный
    язык интерфейса), хранятся в открытом виде.
  - "accounts": по одной записи на каждую почтовую учётную запись.
    Поля imap_host/imap_port/smtp_host/smtp_port/smtp_mode определяются
    автоматически (см. email_providers.py) и хранятся в открытом виде —
    это не секретные данные. Поле "secret" — это зашифрованный Fernet-токен,
    внутри которого лежит JSON вида {"login": ..., "password": ...}.

Расшифровка происходит только в памяти, когда приложению нужно реально
подключиться к серверу — на диске логин и пароль никогда не появляются
в открытом виде.
"""

import base64
import json

from tinydb import TinyDB, Query

from crypto_utils import Cipher, generate_salt

DB_PATH = "data.db"


class AccountStore:
    def __init__(self, db_path: str = DB_PATH):
        self.db = TinyDB(db_path)
        self.meta_table = self.db.table("meta")
        self.accounts_table = self.db.table("accounts")
        self.settings_table = self.db.table("settings")
        self.cipher: Cipher | None = None

    # ---------- Мастер-пароль / инициализация шифрования ----------

    def has_master_password(self) -> bool:
        return len(self.meta_table) > 0

    def setup_master_password(self, master_password: str) -> None:
        """Вызывается один раз при первом запуске приложения."""
        salt = generate_salt()
        cipher = Cipher(master_password, salt)
        check_token = cipher.make_check_token()
        self.meta_table.insert(
            {
                "salt": base64.b64encode(salt).decode("utf-8"),
                "check_token": check_token,
            }
        )
        self.cipher = cipher

    def unlock(self, master_password: str) -> bool:
        """Пытается разблокировать базу существующим мастер-паролем."""
        meta = self.meta_table.all()
        if not meta:
            return False
        salt = base64.b64decode(meta[0]["salt"])
        cipher = Cipher(master_password, salt)
        if cipher.verify_check_token(meta[0]["check_token"]):
            self.cipher = cipher
            return True
        return False

    def _require_unlocked(self):
        if self.cipher is None:
            raise RuntimeError("База данных не разблокирована мастер-паролем")

    # ---------- CRUD для учётных записей ----------

    def add_account(
        self,
        name: str,
        login: str,
        password: str,
        imap_host: str,
        imap_port: int,
        smtp_host: str,
        smtp_port: int,
        smtp_mode: str = "ssl",
    ) -> None:
        self._require_unlocked()
        secret = json.dumps({"login": login, "password": password})
        encrypted_secret = self.cipher.encrypt(secret)
        Account = Query()
        self.accounts_table.upsert(
            {
                "name": name,
                "secret": encrypted_secret,
                "imap_host": imap_host,
                "imap_port": imap_port,
                "smtp_host": smtp_host,
                "smtp_port": smtp_port,
                "smtp_mode": smtp_mode,
            },
            Account.name == name,
        )

    def list_accounts(self) -> list[str]:
        return [row["name"] for row in self.accounts_table.all()]

    def get_account(self, name: str) -> dict:
        """Возвращает запись аккаунта с расшифрованными login/password."""
        self._require_unlocked()
        Account = Query()
        row = self.accounts_table.get(Account.name == name)
        if row is None:
            raise KeyError(f"Аккаунт '{name}' не найден")
        secret = json.loads(self.cipher.decrypt(row["secret"]))
        return {
            "name": row["name"],
            "login": secret["login"],
            "password": secret["password"],
            "imap_host": row["imap_host"],
            "imap_port": row["imap_port"],
            "smtp_host": row["smtp_host"],
            "smtp_port": row["smtp_port"],
            "smtp_mode": row.get("smtp_mode", "ssl"),
        }

    def delete_account(self, name: str) -> None:
        Account = Query()
        self.accounts_table.remove(Account.name == name)

    # ---------- настройки (не секретные, хранятся в открытом виде) ----------

    def get_language(self) -> str | None:
        """Возвращает сохранённый код языка интерфейса ('en'/'ru') или None."""
        row = self.settings_table.get(Query().key == "language")
        return row["value"] if row else None

    def set_language(self, lang: str) -> None:
        Setting = Query()
        self.settings_table.upsert({"key": "language", "value": lang}, Setting.key == "language")

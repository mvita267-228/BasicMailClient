"""
Графический интерфейс приложения на PyQt6.

Экраны:
  1. LanguageDialog — выбор языка интерфейса (показывается один раз при
     первом запуске; язык сохраняется в data.db и используется дальше).
  2. MasterPasswordDialog — при первом запуске просит придумать мастер-пароль,
     при последующих — просит его ввести для разблокировки базы.
  3. AddAccountDialog — форма добавления аккаунта: только email и пароль,
     хост/порт IMAP и SMTP определяются автоматически по домену
     (см. email_providers.py). Если домен принадлежит Яндексу или Mail.ru —
     показывается отказ и аккаунт не добавляется.
  4. MainWindow — основное окно: слева список аккаунтов, справа таблица
     писем и просмотр текста письма с кликабельными ссылками (QTextBrowser).
  5. ComposeDialog — окно отправки нового письма.

Сетевые операции (IMAP/SMTP) выполняются в отдельных потоках (QThread),
чтобы интерфейс не подвисал во время ожидания ответа сервера.
"""

import sys

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QMainWindow,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTextBrowser,
    QWidget,
    QHeaderView,
    QAbstractItemView,
    QStatusBar,
    QMenuBar,
)
from PyQt6.QtGui import QAction

from database import AccountStore
import mail_client
import email_providers
import html_utils
from email_providers import UnsupportedProviderError, UnknownProviderError
from translations import tr, DEFAULT_LANGUAGE


# ============================== Фоновые потоки ==============================


class FetchThread(QThread):
    succeeded = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, account: dict):
        super().__init__()
        self.account = account

    def run(self):
        try:
            emails = mail_client.fetch_recent_emails(self.account)
            self.succeeded.emit(emails)
        except Exception as exc:
            self.failed.emit(str(exc))


class SendThread(QThread):
    succeeded = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, account: dict, to_addr: str, subject: str, body: str):
        super().__init__()
        self.account = account
        self.to_addr = to_addr
        self.subject = subject
        self.body = body

    def run(self):
        try:
            mail_client.send_email(self.account, self.to_addr, self.subject, self.body)
            self.succeeded.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


# ================================= Диалоги ==================================


class LanguageDialog(QDialog):
    """Показывается один раз при первом запуске для выбора языка интерфейса."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_lang: str | None = None
        self.setWindowTitle("Язык / Language")
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Выберите язык интерфейса / Choose interface language:"))

        buttons = QHBoxLayout()
        ru_btn = QPushButton("Русский")
        ru_btn.clicked.connect(lambda: self._choose("ru"))
        en_btn = QPushButton("English")
        en_btn.clicked.connect(lambda: self._choose("en"))
        buttons.addWidget(ru_btn)
        buttons.addWidget(en_btn)
        layout.addLayout(buttons)

    def _choose(self, lang: str):
        self.selected_lang = lang
        self.accept()


class MasterPasswordDialog(QDialog):
    def __init__(self, parent, creating: bool, lang: str):
        super().__init__(parent)
        self.creating = creating
        self.lang = lang
        self.password: str | None = None
        self.setWindowTitle(tr("master_create_title", lang) if creating else tr("master_enter_title", lang))
        self.setMinimumWidth(340)

        layout = QVBoxLayout(self)

        hint = tr("master_create_hint", lang) if creating else tr("master_enter_hint", lang)
        layout.addWidget(QLabel(hint))

        form = QFormLayout()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(tr("password_label", lang), self.password_edit)

        self.repeat_edit = None
        if creating:
            self.repeat_edit = QLineEdit()
            self.repeat_edit.setEchoMode(QLineEdit.EchoMode.Password)
            form.addRow(tr("repeat_label", lang), self.repeat_edit)

        layout.addLayout(form)

        buttons = QHBoxLayout()
        ok_btn = QPushButton(tr("ok", lang))
        ok_btn.clicked.connect(self._on_ok)
        ok_btn.setDefault(True)
        cancel_btn = QPushButton(tr("cancel", lang))
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def _on_ok(self):
        pwd = self.password_edit.text()
        if not pwd:
            QMessageBox.warning(self, tr("warning_title", self.lang), tr("password_empty", self.lang))
            return
        if self.creating and pwd != self.repeat_edit.text():
            QMessageBox.warning(self, tr("warning_title", self.lang), tr("password_mismatch", self.lang))
            return
        self.password = pwd
        self.accept()


class AddAccountDialog(QDialog):
    """
    Форма добавления аккаунта. Пользователь вводит только название, email
    и пароль — настройки IMAP/SMTP определяются автоматически по домену.
    Для Яндекса и Mail.ru показывается явный отказ.
    """

    def __init__(self, parent, lang: str):
        super().__init__(parent)
        self.lang = lang
        self.result_data: dict | None = None
        self.setWindowTitle(tr("add_account_title", lang))
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.login_edit = QLineEdit()
        self.login_edit.setPlaceholderText("example@gmail.com")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow(tr("name_label", lang), self.name_edit)
        form.addRow(tr("email_label", lang), self.login_edit)
        form.addRow(tr("password_label", lang), self.password_edit)
        layout.addLayout(form)

        self.info_label = QLabel(tr("provider_info", lang))
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.info_label)

        buttons = QHBoxLayout()
        add_btn = QPushButton(tr("add", lang))
        add_btn.clicked.connect(self._on_add)
        add_btn.setDefault(True)
        cancel_btn = QPushButton(tr("cancel", lang))
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(add_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def _on_add(self):
        name = self.name_edit.text().strip()
        login = self.login_edit.text().strip()
        password = self.password_edit.text()

        if not name or not login or not password:
            QMessageBox.warning(self, tr("warning_title", self.lang), tr("fill_all_fields", self.lang))
            return

        if "@" not in login:
            QMessageBox.warning(self, tr("warning_title", self.lang), tr("invalid_email", self.lang))
            return

        try:
            settings = email_providers.get_provider_settings(login)
        except UnsupportedProviderError as exc:
            QMessageBox.critical(self, tr("refusal_title", self.lang), str(exc))
            return
        except UnknownProviderError as exc:
            QMessageBox.warning(self, tr("unknown_provider_title", self.lang), str(exc))
            return

        self.result_data = {
            "name": name,
            "login": login,
            "password": password,
            "imap_host": settings["imap_host"],
            "imap_port": settings["imap_port"],
            "smtp_host": settings["smtp_host"],
            "smtp_port": settings["smtp_port"],
            "smtp_mode": settings["smtp_mode"],
        }
        self.accept()


class ComposeDialog(QDialog):
    def __init__(self, parent, account: dict, lang: str):
        super().__init__(parent)
        self.account = account
        self.lang = lang
        self.setWindowTitle(tr("compose_title", lang, login=account["login"]))
        self.setMinimumSize(480, 400)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.to_edit = QLineEdit()
        self.subject_edit = QLineEdit()
        form.addRow(tr("to_label", lang), self.to_edit)
        form.addRow(tr("subject_label", lang), self.subject_edit)
        layout.addLayout(form)

        layout.addWidget(QLabel(tr("body_label", lang)))
        self.body_edit = QTextEdit()
        layout.addWidget(self.body_edit)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.send_btn = QPushButton(tr("send", lang))
        self.send_btn.clicked.connect(self._send)
        buttons.addWidget(self.send_btn)
        layout.addLayout(buttons)

        self.thread: SendThread | None = None

    def _send(self):
        to_addr = self.to_edit.text().strip()
        subject = self.subject_edit.text().strip()
        body = self.body_edit.toPlainText().strip()

        if not to_addr:
            QMessageBox.warning(self, tr("warning_title", self.lang), tr("recipient_required", self.lang))
            return

        self.send_btn.setEnabled(False)
        self.send_btn.setText(tr("sending", self.lang))

        self.thread = SendThread(self.account, to_addr, subject, body)
        self.thread.succeeded.connect(self._on_success)
        self.thread.failed.connect(self._on_error)
        self.thread.start()

    def _on_success(self):
        QMessageBox.information(self, tr("info_title", self.lang), tr("sent_success", self.lang))
        self.accept()

    def _on_error(self, message: str):
        self.send_btn.setEnabled(True)
        self.send_btn.setText(tr("send", self.lang))
        QMessageBox.critical(self, tr("send_error_title", self.lang), message)


# =============================== Главное окно ===============================


class MainWindow(QMainWindow):
    def __init__(self, store: AccountStore, lang: str):
        super().__init__()
        self.store = store
        self.lang = lang
        self.current_account_name: str | None = None
        self.current_emails: list[dict] = []
        self.fetch_thread: FetchThread | None = None

        self.setWindowTitle(tr("window_title", lang))
        self.resize(1000, 600)

        self._build_menu()
        self._build_ui()
        self._refresh_account_list()

    def _build_menu(self):
        menu_bar = self.menuBar()
        settings_menu = menu_bar.addMenu(tr("menu_settings", self.lang))
        lang_menu = settings_menu.addMenu(tr("menu_language", self.lang))

        ru_action = QAction(tr("language_russian", self.lang), self)
        ru_action.triggered.connect(lambda: self._change_language("ru"))
        en_action = QAction(tr("language_english", self.lang), self)
        en_action.triggered.connect(lambda: self._change_language("en"))
        lang_menu.addAction(ru_action)
        lang_menu.addAction(en_action)

    def _change_language(self, lang: str):
        self.store.set_language(lang)
        QMessageBox.information(self, tr("info_title", lang), tr("restart_note", lang))

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)

        # ---- левая панель: аккаунты ----
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel(f"<b>{tr('accounts', self.lang)}</b>"))

        self.account_list = QListWidget()
        self.account_list.currentItemChanged.connect(self._on_select_account)
        left_panel.addWidget(self.account_list)

        account_buttons = QHBoxLayout()
        add_btn = QPushButton(tr("add", self.lang))
        add_btn.clicked.connect(self._add_account)
        del_btn = QPushButton(tr("delete", self.lang))
        del_btn.clicked.connect(self._delete_account)
        account_buttons.addWidget(add_btn)
        account_buttons.addWidget(del_btn)
        left_panel.addLayout(account_buttons)

        left_container = QWidget()
        left_container.setLayout(left_panel)
        left_container.setFixedWidth(240)
        root_layout.addWidget(left_container)

        # ---- правая панель: письма ----
        right_panel = QVBoxLayout()

        toolbar = QHBoxLayout()
        refresh_btn = QPushButton(tr("refresh_inbox", self.lang))
        refresh_btn.clicked.connect(self._refresh_inbox)
        compose_btn = QPushButton(tr("compose", self.lang))
        compose_btn.clicked.connect(self._compose)
        toolbar.addWidget(refresh_btn)
        toolbar.addWidget(compose_btn)
        toolbar.addStretch()
        right_panel.addLayout(toolbar)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(
            [tr("col_from", self.lang), tr("col_subject", self.lang), tr("col_date", self.lang)]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_select_email)
        right_panel.addWidget(self.table)

        right_panel.addWidget(QLabel(tr("body_label", self.lang)))
        # QTextBrowser вместо QTextEdit — умеет рендерить HTML и открывать
        # ссылки во внешнем браузере по клику (превью URL из письма).
        self.body_view = QTextBrowser()
        self.body_view.setOpenExternalLinks(True)
        right_panel.addWidget(self.body_view)

        right_container = QWidget()
        right_container.setLayout(right_panel)
        root_layout.addWidget(right_container)

        self.setStatusBar(QStatusBar())

    # ---------- аккаунты ----------

    def _refresh_account_list(self):
        self.account_list.clear()
        for name in self.store.list_accounts():
            self.account_list.addItem(QListWidgetItem(name))

    def _add_account(self):
        dialog = AddAccountDialog(self, self.lang)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_data:
            data = dialog.result_data
            self.store.add_account(
                name=data["name"],
                login=data["login"],
                password=data["password"],
                imap_host=data["imap_host"],
                imap_port=data["imap_port"],
                smtp_host=data["smtp_host"],
                smtp_port=data["smtp_port"],
                smtp_mode=data["smtp_mode"],
            )
            self._refresh_account_list()

    def _delete_account(self):
        item = self.account_list.currentItem()
        if not item:
            return
        name = item.text()
        reply = QMessageBox.question(
            self,
            tr("confirm_title", self.lang),
            tr("confirm_delete", self.lang, name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.store.delete_account(name)
            self.current_account_name = None
            self._refresh_account_list()
            self._clear_inbox()

    def _on_select_account(self, current: QListWidgetItem, previous: QListWidgetItem):
        if current is None:
            return
        self.current_account_name = current.text()
        self._refresh_inbox()

    def _clear_inbox(self):
        self.table.setRowCount(0)
        self.current_emails = []
        self.body_view.clear()

    # ---------- входящие ----------

    def _refresh_inbox(self):
        if not self.current_account_name:
            QMessageBox.information(self, tr("info_title", self.lang), tr("select_account_first", self.lang))
            return
        account = self.store.get_account(self.current_account_name)
        self.statusBar().showMessage(tr("loading_emails", self.lang))
        self._clear_inbox()

        self.fetch_thread = FetchThread(account)
        self.fetch_thread.succeeded.connect(self._populate_inbox)
        self.fetch_thread.failed.connect(self._on_inbox_error)
        self.fetch_thread.start()

    def _populate_inbox(self, emails: list):
        self.current_emails = emails
        self.table.setRowCount(len(emails))
        for row, msg in enumerate(emails):
            self.table.setItem(row, 0, QTableWidgetItem(msg["from"]))
            self.table.setItem(row, 1, QTableWidgetItem(msg["subject"]))
            self.table.setItem(row, 2, QTableWidgetItem(msg["date"]))
        self.statusBar().showMessage(tr("emails_loaded", self.lang, count=len(emails)))

    def _on_inbox_error(self, message: str):
        self.statusBar().showMessage(tr("error_status", self.lang))
        QMessageBox.critical(self, tr("fetch_error_title", self.lang), message)

    def _on_select_email(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        index = rows[0].row()
        if 0 <= index < len(self.current_emails):
            self._render_email_body(self.current_emails[index])

    def _render_email_body(self, msg: dict):
        """
        Отображает тело письма с превью ссылок:
          - если есть HTML-версия письма, показываем её (после базовой
            санитизации) — ссылки там уже размечены тегами <a>, Qt сделает
            их кликабельными сам;
          - иначе берём обычный текст и оборачиваем найденные URL в <a>
            через html_utils.linkify().
        """
        html_body = msg.get("body_html")
        text_body = msg.get("body_text")

        if html_body:
            content = html_utils.sanitize_html(html_body)
            self.body_view.setHtml(content)
        elif text_body:
            content = html_utils.linkify(text_body)
            self.body_view.setHtml(content)
        else:
            self.body_view.setPlainText(tr("no_text_content", self.lang))

    # ---------- отправка ----------

    def _compose(self):
        if not self.current_account_name:
            QMessageBox.information(self, tr("info_title", self.lang), tr("select_account_for_compose", self.lang))
            return
        account = self.store.get_account(self.current_account_name)
        dialog = ComposeDialog(self, account, self.lang)
        dialog.exec()


def run_app():
    app = QApplication(sys.argv)
    store = AccountStore()

    # ---- выбор языка (один раз, если ещё не выбран) ----
    lang = store.get_language()
    if lang is None:
        lang_dialog = LanguageDialog()
        if lang_dialog.exec() != QDialog.DialogCode.Accepted or not lang_dialog.selected_lang:
            return
        lang = lang_dialog.selected_lang
        store.set_language(lang)

    # ---- мастер-пароль ----
    if not store.has_master_password():
        dialog = MasterPasswordDialog(None, creating=True, lang=lang)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.password:
            return
        store.setup_master_password(dialog.password)
    else:
        unlocked = False
        for _ in range(3):
            dialog = MasterPasswordDialog(None, creating=False, lang=lang)
            if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.password:
                return
            if store.unlock(dialog.password):
                unlocked = True
                break
            QMessageBox.critical(None, tr("error_title", lang), tr("wrong_master_password", lang))
        if not unlocked:
            return

    window = MainWindow(store, lang)
    window.show()
    sys.exit(app.exec())

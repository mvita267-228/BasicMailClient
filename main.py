#!/usr/bin/env python3
"""
Почтовый клиент с шифрованным хранилищем учётных данных (TinyDB + Fernet).

Версия для Windows 7 (32-bit) и Python 3.8.2 — использует PyQt5 вместо
PyQt6, так как PyQt6 официально не поддерживает ни Windows 7, ни Python
младше 3.9.

Запуск:
    pip install -r requirements-win7.txt
    python main.py
"""

from __future__ import annotations

from gui_qt5 import run_app

if __name__ == "__main__":
    run_app()

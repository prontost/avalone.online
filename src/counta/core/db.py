"""Единая SQLite-БД приложения: путь к файлу.

Каждый функциональный модуль (catalog, money, notify, lexicon,
entry_meta) держит СВОЮ таблицу и свой `_conn`, импортируя отсюда только путь
`DB_PATH`. Раньше модуль назывался `chatdb`, а файл — `chat.db` (эпоха
Telegram-бота, разворот №3); и модуль, и файл переименованы, чат-слой удалён.
"""

import os
from pathlib import Path

DB_PATH = Path(os.getenv("COUNTA_DB_PATH", Path.home() / ".counta" / "counta.db"))
_LEGACY_DB = DB_PATH.parent / "chat.db"
# Одноразовая идемпотентная миграция legacy-имени файла: chat.db -> counta.db.
# Срабатывает один раз при первом импорте модуля, если новый файл ещё не создан.
if not DB_PATH.exists() and _LEGACY_DB.exists():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _LEGACY_DB.rename(DB_PATH)

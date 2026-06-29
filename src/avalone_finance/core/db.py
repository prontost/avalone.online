"""Avalone Finance DB connector: uses the unified Avalone SQLite database.

All Avalone Finance tables live in the unified DB and use the `money_` prefix. Modules
continue importing `DB_PATH` from here; the actual connection comes from
`avalone_core.db`.
"""

from pathlib import Path

from avalone_core.database import Database


def _db_path() -> Path:
    """Return the currently configured Avalone DB path.

    This mirrors ``Database.shared().path`` so tests that set ``AVALONE_DB_PATH``
    before importing finance still point at the same database as the portal.
    """
    return Database.shared().path


DB_PATH: Path = _db_path()

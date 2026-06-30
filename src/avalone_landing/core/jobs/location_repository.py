"""Repository for location translations.

Locations are raw strings coming from external job boards.  This table stores
human translations for each unique location so the UI can display them in the
user's preferred language without hardcoding hundreds of values in code.
"""

from __future__ import annotations

from avalone_core.database import Database, Repository


class LocationTranslationRepository(Repository):
    """Read and write translations for raw location strings."""

    def ensure_schema(self) -> None:
        with self._db.connection() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS work_location_translations (
                    location TEXT PRIMARY KEY,
                    ru       TEXT,
                    en       TEXT,
                    ko       TEXT
                )
                """
            )
            con.commit()

    def get(self, location: str, lang: str) -> str | None:
        """Return the translation for ``location`` in ``lang`` if it exists."""
        if not location:
            return None
        with self._db.connection() as con:
            row = con.execute(
                f"SELECT {lang} FROM work_location_translations WHERE location = ?",
                (location,),
            ).fetchone()
        return row[0] if row and row[0] else None

    def list_missing(self, locations: list[str]) -> list[str]:
        """Return locations from the list that have no translation at all."""
        if not locations:
            return []
        placeholders = ",".join("?" for _ in locations)
        with self._db.connection() as con:
            rows = con.execute(
                "SELECT location FROM work_location_translations "
                f"WHERE location IN ({placeholders}) "
                "AND COALESCE(ru, en, ko) IS NOT NULL",
                locations,
            ).fetchall()
        existing = {r[0] for r in rows}
        return [loc for loc in locations if loc not in existing]

    def save(self, location: str, translations: dict[str, str]) -> None:
        """Upsert translations for a single location.

        ``translations`` maps language codes ('ru', 'en', 'ko') to strings.
        """
        with self._db.connection() as con:
            con.execute(
                """
                INSERT INTO work_location_translations (location, ru, en, ko)
                VALUES (:location, :ru, :en, :ko)
                ON CONFLICT(location) DO UPDATE SET
                    ru = COALESCE(excluded.ru, work_location_translations.ru),
                    en = COALESCE(excluded.en, work_location_translations.en),
                    ko = COALESCE(excluded.ko, work_location_translations.ko)
                """,
                {
                    "location": location,
                    "ru": translations.get("ru"),
                    "en": translations.get("en"),
                    "ko": translations.get("ko"),
                },
            )
            con.commit()

    def save_many(self, items: list[tuple[str, dict[str, str]]]) -> None:
        """Batch upsert location translations."""
        with self._db.connection() as con:
            for location, translations in items:
                con.execute(
                    """
                    INSERT INTO work_location_translations (location, ru, en, ko)
                    VALUES (:location, :ru, :en, :ko)
                    ON CONFLICT(location) DO UPDATE SET
                        ru = COALESCE(excluded.ru, work_location_translations.ru),
                        en = COALESCE(excluded.en, work_location_translations.en),
                        ko = COALESCE(excluded.ko, work_location_translations.ko)
                    """,
                    {
                        "location": location,
                        "ru": translations.get("ru"),
                        "en": translations.get("en"),
                        "ko": translations.get("ko"),
                    },
                )
            con.commit()

    def all(self) -> dict[str, dict[str, str | None]]:
        """Return every stored translation keyed by location."""
        with self._db.connection() as con:
            rows = con.execute(
                "SELECT location, ru, en, ko FROM work_location_translations"
            ).fetchall()
        return {
            r["location"]: {"ru": r["ru"], "en": r["en"], "ko": r["ko"]}
            for r in rows
        }

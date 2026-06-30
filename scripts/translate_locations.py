#!/usr/bin/env python3
"""Batch-translate unique job locations through the local Kimi CLI.

This script is idempotent: re-running it will only translate locations that do
not yet have any translation stored in ``work_location_translations``.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Make the project packages importable.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "avalone_core"))

from avalone_core.database import Database
from avalone_landing.core.jobs.location_repository import LocationTranslationRepository


def _log(message: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {message}", flush=True)


def _run_kimi(prompt: str, timeout: int = 120) -> str:
    """Send a prompt to the local Kimi CLI and return the raw answer."""
    import shutil

    kimi_cli = shutil.which("kimi") or str(Path.home() / ".kimi-code" / "bin" / "kimi")
    result = subprocess.run(
        [kimi_cli, "-p", prompt, "--output-format", "text"],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Kimi CLI failed: {result.stderr or result.stdout}")
    return result.stdout.strip()


def _parse_json_block(text: str) -> dict:
    """Extract the first JSON object from the Kimi response."""
    text = text.strip()
    # Remove markdown code fences if present.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    # Strip bullet/thinking markers that may appear before JSON.
    text = re.sub(r"(?m)^\s*[•*-]\s.*$", "", text)
    text = text.strip()
    # Extract the outermost JSON object/array.
    start = text.find("{")
    if start == -1:
        start = text.find("[")
    end = text.rfind("}")
    if end == -1:
        end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object/array found in response")
    return json.loads(text[start : end + 1])


def _translate_batch(locations: list[str]) -> dict[str, dict[str, str]]:
    """Translate a batch of locations into ru/en/ko.

    Returns a dict ``{original_location: {"ru": ..., "en": ..., "ko": ...}}``.
    """
    if not locations:
        return {}

    prompt = (
        "Translate each Korean/English location into Russian, English and Korean. "
        "Return ONLY a JSON object where keys are the original location strings "
        "and each value is an object with keys 'ru', 'en', 'ko'. "
        "Keep addresses concrete; do not invent details. "
        "If the original is already in a given language, you may return it unchanged for that language.\n\n"
        + json.dumps(locations, ensure_ascii=False)
    )

    raw = _run_kimi(prompt, timeout=max(60, len(locations) * 10))
    data = _parse_json_block(raw)

    result: dict[str, dict[str, str]] = {}
    for loc in locations:
        item = data.get(loc, {})
        result[loc] = {
            "ru": str(item.get("ru", "")).strip(),
            "en": str(item.get("en", "")).strip(),
            "ko": str(item.get("ko", "")).strip(),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Translate job locations")
    parser.add_argument("--batch", type=int, default=20, help="Locations per batch")
    parser.add_argument(
        "--timeout", type=int, default=3600, help="Max total runtime in seconds"
    )
    parser.add_argument(
        "--interval", type=int, default=5, help="Seconds to wait when no work left"
    )
    parser.add_argument(
        "--loop", action="store_true", help="Keep running until timeout"
    )
    parser.add_argument(
        "--max-failures", type=int, default=10, help="Stop after N consecutive failures"
    )
    args = parser.parse_args()

    repo = LocationTranslationRepository()
    repo.ensure_schema()

    db = Database.shared()
    failures = 0
    started = time.monotonic()
    total_translated = 0

    while True:
        if time.monotonic() - started > args.timeout:
            _log("Timeout reached; stopping.")
            break

        with db.connection() as con:
            rows = con.execute(
                "SELECT DISTINCT location FROM work_job_posts "
                "WHERE location IS NOT NULL AND location != ''"
            ).fetchall()
        all_locations = [r[0] for r in rows]
        missing = repo.list_missing(all_locations)

        if not missing:
            _log("No untranslated locations left.")
            if args.loop:
                time.sleep(args.interval)
                continue
            break

        batch = missing[: args.batch]
        _log(f"Batch: translating {len(batch)} locations...")
        try:
            translations = _translate_batch(batch)
        except Exception as exc:
            failures += 1
            _log(f"Batch failed ({failures}/{args.max_failures}): {exc}")
            if failures >= args.max_failures:
                _log("Max failures reached; stopping.")
                return 1
            time.sleep(10)
            continue

        valid_items = []
        for loc, trans in translations.items():
            if trans.get("ru") or trans.get("en") or trans.get("ko"):
                valid_items.append((loc, trans))

        if valid_items:
            repo.save_many(valid_items)
            total_translated += len(valid_items)
            _log(f"Batch done: {len(valid_items)}/{len(batch)} applied (total {total_translated}).")
            failures = 0
        else:
            failures += 1
            _log(f"Batch returned no valid translations ({failures}/{args.max_failures}).")
            if failures >= args.max_failures:
                return 1
            time.sleep(10)

        if not args.loop and len(missing) <= args.batch:
            break

    _log(f"Done. {total_translated} locations translated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

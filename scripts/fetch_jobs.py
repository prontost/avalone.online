#!/usr/bin/env python3
"""Fetch recent job postings from configured boards and store them in Avalone DB.

Usage:
    uv run python scripts/fetch_jobs.py [--days 14]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from avalone_core.db import migrate
from avalone_landing.core.jobs.service import JobPostService


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch job postings into Avalone")
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Maximum age of postings to fetch (default: 14)",
    )
    args = parser.parse_args()

    migrate()
    result = JobPostService().fetch_and_store(max_age_days=args.days)
    print(f"Fetched and stored {result['fetched']} postings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

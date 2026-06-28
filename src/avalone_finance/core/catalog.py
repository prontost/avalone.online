"""Canonical personal-finance categories + localized labels.

Categories are intentionally minimal (~12 expense + ~4 income) so that
analytics, tips and the 50/30/20 rule stay readable. Every category has a
role: need / want / goal.

This module is now a backward-compatible facade over :class:`CatalogService`.
All raw SQL lives in :mod:`catalog_repository`, and business logic lives in
:mod:`catalog_service`.
"""

from __future__ import annotations

from avalone_finance.core.catalog_service import (
    CANON,
    DEFAULT_KEYS,
    CatalogService,
)

_default_service = CatalogService()

# Canonical data is exposed directly so importers can keep using
# ``catalog.CANON`` and ``catalog.DEFAULT_KEYS``.
canon_key = CatalogService.canon_key
role = CatalogService.role

# Backward-compatible module-level API.
set_labels = _default_service.set_labels
forget_labels = _default_service.forget_labels
label = _default_service.label
seed_glossary = _default_service.seed_glossary
known_accounts = _default_service.known_accounts
is_user_category = _default_service.is_user_category
ensure_user_catalog = _default_service.ensure_user_catalog

# keep private helpers available for any internal callers that used them
_tid = _default_service._tid
_user_labels = _default_service._user_labels

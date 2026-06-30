"""Job aggregation module for the Avalone Work branch."""

from .models import JobPost
from .parser import BaseJobParser, ExpatComKoreaParser, KoreabridgeRSSParser, MultiSourceParser
from .repository import JobPostRepository
from .service import JobPostService

__all__ = [
    "BaseJobParser",
    "JobPost",
    "ExpatComKoreaParser",
    "KoreabridgeRSSParser",
    "MultiSourceParser",
    "JobPostRepository",
    "JobPostService",
]

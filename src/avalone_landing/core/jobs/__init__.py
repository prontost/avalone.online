"""Job aggregation module for the Avalone Work branch."""

from .interaction_repository import UserJobInteractionRepository
from .models import JobPost, UserJobInteraction
from .parser import AlbamonParser, BaseJobParser, JobKoreaParser, KoreabridgeRSSParser, MultiSourceParser, OneOneFourParser, SaraminParser
from .repository import JobPostRepository
from .service import JobPostService

__all__ = [
    "BaseJobParser",
    "JobPost",
    "UserJobInteraction",
    "AlbamonParser",
    "JobKoreaParser",
    "KoreabridgeRSSParser",
    "OneOneFourParser",
    "SaraminParser",
    "MultiSourceParser",
    "JobPostRepository",
    "JobPostService",
    "UserJobInteractionRepository",
]

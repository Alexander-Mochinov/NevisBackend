"""Search query normalization."""

import re

WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_query(query: str) -> str:
    """Trim, lowercase, and collapse whitespace while preserving token punctuation."""
    return WHITESPACE_PATTERN.sub(" ", query.strip().lower())


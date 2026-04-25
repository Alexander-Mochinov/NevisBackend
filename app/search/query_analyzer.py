"""Search query analysis."""

import re

from app.search.normalizer import normalize_query
from app.search.types import QueryAnalysis, QueryType

EMAIL_LIKE_PATTERN = re.compile(r"^[^\s@]+@[^\s@]*$")
DOMAIN_LIKE_PATTERN = re.compile(r"^(?:[a-z0-9-]+\.)+[a-z]{2,}$")
DOCUMENT_SEMANTIC_TERMS = frozenset(
    {
        "address",
        "proof",
        "document",
        "bill",
        "passport",
        "statement",
        "income",
        "bank",
        "kyc",
        "identity",
        "residence",
        "verification",
    }
)


def analyze_query(query: str) -> QueryAnalysis:
    """Classify a normalized search query into a simple query type."""
    normalized_query = normalize_query(query)
    tokens = tuple(normalized_query.split()) if normalized_query else ()
    query_type = _classify(normalized_query, tokens)
    return QueryAnalysis(query=normalized_query, query_type=query_type, tokens=tokens)


def _classify(query: str, tokens: tuple[str, ...]) -> QueryType:
    if not query:
        return QueryType.GENERAL

    if "@" in query or EMAIL_LIKE_PATTERN.match(query):
        return QueryType.EMAIL_EXACT_OR_PARTIAL

    if DOMAIN_LIKE_PATTERN.match(query) or _looks_like_domain_fragment(query):
        return QueryType.DOMAIN_LIKE

    if tokens and any(token in DOCUMENT_SEMANTIC_TERMS for token in tokens):
        return QueryType.DOCUMENT_SEMANTIC

    if 1 <= len(tokens) <= 3 and all(_looks_name_token(token) for token in tokens):
        return QueryType.PERSON_NAME_LIKE

    return QueryType.GENERAL


def _looks_like_domain_fragment(query: str) -> bool:
    return "." not in query and any(
        marker in query for marker in ("wealth", "bank", "capital", "advis", "finance")
    )


def _looks_name_token(token: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z'-]*", token))


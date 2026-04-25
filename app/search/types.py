"""Shared search core types."""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class QueryType(StrEnum):
    """Supported high-level query types."""

    EMAIL_EXACT_OR_PARTIAL = "email_exact_or_partial"
    DOMAIN_LIKE = "domain_like"
    PERSON_NAME_LIKE = "person_name_like"
    DOCUMENT_SEMANTIC = "document_semantic"
    GENERAL = "general"


class SearchChannel(StrEnum):
    """Candidate retrieval channel identifiers."""

    CLIENT_EXACT = "client_exact"
    CLIENT_TRIGRAM = "client_trigram"
    CLIENT_FULLTEXT = "client_fulltext"
    DOCUMENT_VECTOR = "document_vector"
    DOCUMENT_FULLTEXT = "document_fulltext"
    DOCUMENT_TITLE_TRIGRAM = "document_title_trigram"
    DOCUMENT_SYNONYM = "document_synonym"


class SearchResultType(StrEnum):
    """Searchable domain result types."""

    CLIENT = "client"
    DOCUMENT = "document"


class MatchReason(StrEnum):
    """Business-level match reasons."""

    EXACT_EMAIL = "exact_email"
    EMAIL_DOMAIN = "email_domain"
    EXACT_DOCUMENT_TITLE = "exact_document_title"
    HIGH_SEMANTIC_CONFIDENCE = "high_semantic_confidence"


@dataclass(frozen=True)
class QueryAnalysis:
    """Analysis result for a normalized query."""

    query: str
    query_type: QueryType
    tokens: tuple[str, ...]


@dataclass(frozen=True)
class RankedCandidate:
    """Candidate returned by a retrieval channel."""

    result_id: str
    rank: int
    channel: SearchChannel


@dataclass
class ScoredResult:
    """Search result score container."""

    result_id: str
    score: float = 0.0
    normalized_score: float = 0.0
    match_reasons: set[MatchReason] = field(default_factory=set)


@dataclass(frozen=True)
class SearchCandidate:
    """Internal candidate returned by a single database retrieval channel."""

    result_type: SearchResultType
    id: uuid.UUID
    channel: SearchChannel
    rank: int
    raw_score: float
    matched_fields: tuple[str, ...]
    highlights: tuple[str, ...]
    payload: Mapping[str, object]


@dataclass(frozen=True)
class CandidateRetrievalResult:
    """Raw hybrid retrieval output before rank fusion and business boosts."""

    query: str
    analysis: QueryAnalysis
    expanded_queries: tuple[str, ...]
    candidates_by_channel: Mapping[SearchChannel, tuple[SearchCandidate, ...]]

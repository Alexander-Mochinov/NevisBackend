"""Search response schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SearchClientPayload(BaseModel):
    """Client details included in a search result."""

    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    description: str | None
    social_links: list[str] | None
    created_at: datetime
    updated_at: datetime


class SearchDocumentPayload(BaseModel):
    """Document details included in a search result."""

    id: uuid.UUID
    client_id: uuid.UUID
    title: str
    content: str | None = None
    summary: str | None
    created_at: datetime
    best_chunk_excerpt: str | None = None


class SearchResultRead(BaseModel):
    """Public mixed search result."""

    type: Literal["client", "document"]
    id: uuid.UUID
    score: float
    match_reason: str
    matched_fields: list[str]
    highlights: list[str]
    client: SearchClientPayload | None = None
    document: SearchDocumentPayload | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "document",
                    "id": "85a2202e-a0ae-4087-b73d-250dc04b812f",
                    "score": 1.0,
                    "match_reason": "Synonym match: address proof ≈ utility bill",
                    "matched_fields": ["chunk.content", "synonym:utility bill"],
                    "highlights": [
                        (
                            "The client uploaded a recent utility bill as proof of residence "
                            "and address verification."
                        )
                    ],
                    "client": None,
                    "document": {
                        "id": "85a2202e-a0ae-4087-b73d-250dc04b812f",
                        "client_id": "6b8ed0b3-6635-4901-9cb2-ec65893f51f1",
                        "title": "Utility Bill",
                        "content": (
                            "The client uploaded a recent utility bill as proof of residence "
                            "and address verification."
                        ),
                        "summary": (
                            "The client uploaded a recent utility bill as proof of residence "
                            "and address verification."
                        ),
                        "created_at": "2026-04-25T10:01:00Z",
                        "best_chunk_excerpt": (
                            "The client uploaded a recent utility bill as proof of residence "
                            "and address verification."
                        ),
                    },
                }
            ]
        }
    )


class SearchChannelExplanationRead(BaseModel):
    """Explain output for one retrieval channel."""

    channel: str
    candidate_count: int
    top_result_ids: list[str]


class SearchResultExplanationRead(BaseModel):
    """Explain output for one ranked result."""

    result_id: str
    result_type: Literal["client", "document"]
    channels: list[str]
    rrf_contributions: dict[str, float]
    business_boosts: list[str]
    final_score: float
    normalized_score: float


class SearchExplanationRead(BaseModel):
    """Debug explanation for the hybrid search pipeline."""

    original_query: str
    normalized_query: str
    query_type: str
    tokens: list[str]
    expanded_queries: list[str]
    channels: list[SearchChannelExplanationRead]
    results: list[SearchResultExplanationRead]


class SearchExplainResponseRead(BaseModel):
    """Search response with pipeline explanation enabled."""

    results: list[SearchResultRead]
    explanation: SearchExplanationRead

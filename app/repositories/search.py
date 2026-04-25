"""Database candidate retrieval for hybrid search."""

import uuid
from collections.abc import Iterable, Mapping
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam, text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from app.search.types import SearchCandidate, SearchChannel, SearchResultType

DEFAULT_CHANNEL_LIMIT = 50
TRIGRAM_THRESHOLD = 0.10


class SearchRepository:
    """Small, channel-specific search queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def client_exact(self, query: str, *, limit: int = DEFAULT_CHANNEL_LIMIT) -> tuple[
        SearchCandidate, ...
    ]:
        """Find clients by exact or substring matches."""
        if not query:
            return ()

        statement = text(
            """
            SELECT
                id,
                first_name,
                last_name,
                email,
                description,
                social_links,
                created_at,
                updated_at,
                CASE
                    WHEN lower(email) = :query THEN 1.0
                    WHEN lower(email) LIKE :pattern THEN 0.9
                    WHEN lower(first_name || ' ' || last_name) LIKE :pattern THEN 0.85
                    WHEN lower(first_name) LIKE :pattern THEN 0.8
                    WHEN lower(last_name) LIKE :pattern THEN 0.8
                    ELSE 0.0
                END AS raw_score
            FROM clients
            WHERE
                lower(email) LIKE :pattern
                OR lower(first_name) LIKE :pattern
                OR lower(last_name) LIKE :pattern
                OR lower(first_name || ' ' || last_name) LIKE :pattern
            ORDER BY raw_score DESC, created_at DESC, id
            LIMIT :limit
            """
        )
        rows = await self._fetch_mappings(
            statement,
            {"query": query, "pattern": _contains_pattern(query), "limit": limit},
        )
        return tuple(
            _client_candidate(
                row=row,
                channel=SearchChannel.CLIENT_EXACT,
                rank=index + 1,
                query=query,
            )
            for index, row in enumerate(rows)
        )

    async def client_trigram(self, query: str, *, limit: int = DEFAULT_CHANNEL_LIMIT) -> tuple[
        SearchCandidate, ...
    ]:
        """Find clients by PostgreSQL trigram similarity."""
        if not query:
            return ()

        statement = text(
            """
            SELECT
                id,
                first_name,
                last_name,
                email,
                description,
                social_links,
                created_at,
                updated_at,
                similarity(lower(email), :query) AS email_score,
                similarity(lower(first_name), :query) AS first_name_score,
                similarity(lower(last_name), :query) AS last_name_score,
                similarity(lower(coalesce(description, '')), :query) AS description_score,
                greatest(
                    similarity(lower(email), :query),
                    similarity(lower(first_name), :query),
                    similarity(lower(last_name), :query),
                    similarity(lower(coalesce(description, '')), :query)
                ) AS raw_score
            FROM clients
            WHERE greatest(
                similarity(lower(email), :query),
                similarity(lower(first_name), :query),
                similarity(lower(last_name), :query),
                similarity(lower(coalesce(description, '')), :query)
            ) >= :threshold
            ORDER BY raw_score DESC, created_at DESC, id
            LIMIT :limit
            """
        )
        rows = await self._fetch_mappings(
            statement,
            {"query": query, "threshold": TRIGRAM_THRESHOLD, "limit": limit},
        )
        return tuple(
            _client_candidate(
                row=row,
                channel=SearchChannel.CLIENT_TRIGRAM,
                rank=index + 1,
                query=query,
                trigram=True,
            )
            for index, row in enumerate(rows)
        )

    async def client_fulltext(self, query: str, *, limit: int = DEFAULT_CHANNEL_LIMIT) -> tuple[
        SearchCandidate, ...
    ]:
        """Find clients by PostgreSQL full-text search."""
        if not query:
            return ()

        statement = text(
            """
            WITH search AS (
                SELECT websearch_to_tsquery('simple', :query) AS tsq
            )
            SELECT
                c.id,
                c.first_name,
                c.last_name,
                c.email,
                c.description,
                c.social_links,
                c.created_at,
                c.updated_at,
                ts_rank_cd(
                    coalesce(
                        c.search_vector,
                        to_tsvector(
                            'simple',
                            concat_ws(
                                ' ',
                                c.first_name,
                                c.last_name,
                                c.email,
                                coalesce(c.description, '')
                            )
                        )
                    ),
                    search.tsq
                ) AS raw_score
            FROM clients c
            CROSS JOIN search
            WHERE coalesce(
                c.search_vector,
                to_tsvector(
                    'simple',
                    concat_ws(' ', c.first_name, c.last_name, c.email, coalesce(c.description, ''))
                )
            ) @@ search.tsq
            ORDER BY raw_score DESC, c.created_at DESC, c.id
            LIMIT :limit
            """
        )
        rows = await self._fetch_mappings(statement, {"query": query, "limit": limit})
        return tuple(
            _client_candidate(
                row=row,
                channel=SearchChannel.CLIENT_FULLTEXT,
                rank=index + 1,
                query=query,
            )
            for index, row in enumerate(rows)
        )

    async def document_vector(
        self,
        query_embedding: list[float],
        *,
        limit: int = DEFAULT_CHANNEL_LIMIT,
    ) -> tuple[SearchCandidate, ...]:
        """Find documents by nearest chunk embedding and aggregate to document candidates."""
        if not query_embedding:
            return ()

        statement = text(
            """
            WITH ranked_chunks AS (
                SELECT
                    d.id,
                    d.client_id,
                    d.title,
                    d.content,
                    d.summary,
                    d.created_at,
                    dc.content AS excerpt,
                    1.0 - (dc.embedding <=> :embedding) AS raw_score,
                    row_number() OVER (
                        PARTITION BY d.id
                        ORDER BY dc.embedding <=> :embedding ASC, dc.chunk_index ASC
                    ) AS document_rank
                FROM document_chunks dc
                JOIN documents d ON d.id = dc.document_id
                WHERE dc.embedding IS NOT NULL
                ORDER BY dc.embedding <=> :embedding ASC, dc.chunk_index ASC
                LIMIT :chunk_limit
            )
            SELECT id, client_id, title, content, summary, created_at, excerpt, raw_score
            FROM ranked_chunks
            WHERE document_rank = 1
            ORDER BY raw_score DESC, id
            LIMIT :limit
            """
        ).bindparams(bindparam("embedding", type_=Vector(384)))
        rows = await self._fetch_mappings(
            statement,
            {
                "embedding": query_embedding,
                "chunk_limit": max(limit * 3, limit),
                "limit": limit,
            },
        )
        return tuple(
            _document_candidate(
                row=row,
                channel=SearchChannel.DOCUMENT_VECTOR,
                rank=index + 1,
                matched_fields=("chunk.embedding",),
            )
            for index, row in enumerate(rows)
        )

    async def document_fulltext(self, query: str, *, limit: int = DEFAULT_CHANNEL_LIMIT) -> tuple[
        SearchCandidate, ...
    ]:
        """Find documents by document or chunk full-text search."""
        if not query:
            return ()

        statement = text(
            """
            WITH search AS (
                SELECT websearch_to_tsquery('simple', :query) AS tsq
            ),
            candidate_rows AS (
                SELECT
                    d.id,
                    d.client_id,
                    d.title,
                    d.content,
                    d.summary,
                    d.created_at,
                    d.content AS excerpt,
                    'document.search_vector' AS matched_field,
                    ts_rank_cd(
                        coalesce(
                            d.search_vector,
                            to_tsvector(
                                'simple',
                                concat_ws(' ', d.title, d.content, coalesce(d.summary, ''))
                            )
                        ),
                        search.tsq
                    ) AS raw_score
                FROM documents d
                CROSS JOIN search
                WHERE coalesce(
                    d.search_vector,
                    to_tsvector(
                        'simple',
                        concat_ws(' ', d.title, d.content, coalesce(d.summary, ''))
                    )
                ) @@ search.tsq

                UNION ALL

                SELECT
                    d.id,
                    d.client_id,
                    d.title,
                    d.content,
                    d.summary,
                    d.created_at,
                    dc.content AS excerpt,
                    'document_chunks.search_vector' AS matched_field,
                    ts_rank_cd(
                        coalesce(dc.search_vector, to_tsvector('simple', dc.content)),
                        search.tsq
                    ) AS raw_score
                FROM document_chunks dc
                JOIN documents d ON d.id = dc.document_id
                CROSS JOIN search
                WHERE coalesce(dc.search_vector, to_tsvector('simple', dc.content)) @@ search.tsq
            ),
            best_rows AS (
                SELECT DISTINCT ON (id)
                    id,
                    client_id,
                    title,
                    content,
                    summary,
                    created_at,
                    excerpt,
                    matched_field,
                    raw_score
                FROM candidate_rows
                ORDER BY id, raw_score DESC
            )
            SELECT
                id,
                client_id,
                title,
                content,
                summary,
                created_at,
                excerpt,
                matched_field,
                raw_score
            FROM best_rows
            ORDER BY raw_score DESC, id
            LIMIT :limit
            """
        )
        rows = await self._fetch_mappings(statement, {"query": query, "limit": limit})
        return tuple(
            _document_candidate(
                row=row,
                channel=SearchChannel.DOCUMENT_FULLTEXT,
                rank=index + 1,
                matched_fields=(str(row["matched_field"]),),
            )
            for index, row in enumerate(rows)
        )

    async def document_title_trigram(
        self,
        query: str,
        *,
        limit: int = DEFAULT_CHANNEL_LIMIT,
    ) -> tuple[SearchCandidate, ...]:
        """Find documents by title trigram similarity."""
        if not query:
            return ()

        statement = text(
            """
            SELECT
                id,
                client_id,
                title,
                content,
                summary,
                created_at,
                content AS excerpt,
                similarity(lower(title), :query) AS raw_score
            FROM documents
            WHERE similarity(lower(title), :query) >= :threshold
            ORDER BY raw_score DESC, created_at DESC, id
            LIMIT :limit
            """
        )
        rows = await self._fetch_mappings(
            statement,
            {"query": query, "threshold": TRIGRAM_THRESHOLD, "limit": limit},
        )
        return tuple(
            _document_candidate(
                row=row,
                channel=SearchChannel.DOCUMENT_TITLE_TRIGRAM,
                rank=index + 1,
                matched_fields=("title",),
            )
            for index, row in enumerate(rows)
        )

    async def document_synonym(
        self,
        expanded_queries: Iterable[str],
        *,
        limit: int = DEFAULT_CHANNEL_LIMIT,
    ) -> tuple[SearchCandidate, ...]:
        """Find documents with synonym-expanded lexical matching."""
        best_by_document_id: dict[uuid.UUID, SearchCandidate] = {}

        for term in expanded_queries:
            if not term:
                continue

            rows = await self._document_synonym_term(term=term, limit=limit)
            for row in rows:
                candidate = _document_candidate(
                    row=row,
                    channel=SearchChannel.DOCUMENT_SYNONYM,
                    rank=1,
                    matched_fields=(str(row["matched_field"]), f"synonym:{term}"),
                )
                current = best_by_document_id.get(candidate.id)
                if current is None or candidate.raw_score > current.raw_score:
                    best_by_document_id[candidate.id] = candidate

        ordered = sorted(
            best_by_document_id.values(),
            key=lambda candidate: (-candidate.raw_score, str(candidate.id)),
        )[:limit]
        return tuple(
            _replace_rank(candidate, rank=index + 1) for index, candidate in enumerate(ordered)
        )

    async def _document_synonym_term(
        self,
        *,
        term: str,
        limit: int,
    ) -> list[RowMapping]:
        statement = text(
            """
            WITH search AS (
                SELECT websearch_to_tsquery('simple', :term) AS tsq
            ),
            candidate_rows AS (
                SELECT
                    d.id,
                    d.client_id,
                    d.title,
                    d.content,
                    d.summary,
                    d.created_at,
                    d.content AS excerpt,
                    CASE
                        WHEN lower(d.title) LIKE :pattern THEN 'title'
                        WHEN lower(d.content) LIKE :pattern THEN 'content'
                        ELSE 'document.search_vector'
                    END AS matched_field,
                    CASE
                        WHEN lower(d.title) LIKE :pattern THEN 1.0
                        WHEN lower(d.content) LIKE :pattern THEN 0.9
                        ELSE ts_rank_cd(
                            coalesce(
                                d.search_vector,
                                to_tsvector(
                                    'simple',
                                    concat_ws(' ', d.title, d.content, coalesce(d.summary, ''))
                                )
                            ),
                            search.tsq
                        )
                    END AS raw_score
                FROM documents d
                CROSS JOIN search
                WHERE
                    lower(d.title) LIKE :pattern
                    OR lower(d.content) LIKE :pattern
                    OR coalesce(
                        d.search_vector,
                        to_tsvector(
                            'simple',
                            concat_ws(' ', d.title, d.content, coalesce(d.summary, ''))
                        )
                    ) @@ search.tsq

                UNION ALL

                SELECT
                    d.id,
                    d.client_id,
                    d.title,
                    d.content,
                    d.summary,
                    d.created_at,
                    dc.content AS excerpt,
                    CASE
                        WHEN lower(dc.content) LIKE :pattern THEN 'chunk.content'
                        ELSE 'document_chunks.search_vector'
                    END AS matched_field,
                    CASE
                        WHEN lower(dc.content) LIKE :pattern THEN 0.95
                        ELSE ts_rank_cd(
                            coalesce(dc.search_vector, to_tsvector('simple', dc.content)),
                            search.tsq
                        )
                    END AS raw_score
                FROM document_chunks dc
                JOIN documents d ON d.id = dc.document_id
                CROSS JOIN search
                WHERE
                    lower(dc.content) LIKE :pattern
                    OR coalesce(dc.search_vector, to_tsvector('simple', dc.content)) @@ search.tsq
            ),
            best_rows AS (
                SELECT DISTINCT ON (id)
                    id,
                    client_id,
                    title,
                    content,
                    summary,
                    created_at,
                    excerpt,
                    matched_field,
                    raw_score
                FROM candidate_rows
                ORDER BY id, raw_score DESC
            )
            SELECT
                id,
                client_id,
                title,
                content,
                summary,
                created_at,
                excerpt,
                matched_field,
                raw_score
            FROM best_rows
            ORDER BY raw_score DESC, id
            LIMIT :limit
            """
        )
        return await self._fetch_mappings(
            statement,
            {"term": term, "pattern": _contains_pattern(term), "limit": limit},
        )

    async def _fetch_mappings(
        self,
        statement: Any,
        parameters: Mapping[str, object],
    ) -> list[RowMapping]:
        result = await self._session.execute(statement, parameters)
        return list(result.mappings().all())


def _client_candidate(
    *,
    row: RowMapping,
    channel: SearchChannel,
    rank: int,
    query: str,
    trigram: bool = False,
) -> SearchCandidate:
    matched_fields = _client_matched_fields(row=row, query=query, trigram=trigram)
    first_name = str(row["first_name"])
    last_name = str(row["last_name"])
    email = str(row["email"])
    description = row["description"]
    client_name_highlight = (
        f"{first_name} {last_name}"
        if {"first_name", "last_name"} & set(matched_fields)
        else None
    )
    description_highlight = (
        _excerpt(str(description), query)
        if description and "description" in matched_fields
        else None
    )
    highlights = tuple(
        excerpt
        for excerpt in (
            email if "email" in matched_fields else None,
            client_name_highlight,
            description_highlight,
        )
        if excerpt
    )
    return SearchCandidate(
        result_type=SearchResultType.CLIENT,
        id=_uuid(row["id"]),
        channel=channel,
        rank=rank,
        raw_score=float(row["raw_score"]),
        matched_fields=matched_fields,
        highlights=highlights,
        payload={
            "id": _uuid(row["id"]),
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "description": description,
            "social_links": row["social_links"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "full_name": f"{first_name} {last_name}",
        },
    )


def _document_candidate(
    *,
    row: RowMapping,
    channel: SearchChannel,
    rank: int,
    matched_fields: tuple[str, ...],
) -> SearchCandidate:
    title = str(row["title"])
    excerpt = _excerpt(str(row["excerpt"]), "") if row["excerpt"] else ""
    return SearchCandidate(
        result_type=SearchResultType.DOCUMENT,
        id=_uuid(row["id"]),
        channel=channel,
        rank=rank,
        raw_score=float(row["raw_score"]),
        matched_fields=matched_fields,
        highlights=(excerpt,) if excerpt else (),
        payload={
            "id": _uuid(row["id"]),
            "client_id": str(row["client_id"]),
            "title": title,
            "content": row["content"],
            "summary": row["summary"],
            "created_at": row["created_at"],
            "best_chunk_excerpt": excerpt or None,
        },
    )


def _client_matched_fields(*, row: RowMapping, query: str, trigram: bool) -> tuple[str, ...]:
    if trigram:
        score_fields = (
            ("email", "email_score"),
            ("first_name", "first_name_score"),
            ("last_name", "last_name_score"),
            ("description", "description_score"),
        )
        return tuple(field for field, score_key in score_fields if float(row[score_key]) > 0.0)

    query_lower = query.lower()
    first_name = str(row["first_name"]).lower()
    last_name = str(row["last_name"]).lower()
    full_name = f"{first_name} {last_name}"
    description = str(row["description"] or "").lower()
    field_values = (
        ("email", str(row["email"]).lower()),
        ("first_name", first_name),
        ("last_name", last_name),
        ("full_name", full_name),
        ("description", description),
    )
    return tuple(field for field, value in field_values if query_lower in value)


def _replace_rank(candidate: SearchCandidate, *, rank: int) -> SearchCandidate:
    return SearchCandidate(
        result_type=candidate.result_type,
        id=candidate.id,
        channel=candidate.channel,
        rank=rank,
        raw_score=candidate.raw_score,
        matched_fields=candidate.matched_fields,
        highlights=candidate.highlights,
        payload=candidate.payload,
    )


def _contains_pattern(query: str) -> str:
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _excerpt(value: str, query: str, *, max_length: int = 220) -> str:
    collapsed = " ".join(value.split())
    if len(collapsed) <= max_length:
        return collapsed

    query_index = collapsed.lower().find(query.lower()) if query else -1
    if query_index < 0:
        return f"{collapsed[:max_length].rstrip()}..."

    start = max(query_index - 60, 0)
    end = min(start + max_length, len(collapsed))
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(collapsed) else ""
    return f"{prefix}{collapsed[start:end].strip()}{suffix}"


def _uuid(value: object) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))

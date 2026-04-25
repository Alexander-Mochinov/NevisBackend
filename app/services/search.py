"""Search retrieval and ranking use cases."""

import asyncio
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from fastapi import status

from app.core.errors import AppError
from app.repositories.search import DEFAULT_CHANNEL_LIMIT, SearchRepository
from app.schemas.search import (
    SearchChannelExplanationRead,
    SearchClientPayload,
    SearchDocumentPayload,
    SearchExplainResponseRead,
    SearchExplanationRead,
    SearchResultExplanationRead,
    SearchResultRead,
)
from app.search.normalizer import normalize_query
from app.search.query_analyzer import analyze_query
from app.search.scoring import (
    DEFAULT_CHANNEL_WEIGHTS,
    DEFAULT_RRF_K,
    apply_business_boosts,
    normalize_scores,
    reciprocal_rank_fusion_from_candidates,
)
from app.search.synonym_expander import expand_synonyms
from app.search.types import (
    CandidateRetrievalResult,
    MatchReason,
    RankedCandidate,
    ScoredResult,
    SearchCandidate,
    SearchChannel,
    SearchResultType,
)
from app.services.embedding_service import EmbeddingProvider

HIGH_SEMANTIC_CONFIDENCE_THRESHOLD = 0.75


@dataclass(frozen=True)
class _RankedSearchOutput:
    retrieval: CandidateRetrievalResult
    candidates_by_result: dict[str, list[SearchCandidate]]
    scored_results: list[ScoredResult]
    results: list[SearchResultRead]


class SearchService:
    """Orchestrates hybrid retrieval, ranking, and response shaping."""

    def __init__(
        self,
        *,
        repository: SearchRepository,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._repository = repository
        self._embedding_provider = embedding_provider

    async def retrieve_candidates(
        self,
        query: str,
        *,
        limit_per_channel: int = DEFAULT_CHANNEL_LIMIT,
    ) -> CandidateRetrievalResult:
        """Retrieve raw candidates grouped by search channel."""
        normalized_query = normalize_query(query)
        analysis = analyze_query(normalized_query)
        expanded_queries = tuple(expand_synonyms(normalized_query))
        query_embedding = (
            await asyncio.to_thread(self._embedding_provider.encode_query, normalized_query)
            if normalized_query
            else []
        )

        candidates_by_channel: dict[SearchChannel, tuple[SearchCandidate, ...]] = {
            SearchChannel.CLIENT_EXACT: await self._repository.client_exact(
                normalized_query,
                limit=limit_per_channel,
            ),
            SearchChannel.CLIENT_TRIGRAM: await self._repository.client_trigram(
                normalized_query,
                limit=limit_per_channel,
            ),
            SearchChannel.CLIENT_FULLTEXT: await self._repository.client_fulltext(
                normalized_query,
                limit=limit_per_channel,
            ),
            SearchChannel.DOCUMENT_VECTOR: await self._repository.document_vector(
                query_embedding,
                limit=limit_per_channel,
            ),
            SearchChannel.DOCUMENT_FULLTEXT: await self._repository.document_fulltext(
                normalized_query,
                limit=limit_per_channel,
            ),
            SearchChannel.DOCUMENT_TITLE_TRIGRAM: await self._repository.document_title_trigram(
                normalized_query,
                limit=limit_per_channel,
            ),
            SearchChannel.DOCUMENT_SYNONYM: await self._repository.document_synonym(
                expanded_queries,
                limit=limit_per_channel,
            ),
        }

        return CandidateRetrievalResult(
            query=normalized_query,
            analysis=analysis,
            expanded_queries=expanded_queries,
            candidates_by_channel=candidates_by_channel,
        )

    async def search(self, query: str, *, result_limit: int) -> list[SearchResultRead]:
        """Run the full hybrid pipeline and return API-ready results."""
        ranked_output = await self._run_ranked_search(query, result_limit=result_limit)
        return ranked_output.results

    async def search_with_explanation(
        self,
        query: str,
        *,
        result_limit: int,
    ) -> SearchExplainResponseRead:
        """Run search and include a reviewer-friendly pipeline explanation."""
        ranked_output = await self._run_ranked_search(query, result_limit=result_limit)
        return SearchExplainResponseRead(
            results=ranked_output.results,
            explanation=_build_explanation(
                original_query=query,
                ranked_output=ranked_output,
            ),
        )

    async def _run_ranked_search(self, query: str, *, result_limit: int) -> _RankedSearchOutput:
        """Run retrieval, fusion, boosts, normalization, and response shaping."""
        normalized_query = normalize_query(query)
        if not normalized_query:
            raise AppError(
                code="empty_search_query",
                message="Search query must not be empty.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        retrieval = await self.retrieve_candidates(normalized_query)
        candidates_by_result = _group_candidates_by_result(retrieval.candidates_by_channel)
        if not candidates_by_result:
            return _RankedSearchOutput(
                retrieval=retrieval,
                candidates_by_result={},
                scored_results=[],
                results=[],
            )

        ranked_candidates = [
            RankedCandidate(
                result_id=_candidate_key(candidate),
                rank=candidate.rank,
                channel=candidate.channel,
            )
            for channel_candidates in retrieval.candidates_by_channel.values()
            for candidate in channel_candidates
        ]
        scored_results = reciprocal_rank_fusion_from_candidates(ranked_candidates)

        for scored_result in scored_results:
            candidates = candidates_by_result[scored_result.result_id]
            apply_business_boosts(
                scored_result,
                _business_boost_reasons(normalized_query, candidates),
            )

        scored_results = sorted(
            normalize_scores(sorted(scored_results, key=_score_sort_key)),
            key=_normalized_score_sort_key,
        )
        limited_results = scored_results[:result_limit]
        results = [
            _build_search_result(
                query=normalized_query,
                scored_result=scored_result,
                candidates=candidates_by_result[scored_result.result_id],
            )
            for scored_result in limited_results
        ]

        return _RankedSearchOutput(
            retrieval=retrieval,
            candidates_by_result=candidates_by_result,
            scored_results=limited_results,
            results=results,
        )


def _group_candidates_by_result(
    candidates_by_channel: Mapping[SearchChannel, tuple[SearchCandidate, ...]],
) -> dict[str, list[SearchCandidate]]:
    grouped: dict[str, list[SearchCandidate]] = {}
    for candidates in candidates_by_channel.values():
        for candidate in candidates:
            grouped.setdefault(_candidate_key(candidate), []).append(candidate)
    return grouped


def _candidate_key(candidate: SearchCandidate) -> str:
    return f"{candidate.result_type.value}:{candidate.id}"


def _business_boost_reasons(
    query: str,
    candidates: list[SearchCandidate],
) -> tuple[MatchReason, ...]:
    reasons: list[MatchReason] = []
    best_candidate = _best_candidate(candidates)

    if best_candidate.result_type == SearchResultType.CLIENT:
        email = str(best_candidate.payload["email"]).lower()
        if query == email:
            reasons.append(MatchReason.EXACT_EMAIL)
        if _matches_email_domain(query=query, email=email):
            reasons.append(MatchReason.EMAIL_DOMAIN)

    if best_candidate.result_type == SearchResultType.DOCUMENT:
        title = str(best_candidate.payload["title"]).lower()
        if query == title:
            reasons.append(MatchReason.EXACT_DOCUMENT_TITLE)
        if any(
            candidate.channel == SearchChannel.DOCUMENT_VECTOR
            and candidate.raw_score >= HIGH_SEMANTIC_CONFIDENCE_THRESHOLD
            for candidate in candidates
        ):
            reasons.append(MatchReason.HIGH_SEMANTIC_CONFIDENCE)

    return tuple(reasons)


def _build_search_result(
    *,
    query: str,
    scored_result: ScoredResult,
    candidates: list[SearchCandidate],
) -> SearchResultRead:
    best_candidate = _best_candidate(candidates)
    matched_fields = _dedupe(
        field for candidate in candidates for field in candidate.matched_fields
    )
    highlights = _dedupe(
        highlight for candidate in candidates for highlight in candidate.highlights
    )
    score = max(0.0, min(1.0, scored_result.normalized_score))

    return SearchResultRead(
        type=best_candidate.result_type.value,
        id=best_candidate.id,
        score=score,
        match_reason=_match_reason(query=query, candidates=candidates),
        matched_fields=matched_fields,
        highlights=highlights,
        client=(
            _client_payload(best_candidate)
            if best_candidate.result_type == SearchResultType.CLIENT
            else None
        ),
        document=(
            _document_payload(best_candidate)
            if best_candidate.result_type == SearchResultType.DOCUMENT
            else None
        ),
    )


def _best_candidate(candidates: list[SearchCandidate]) -> SearchCandidate:
    return sorted(
        candidates,
        key=lambda candidate: (candidate.rank, -candidate.raw_score, candidate.channel.value),
    )[0]


def _client_payload(candidate: SearchCandidate) -> SearchClientPayload:
    payload = candidate.payload
    return SearchClientPayload(
        id=cast(uuid.UUID, payload["id"]),
        first_name=str(payload["first_name"]),
        last_name=str(payload["last_name"]),
        email=str(payload["email"]),
        description=cast(str | None, payload["description"]),
        social_links=cast(list[str] | None, payload["social_links"]),
        created_at=cast(datetime, payload["created_at"]),
        updated_at=cast(datetime, payload["updated_at"]),
    )


def _document_payload(candidate: SearchCandidate) -> SearchDocumentPayload:
    payload = candidate.payload
    return SearchDocumentPayload(
        id=cast(uuid.UUID, payload["id"]),
        client_id=uuid.UUID(str(payload["client_id"])),
        title=str(payload["title"]),
        content=cast(str | None, payload["content"]),
        summary=cast(str | None, payload["summary"]),
        created_at=cast(datetime, payload["created_at"]),
        best_chunk_excerpt=cast(str | None, payload["best_chunk_excerpt"]),
    )


def _match_reason(*, query: str, candidates: list[SearchCandidate]) -> str:
    best_candidate = _best_candidate(candidates)
    channels = {candidate.channel for candidate in candidates}
    matched_fields = {
        field for candidate in candidates for field in candidate.matched_fields
    }

    if best_candidate.result_type == SearchResultType.CLIENT:
        if "email" in matched_fields or _matches_email_domain(
            query=query,
            email=str(best_candidate.payload["email"]).lower(),
        ):
            return "Matched email/domain"
        if {"first_name", "last_name", "full_name"} & matched_fields:
            return "Matched client name"
        return "Matched client profile"

    synonym = _best_synonym_term(candidates, query=query)
    if synonym:
        return f"Synonym match: {query} ≈ {synonym}"
    if SearchChannel.DOCUMENT_TITLE_TRIGRAM in channels:
        return "Matched document title"
    if SearchChannel.DOCUMENT_VECTOR in channels:
        return "Semantic document match"
    if SearchChannel.DOCUMENT_FULLTEXT in channels:
        return "Full-text document match"
    return "Matched document"


def _best_synonym_term(candidates: list[SearchCandidate], *, query: str) -> str | None:
    for candidate in candidates:
        if candidate.channel != SearchChannel.DOCUMENT_SYNONYM:
            continue
        for field in candidate.matched_fields:
            if not field.startswith("synonym:"):
                continue
            term = field.removeprefix("synonym:")
            if term != query:
                return term
    return None


def _matches_email_domain(*, query: str, email: str) -> bool:
    if len(query) < 3 or "@" not in email:
        return False

    domain = email.split("@", maxsplit=1)[1]
    compact_domain = domain.replace(".", "")
    compact_query = query.replace(".", "")
    return compact_query in {domain, compact_domain} or compact_query in compact_domain


def _dedupe(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _build_explanation(
    *,
    original_query: str,
    ranked_output: _RankedSearchOutput,
) -> SearchExplanationRead:
    retrieval = ranked_output.retrieval
    return SearchExplanationRead(
        original_query=original_query,
        normalized_query=retrieval.query,
        query_type=retrieval.analysis.query_type.value,
        tokens=list(retrieval.analysis.tokens),
        expanded_queries=list(retrieval.expanded_queries),
        channels=[
            SearchChannelExplanationRead(
                channel=channel.value,
                candidate_count=len(candidates),
                top_result_ids=[_candidate_key(candidate) for candidate in candidates[:5]],
            )
            for channel, candidates in retrieval.candidates_by_channel.items()
        ],
        results=[
            _build_result_explanation(
                scored_result=scored_result,
                candidates=ranked_output.candidates_by_result[scored_result.result_id],
            )
            for scored_result in ranked_output.scored_results
        ],
    )


def _build_result_explanation(
    *,
    scored_result: ScoredResult,
    candidates: list[SearchCandidate],
) -> SearchResultExplanationRead:
    best_candidate = _best_candidate(candidates)
    return SearchResultExplanationRead(
        result_id=scored_result.result_id,
        result_type=best_candidate.result_type.value,
        channels=[candidate.channel.value for candidate in candidates],
        rrf_contributions={
            candidate.channel.value: _rrf_contribution(candidate)
            for candidate in candidates
        },
        business_boosts=sorted(reason.value for reason in scored_result.match_reasons),
        final_score=scored_result.score,
        normalized_score=scored_result.normalized_score,
    )


def _rrf_contribution(candidate: SearchCandidate) -> float:
    channel_weight = DEFAULT_CHANNEL_WEIGHTS.get(candidate.channel, 1.0)
    return channel_weight / (DEFAULT_RRF_K + candidate.rank)


def _score_sort_key(scored_result: ScoredResult) -> tuple[float, str]:
    return (-scored_result.score, scored_result.result_id)


def _normalized_score_sort_key(scored_result: ScoredResult) -> tuple[float, float, str]:
    return (-scored_result.normalized_score, -scored_result.score, scored_result.result_id)

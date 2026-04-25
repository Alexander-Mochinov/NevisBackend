"""Search scoring helpers."""

from collections.abc import Iterable, Mapping, MutableMapping, Sequence

from app.search.types import MatchReason, RankedCandidate, ScoredResult, SearchChannel

DEFAULT_RRF_K = 60
DEFAULT_CHANNEL_WEIGHTS: dict[SearchChannel, float] = {
    SearchChannel.CLIENT_EXACT: 3.0,
    SearchChannel.CLIENT_TRIGRAM: 1.5,
    SearchChannel.CLIENT_FULLTEXT: 1.2,
    SearchChannel.DOCUMENT_VECTOR: 3.0,
    SearchChannel.DOCUMENT_FULLTEXT: 2.0,
    SearchChannel.DOCUMENT_TITLE_TRIGRAM: 1.3,
    SearchChannel.DOCUMENT_SYNONYM: 1.5,
}

BUSINESS_BOOSTS: dict[MatchReason, float] = {
    MatchReason.EXACT_EMAIL: 0.50,
    MatchReason.EMAIL_DOMAIN: 0.25,
    MatchReason.EXACT_DOCUMENT_TITLE: 0.20,
    MatchReason.HIGH_SEMANTIC_CONFIDENCE: 0.15,
}


def reciprocal_rank_fusion(
    channels: Mapping[SearchChannel, Sequence[str]],
    *,
    k: int = DEFAULT_RRF_K,
    channel_weights: Mapping[SearchChannel, float] = DEFAULT_CHANNEL_WEIGHTS,
) -> list[ScoredResult]:
    """Fuse ranked channel result ids with weighted Reciprocal Rank Fusion."""
    scores: MutableMapping[str, float] = {}

    for channel, result_ids in channels.items():
        channel_weight = channel_weights.get(channel, 1.0)
        for zero_based_rank, result_id in enumerate(result_ids):
            rank = zero_based_rank + 1
            scores[result_id] = scores.get(result_id, 0.0) + channel_weight / (k + rank)

    results = [
        ScoredResult(result_id=result_id, score=score)
        for result_id, score in scores.items()
    ]
    return sorted(results, key=lambda result: (-result.score, result.result_id))


def reciprocal_rank_fusion_from_candidates(
    candidates: Iterable[RankedCandidate],
    *,
    k: int = DEFAULT_RRF_K,
    channel_weights: Mapping[SearchChannel, float] = DEFAULT_CHANNEL_WEIGHTS,
) -> list[ScoredResult]:
    """Fuse explicit ranked candidates with weighted Reciprocal Rank Fusion."""
    scores: MutableMapping[str, float] = {}

    for candidate in candidates:
        channel_weight = channel_weights.get(candidate.channel, 1.0)
        scores[candidate.result_id] = scores.get(candidate.result_id, 0.0) + (
            channel_weight / (k + candidate.rank)
        )

    results = [
        ScoredResult(result_id=result_id, score=score)
        for result_id, score in scores.items()
    ]
    return sorted(results, key=lambda result: (-result.score, result.result_id))


def apply_business_boost(result: ScoredResult, reason: MatchReason) -> ScoredResult:
    """Apply a named business boost to a scored result."""
    result.score += BUSINESS_BOOSTS[reason]
    result.match_reasons.add(reason)
    return result


def apply_business_boosts(
    result: ScoredResult,
    reasons: Iterable[MatchReason],
) -> ScoredResult:
    """Apply multiple named business boosts to a scored result."""
    for reason in reasons:
        apply_business_boost(result, reason)
    return result


def normalize_scores(results: Sequence[ScoredResult]) -> list[ScoredResult]:
    """Normalize result scores to 0..1 within the result set."""
    if not results:
        return []

    min_score = min(result.score for result in results)
    max_score = max(result.score for result in results)

    if max_score == min_score:
        for result in results:
            result.normalized_score = 1.0 if max_score > 0 else 0.0
        return list(results)

    score_range = max_score - min_score
    for result in results:
        result.normalized_score = (result.score - min_score) / score_range

    return list(results)

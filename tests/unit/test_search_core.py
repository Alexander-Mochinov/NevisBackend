"""Search core tests."""

from app.search.normalizer import normalize_query
from app.search.query_analyzer import analyze_query
from app.search.scoring import (
    apply_business_boost,
    normalize_scores,
    reciprocal_rank_fusion,
)
from app.search.synonym_expander import expand_synonyms
from app.search.types import MatchReason, QueryType, ScoredResult, SearchChannel


def test_normalization_trims_and_lowercases() -> None:
    assert (
        normalize_query("  Sample.Client@NevisWealth.TEST  ")
        == "sample.client@neviswealth.test"
    )


def test_normalization_collapses_whitespace() -> None:
    assert normalize_query(" address    proof \n utility\tbill ") == "address proof utility bill"


def test_empty_query_normalizes_to_empty() -> None:
    assert normalize_query(" \n\t ") == ""


def test_neviswealth_is_domain_or_general_like_for_client_search() -> None:
    analysis = analyze_query("NevisWealth")

    assert analysis.query == "neviswealth"
    assert analysis.query_type in {QueryType.DOMAIN_LIKE, QueryType.GENERAL}


def test_address_proof_expands_to_utility_bill() -> None:
    expansions = expand_synonyms("address proof")

    assert "utility bill" in expansions


def test_unknown_query_returns_itself() -> None:
    assert expand_synonyms("portfolio review") == ["portfolio review"]


def test_rrf_ranks_multi_channel_item_above_single_weak_channel_item() -> None:
    results = reciprocal_rank_fusion(
        {
            SearchChannel.CLIENT_TRIGRAM: ["client-a"],
            SearchChannel.CLIENT_FULLTEXT: ["client-a"],
            SearchChannel.DOCUMENT_TITLE_TRIGRAM: ["document-b"],
        }
    )

    assert results[0].result_id == "client-a"


def test_exact_email_boost_increases_score() -> None:
    result = ScoredResult(result_id="client-a", score=0.10)

    apply_business_boost(result, MatchReason.EXACT_EMAIL)

    assert result.score == 0.60
    assert MatchReason.EXACT_EMAIL in result.match_reasons


def test_domain_match_boost_increases_score() -> None:
    result = ScoredResult(result_id="client-a", score=0.10)

    apply_business_boost(result, MatchReason.EMAIL_DOMAIN)

    assert result.score == 0.35
    assert MatchReason.EMAIL_DOMAIN in result.match_reasons


def test_score_normalization_returns_values_between_zero_and_one() -> None:
    results = normalize_scores(
        [
            ScoredResult(result_id="low", score=2.0),
            ScoredResult(result_id="high", score=4.0),
        ]
    )

    assert [result.normalized_score for result in results] == [0.0, 1.0]


def test_equal_scores_do_not_crash_normalization() -> None:
    results = normalize_scores(
        [
            ScoredResult(result_id="a", score=2.0),
            ScoredResult(result_id="b", score=2.0),
        ]
    )

    assert [result.normalized_score for result in results] == [1.0, 1.0]


def test_empty_result_list_normalization_returns_empty_list() -> None:
    assert normalize_scores([]) == []

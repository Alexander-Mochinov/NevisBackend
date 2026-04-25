"""Summary service tests."""

from app.services.summary_service import SummaryService


def test_summary_short_text_returns_first_sentence() -> None:
    service = SummaryService()

    summary = service.summarize(
        "The client uploaded a recent utility bill. It verifies the current address."
    )

    assert summary == "The client uploaded a recent utility bill."


def test_summary_long_text_returns_first_meaningful_sentences() -> None:
    service = SummaryService(short_content_limit=60, max_sentences=2)

    summary = service.summarize(
        "The client uploaded a utility bill as proof of residence. "
        "The document is dated within the last three months. "
        "The advisor accepted it for onboarding."
    )

    assert summary == (
        "The client uploaded a utility bill as proof of residence. "
        "The document is dated within the last three months."
    )


def test_summary_empty_text_returns_none() -> None:
    service = SummaryService()

    assert service.summarize("   ") is None

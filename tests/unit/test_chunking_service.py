"""Chunking service tests."""

from app.services.chunking_service import ChunkingService


def test_chunking_short_text_returns_one_chunk() -> None:
    service = ChunkingService(chunk_size=900, overlap_size=125)

    chunks = service.chunk_text("The client uploaded a utility bill.")

    assert chunks == ["The client uploaded a utility bill."]


def test_chunking_long_text_returns_multiple_chunks() -> None:
    service = ChunkingService(chunk_size=140, overlap_size=30)
    text = " ".join(
        [
            "The client uploaded a utility bill as proof of address.",
            "The document confirms the residence for onboarding.",
            "The advisor reviewed the file for KYC compliance.",
            "The operations team marked the document as current.",
        ]
    )

    chunks = service.chunk_text(text)

    assert len(chunks) > 1


def test_chunking_overlap_works() -> None:
    service = ChunkingService(chunk_size=140, overlap_size=40)
    text = " ".join(
        [
            "Sentence one contains introductory client context.",
            "Sentence two contains address verification details.",
            "Sentence three contains onboarding and KYC review details.",
            "Sentence four contains final advisor notes.",
        ]
    )

    chunks = service.chunk_text(text)

    assert len(chunks) > 1
    assert "address verification details." in chunks[1]

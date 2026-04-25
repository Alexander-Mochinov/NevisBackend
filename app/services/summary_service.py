"""Deterministic local extractive summaries."""

import re


class SummaryService:
    """Generate short extractive summaries without network calls."""

    def __init__(self, *, short_content_limit: int = 240, max_sentences: int = 3) -> None:
        self._short_content_limit = short_content_limit
        self._max_sentences = max_sentences

    def summarize(self, content: str) -> str | None:
        normalized_content = self._normalize_whitespace(content)
        if not normalized_content:
            return None

        sentences = self._split_sentences(normalized_content)
        if not sentences:
            return normalized_content

        if len(normalized_content) <= self._short_content_limit:
            return sentences[0]

        meaningful_sentences = [sentence for sentence in sentences if len(sentence.split()) >= 3]
        selected_sentences = meaningful_sentences[: self._max_sentences] or sentences[:1]
        return " ".join(selected_sentences)

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        sentences = re.findall(r"[^.!?]+(?:[.!?]+|$)", text)
        return [sentence.strip() for sentence in sentences if sentence.strip()]

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        return " ".join(text.split())

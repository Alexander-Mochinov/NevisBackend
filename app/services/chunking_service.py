"""Deterministic document chunking."""

import re


class ChunkingService:
    """Split document content into overlapping chunks."""

    def __init__(self, *, chunk_size: int = 900, overlap_size: int = 125) -> None:
        if chunk_size <= overlap_size:
            raise ValueError("chunk_size must be greater than overlap_size")
        self._chunk_size = chunk_size
        self._overlap_size = overlap_size

    def chunk_text(self, content: str) -> list[str]:
        normalized_content = self._normalize_whitespace(content)
        if not normalized_content:
            return []
        if len(normalized_content) <= self._chunk_size:
            return [normalized_content]

        chunks: list[str] = []
        current_chunk = ""

        for sentence in self._split_sentences(normalized_content):
            if not current_chunk:
                current_chunk = sentence
                continue

            candidate = f"{current_chunk} {sentence}"
            if len(candidate) <= self._chunk_size:
                current_chunk = candidate
                continue

            chunks.append(current_chunk)
            current_chunk = f"{self._overlap_tail(current_chunk)} {sentence}".strip()

        if current_chunk:
            chunks.append(current_chunk)

        return self._split_oversized_chunks(chunks)

    def _split_oversized_chunks(self, chunks: list[str]) -> list[str]:
        split_chunks: list[str] = []
        for chunk in chunks:
            if len(chunk) <= self._chunk_size + self._overlap_size:
                split_chunks.append(chunk)
                continue
            split_chunks.extend(self._split_by_size(chunk))
        return split_chunks

    def _split_by_size(self, text: str) -> list[str]:
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self._chunk_size, len(text))
            chunks.append(text[start:end].strip())
            if end == len(text):
                break
            start = max(0, end - self._overlap_size)
        return [chunk for chunk in chunks if chunk]

    def _overlap_tail(self, text: str) -> str:
        if len(text) <= self._overlap_size:
            return text

        tail = text[-self._overlap_size :]
        first_space = tail.find(" ")
        if first_space > 0:
            tail = tail[first_space + 1 :]
        return tail.strip()

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        sentences = re.findall(r"[^.!?]+(?:[.!?]+|$)", text)
        return [sentence.strip() for sentence in sentences if sentence.strip()]

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        return " ".join(text.split())

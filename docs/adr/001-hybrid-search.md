# ADR 001: Hybrid Search With PostgreSQL, pgvector, and RRF

## Status

Accepted.

## Context

The task needs a small WealthTech search API that can find clients by profile fields and documents by both exact wording and similar KYC language.

The important examples are:

- `NevisWealth` should find `sample.client@neviswealth.test`.
- `address proof` should find a document containing `utility bill`.
- `utlity bil` should still find `Utility Bill`.

A single retrieval method is not enough for these cases. Exact matching is predictable for emails, full-text search is good for lexical document queries, trigram search handles typos, synonyms bridge advisor/KYC wording, and embeddings help with semantic document search.

## Decision

Use a hybrid search pipeline:

1. Normalize the query.
2. Analyze the query type.
3. Expand local KYC/WealthTech synonyms.
4. Generate a local query embedding.
5. Retrieve candidates from separate client and document channels.
6. Merge channel rankings with weighted Reciprocal Rank Fusion.
7. Apply explicit business boosts.
8. Normalize final scores to `0..1`.
9. Return result explanations: match reason, matched fields, highlights, and result type.

Use PostgreSQL as the only database:

- `pg_trgm` for fuzzy client and title matching.
- PostgreSQL full-text search for lexical matching.
- `pgvector` for document chunk embeddings.

Use `sentence-transformers/all-MiniLM-L6-v2` as the production local embedding model. Its output dimension is `384`, which matches the `document_chunks.embedding vector(384)` column.

Use deterministic fake embeddings in tests. This keeps tests fast, stable, and network-free while preserving the same application flow.

## Consequences

Positive:

- The project is reproducible with Docker Compose and does not need a separate vector database.
- Search behavior is explainable because each channel is visible and independently tested.
- RRF avoids comparing incompatible raw score scales directly.
- Tests do not require external APIs, API keys, or model downloads.

Tradeoffs:

- Changing to an embedding model with a different dimension requires a database migration and re-embedding existing chunks.
- PostgreSQL search is enough for this task, but a larger production system might split lexical and vector search into dedicated infrastructure.
- Local sentence-transformer inference can be CPU-heavy; production workloads should offload large embedding jobs outside request handling.

## Alternatives Considered

Use only full-text search:

- Rejected because it would not reliably handle `address proof -> utility bill` or semantic document matches.

Use only vector search:

- Rejected because email/domain/name lookup should be exact and predictable, not approximate.

Use a separate vector database:

- Rejected for this home task because it adds operational complexity without improving the core evaluation criteria.

Use a paid external embedding or LLM API:

- Rejected because the project should run locally and should not require paid external services.

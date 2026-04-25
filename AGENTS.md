# Nevis Backend Home Task Implementation Rules

## Project Goal

Build a simplified WealthTech Search API for advisors.

The API must support:
- Creating clients.
- Creating documents for clients.
- Searching clients by email, name, and description.
- Searching documents semantically, so queries such as `address proof` can match document content such as `utility bill`.
- Optional quick document summaries.
- Swagger/OpenAPI documentation through FastAPI.
- Docker-reproducible local development, migrations, and tests.

This is a home task, so favor clear, testable implementation over premature infrastructure complexity.

## Architecture Rules

Use a clean layered architecture. Keep responsibilities separated by package:

```text
app/
  main.py
  api/
    routes/
    dependencies.py
  core/
    config.py
    errors.py
    logging.py
  db/
    session.py
    base.py
  models/
  schemas/
  repositories/
  services/
  search/
  tests/
    unit/
    integration/
```

Layer rules:
- `api/routes/` owns HTTP routing, request parsing, response models, and status codes.
- `api/dependencies.py` owns FastAPI dependency wiring only.
- `schemas/` contains Pydantic v2 request and response schemas. Do not expose SQLAlchemy models from API responses.
- `models/` contains SQLAlchemy 2.x ORM models only.
- `repositories/` owns database queries and persistence. Do not place HTTP or business orchestration logic here.
- `services/` owns use-case orchestration and business rules.
- `search/` owns query normalization, analysis, synonym expansion, candidate retrieval coordination, scoring, ranking, highlighting, and match reasons.
- `db/` owns async engine/session configuration, metadata base, and migration integration.
- `core/` owns configuration, logging setup, shared error types, and application-level constants.

Dependency direction:
- Routes may depend on schemas, services, and dependencies.
- Services may depend on repositories, search components, schemas or DTOs, and core errors.
- Repositories may depend on models and database session primitives.
- Search components may depend on repositories for candidate retrieval, but ranking logic must remain testable without FastAPI.
- Lower layers must not import from `api/routes/`.

Database rules:
- Use SQLAlchemy 2.x async APIs and `asyncpg`.
- Use Alembic for schema changes.
- Use PostgreSQL as the only application database.
- Use `pgvector` for document embeddings.
- Use PostgreSQL full-text search for lexical search.
- Use PostgreSQL `pg_trgm` for fuzzy and substring-like matching.
- Database-specific search SQL belongs in repositories or dedicated search query modules, not in route handlers.

Embedding rules:
- Use `sentence-transformers` for local embeddings.
- Do not introduce external paid APIs as required dependencies.
- Keep embedding model choice configurable.
- Make embedding generation injectable so tests can use deterministic fake embeddings.

Docker reproducibility:
- Local development must be reproducible with Docker.
- PostgreSQL must be started with required extensions available: `vector`, `pg_trgm`, and full-text search support.
- README setup commands must work from a clean checkout.
- Avoid undocumented host-machine prerequisites beyond Docker and Python tooling explicitly listed in README.

## Coding Conventions

Python:
- Use Python type hints throughout application code.
- Prefer small, explicit functions over broad utility abstractions.
- Use async all the way through FastAPI routes, services, repositories, and database access.
- Do not block the event loop with embedding generation in request handlers without an explicit offloading strategy.
- Keep public service and repository methods narrow and named by use case.
- Use clear domain names such as `Client`, `Document`, `DocumentChunk`, `SearchResult`, and `MatchReason`.

Pydantic v2:
- Use `BaseModel`, `ConfigDict`, and v2 validators/serializers where needed.
- Keep API schemas separate from ORM models.
- Validate external input at schema boundaries.

SQLAlchemy:
- Use typed declarative models.
- Use explicit relationships and indexes.
- Keep migrations consistent with models.
- Do not rely on implicit database state not represented by migrations.

Errors:
- Define domain/application errors in `core/errors.py`.
- Map errors to HTTP responses in API-level exception handlers.
- Do not raise raw database exceptions from services to routes.

Configuration:
- Use environment-driven settings in `core/config.py`.
- Never hardcode database URLs, embedding model names, or test database names in application code.

Logging:
- Configure structured, concise application logging in `core/logging.py`.
- Do not log sensitive client data or full document contents.

## Testing Requirements

Every implementation step must include tests unless the step only changes documentation or project metadata.

Required test coverage:
- Unit tests for query normalization, query analysis, synonym expansion, rank fusion, score normalization, highlights, and match reasons.
- Unit tests for service-layer validation and edge cases.
- Integration tests for create client, create document, client search, document search, and combined search behavior.
- Repository/search integration tests that verify PostgreSQL full-text search, `pg_trgm`, and `pgvector` behavior.
- Edge cases for empty queries, whitespace-only queries, duplicate emails, missing clients, documents with no useful content, fuzzy misspellings, and synonym matches such as `address proof` matching `utility bill`.

Testing conventions:
- Use `pytest`, `pytest-asyncio`, and `httpx`.
- Use deterministic fake embeddings in unit tests.
- Integration tests may use the Docker PostgreSQL service or a dedicated test database.
- Tests must not require external paid APIs or network calls.
- Prefer asserting behavior and response shape over implementation details.

## Commands To Run After Changes

When application code exists, run the relevant subset locally before handing off:

```bash
pytest
```

For database or integration changes, also run migrations against the local Docker database:

```bash
alembic upgrade head
pytest app/tests/integration
```

When formatting/linting tools are added, document and run them here. Do not invent commands that are not configured in the repository.

For documentation-only changes, tests are not required.

## Search Algorithm Requirements

The final implementation must use a hybrid search pipeline with these stages:

1. Query normalization.
2. Query analysis.
3. KYC/WealthTech synonym expansion.
4. Client candidate retrieval:
   - Exact and substring matching.
   - Trigram fuzzy matching.
   - Full-text search.
5. Document candidate retrieval:
   - Vector semantic search over chunks.
   - Full-text search.
   - Title trigram search.
   - Synonym-expanded search.
6. Reciprocal Rank Fusion.
7. Business boosts.
8. Final score normalization.
9. Search response including:
   - Result type.
   - Match reasons.
   - Matched fields.
   - Highlights.
   - Final normalized score.

Search implementation rules:
- Keep normalization, analysis, synonym expansion, fusion, boosting, and final score normalization independently unit-testable.
- Candidate retrieval should return enough metadata to explain why a result matched.
- Do not collapse all search behavior into one SQL statement if it makes ranking, explanations, or testing opaque.
- Business boosts must be explicit and documented in code, for example exact email match outranking fuzzy name match.
- Final scores must be normalized to a predictable response range.
- Highlights must be generated from matched fields or content snippets, not fabricated.
- Document semantic search must operate over chunks rather than only whole documents.
- Synonyms must be domain-specific and local, covering KYC and WealthTech terms such as address proof, proof of identity, utility bill, passport, bank statement, suitability, risk profile, portfolio, and onboarding.

## Implementation Guardrails

- Do not implement app code before the architecture skeleton is agreed.
- Do not introduce external paid APIs as required dependencies.
- Keep local development reproducible through Docker.
- Keep API behavior documented through Swagger/OpenAPI and README examples.
- Keep migrations, models, and tests aligned in the same implementation step.
- Do not bypass the service layer from routes for non-trivial behavior.
- Do not bypass repositories from services for persistence or search queries.
- Do not store secrets in the repository.
- Do not add broad frameworks or background systems unless required by the task.
- Prefer explicit, maintainable code over clever abstractions.

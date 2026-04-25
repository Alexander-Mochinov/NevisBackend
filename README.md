# Nevis Backend Home Task

A small WealthTech search API for advisors. It lets an advisor create clients, attach documents to those clients, and search across both profiles and documents using a mix of exact, fuzzy, full-text, synonym, and vector search.

The two task examples are supported directly:

- Searching `NevisWealth` returns the demo client `sample.client@neviswealth.test`.
- Searching `address proof` returns a document that contains `utility bill`.

The project is intentionally self-contained. It uses PostgreSQL with `pgvector`, local `sentence-transformers` support, deterministic fake embeddings for tests, and no paid external LLM/API dependency.

## Quick Review Path

If you are reviewing the task, this is the shortest path from a clean checkout to a working API:

```bash
cp .env.example .env
docker compose up -d --build
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m pytest
```

Seed the demo data through the public API:

```bash
make demo-seed
```

Then try the required searches:

```bash
curl 'http://localhost:8000/search?q=NevisWealth'
curl 'http://localhost:8000/search?q=address%20proof'
curl 'http://localhost:8000/search?q=utlity%20bil'
```

To inspect why a result matched, enable the explanation mode:

```bash
curl 'http://localhost:8000/search?q=address%20proof&explain=true'
```

Expected behavior:

| Query | Expected match | Why it matches |
| --- | --- | --- |
| `NevisWealth` | `sample.client@neviswealth.test` | email/domain matching |
| `address proof` | `Utility Bill` | KYC synonym expansion and document retrieval |
| `utlity bil` | `Utility Bill` | title trigram fuzzy matching |
| `wealth management` | sample client | client description search |

## Stack

- Python 3.12
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x async with `asyncpg`
- Alembic
- PostgreSQL
- `pgvector`
- PostgreSQL full-text search
- PostgreSQL `pg_trgm`
- `sentence-transformers`
- pytest, pytest-asyncio, httpx
- Ruff and mypy

## Project Layout

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
alembic/
```

The app follows a simple layered structure:

- Routes handle HTTP only: request parsing, response schemas, and status codes.
- Services hold use-case logic and validation flow.
- Repositories own database reads and writes.
- Search modules contain normalization, query analysis, synonym expansion, ranking, and scoring.
- Schemas are separate from SQLAlchemy models, so ORM objects are not exposed directly as API contracts.

## Search

`GET /search?q=...` runs a hybrid pipeline:

1. Normalize the query by trimming, lowercasing, and collapsing whitespace.
2. Analyze whether the query looks like an email, domain, person name, document query, or general query.
3. Expand known KYC/WealthTech synonyms, for example `address proof -> utility bill`.
4. Generate a query embedding with the configured embedding provider.
5. Retrieve candidates from independent channels.
6. Merge candidates with Reciprocal Rank Fusion.
7. Apply explicit business boosts.
8. Normalize final scores to `0..1`.
9. Return mixed client/document results with match reasons, matched fields, highlights, and payload data.

Client retrieval channels:

- exact and substring matching across email, first name, last name, and full name
- trigram similarity across email, names, and description
- PostgreSQL full-text search across profile fields

Document retrieval channels:

- vector search over document chunks
- PostgreSQL full-text search over documents and chunks
- title trigram search for typos such as `utlity bil`
- synonym-expanded lexical search for KYC terms

RRF is used because every channel has a different raw score scale. It keeps the ranking explainable without pretending that vector distance, trigram similarity, and full-text rank are directly comparable.

For the design rationale, see `docs/adr/001-hybrid-search.md`.

## Embeddings

The default embedding model is:

```text
sentence-transformers/all-MiniLM-L6-v2
```

That model returns 384-dimensional vectors, and the database column is `vector(384)`. This is intentional. Changing to a model with a different dimension requires a database migration and re-embedding existing chunks.

For local tests and Docker test runs, the default provider is `fake`. It is deterministic, fast, does not load ML models, and does not touch the network. To use the real local model, set:

```bash
EMBEDDING_PROVIDER=sentence_transformers
```

## Setup

Create a local environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
cp .env.example .env
```

Start PostgreSQL, run migrations, then run the API:

```bash
docker compose up -d postgres
alembic upgrade head
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://localhost:8000
```

Swagger UI:

```text
http://localhost:8000/docs
```

OpenAPI JSON:

```text
http://localhost:8000/openapi.json
```

## Docker Compose

Build and start everything:

```bash
docker compose up -d --build
```

Start only the API after the image exists:

```bash
docker compose up -d api
```

If port `8000` is already in use:

```bash
API_PORT=8001 docker compose up -d api
```

If port `5432` is already in use:

```bash
POSTGRES_PORT=55432 docker compose up -d postgres
```

Stop services:

```bash
docker compose down
```

Remove the database volume as well:

```bash
docker compose down -v
```

Useful Make targets:

```bash
make compose-up
make migrate
make docker-test
make demo-seed
make compose-down
```

## Migrations

Run migrations locally:

```bash
alembic upgrade head
```

Run migrations inside Docker Compose:

```bash
docker compose run --rm api alembic upgrade head
```

The migrations enable:

- `vector`
- `pg_trgm`

They also create:

- `clients`
- `documents`
- `document_chunks`
- full-text indexes
- trigram indexes
- vector index on chunk embeddings

## Tests

Run the local test suite:

```bash
python -m pytest
```

Run lint and type checks:

```bash
python -m ruff check .
python -m mypy app
```

Or run all local checks:

```bash
make check
```

Database integration tests are gated by `RUN_DB_TESTS=1` and `DATABASE_URL`. Docker Compose sets these for the API container:

```bash
docker compose run --rm api python -m pytest
```

Equivalent Make target:

```bash
make docker-test
```

The tests cover:

- client creation, email normalization, duplicate email handling, and validation errors
- document creation, missing clients, chunk creation, summaries, and stored embeddings
- query normalization, synonym expansion, RRF, boosts, and score normalization
- PostgreSQL-backed client and document retrieval channels
- public `/search` behavior for `NevisWealth`, `address proof`, and `utlity bil`

The repository also includes a GitHub Actions workflow in `.github/workflows/ci.yml` that runs migrations, tests, Ruff, and mypy against PostgreSQL with `pgvector`.

## API Examples

Create a client:

```bash
curl -X POST http://localhost:8000/clients \
  -H 'Content-Type: application/json' \
  -d '{
    "first_name": "Sample",
    "last_name": "Client",
    "email": "sample.client@neviswealth.test",
    "description": "Wealth management client",
    "social_links": ["https://example.test/profiles/sample-client"]
  }'
```

Create a document:

```bash
curl -X POST http://localhost:8000/clients/{CLIENT_ID}/documents \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Utility Bill",
    "content": "The client uploaded a recent utility bill as proof of residence and address verification."
  }'
```

Search for a client by email domain:

```bash
curl 'http://localhost:8000/search?q=NevisWealth'
```

Search for a document using KYC language:

```bash
curl 'http://localhost:8000/search?q=address%20proof'
```

Search with a typo:

```bash
curl 'http://localhost:8000/search?q=utlity%20bil'
```

Empty search queries return `400`:

```bash
curl 'http://localhost:8000/search?q=%20%20%20'
```

Explain why a result matched:

```bash
curl 'http://localhost:8000/search?q=address%20proof&explain=true'
```

## Example Responses

Client search result:

```json
[
  {
    "type": "client",
    "id": "6b8ed0b3-6635-4901-9cb2-ec65893f51f1",
    "score": 1.0,
    "match_reason": "Matched email/domain",
    "matched_fields": ["email"],
    "highlights": ["sample.client@neviswealth.test"],
    "client": {
      "id": "6b8ed0b3-6635-4901-9cb2-ec65893f51f1",
      "first_name": "Sample",
      "last_name": "Client",
      "email": "sample.client@neviswealth.test",
      "description": "Wealth management client",
      "social_links": ["https://example.test/profiles/sample-client"],
      "created_at": "2026-04-25T10:00:00Z",
      "updated_at": "2026-04-25T10:00:00Z"
    },
    "document": null
  }
]
```

Document search result:

```json
[
  {
    "type": "document",
    "id": "85a2202e-a0ae-4087-b73d-250dc04b812f",
    "score": 1.0,
    "match_reason": "Synonym match: address proof ≈ utility bill",
    "matched_fields": ["chunk.content", "synonym:utility bill"],
    "highlights": [
      "The client uploaded a recent utility bill as proof of residence and address verification."
    ],
    "client": null,
    "document": {
      "id": "85a2202e-a0ae-4087-b73d-250dc04b812f",
      "client_id": "6b8ed0b3-6635-4901-9cb2-ec65893f51f1",
      "title": "Utility Bill",
      "content": "The client uploaded a recent utility bill as proof of residence and address verification.",
      "summary": "The client uploaded a recent utility bill as proof of residence and address verification.",
      "created_at": "2026-04-25T10:01:00Z",
      "best_chunk_excerpt": "The client uploaded a recent utility bill as proof of residence and address verification."
    }
  }
]
```

## Status Codes

- `POST /clients` returns `201` for a valid client.
- Duplicate client email returns `409`.
- Invalid client payloads return `422`.
- `POST /clients/{id}/documents` returns `201` for a valid document.
- Creating a document for an unknown client returns `404`.
- `GET /search?q=...` returns `200` for a valid query.
- Empty or whitespace-only search returns `400`.

## Tradeoffs

- PostgreSQL with `pgvector` keeps the project easy to run locally. A separate vector database would be unnecessary for this scope.
- Local `sentence-transformers` avoids mandatory API keys and paid services.
- Fake embeddings make tests deterministic and fast.
- The embedding dimension is fixed to `384` because it matches `all-MiniLM-L6-v2` and the `vector(384)` schema.
- The summary is extractive and local. It is less polished than an LLM summary, but it is predictable and reproducible.
- Search ranking is split into visible stages instead of one large SQL query, so behavior is easier to test and explain.

## Future Work

- Add pagination and filters to `/search`.
- Add update/delete endpoints for clients and documents.
- Move heavy production embedding work to a background/offloaded path.
- Add tenant/advisor-level authorization.
- Add a relevance benchmark dataset for search tuning.
- Add configurable synonym dictionaries.

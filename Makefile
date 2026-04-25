PYTHON ?= python

.PHONY: run test lint typecheck check migrate compose-up compose-down compose-down-v docker-test demo-seed

run:
	uvicorn app.main:app --reload

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy app

check: test lint typecheck

migrate:
	alembic upgrade head

compose-up:
	docker compose up -d --build

compose-down:
	docker compose down

compose-down-v:
	docker compose down -v

docker-test:
	docker compose up -d postgres
	docker compose run --rm api alembic upgrade head
	docker compose run --rm api python -m pytest

demo-seed:
	$(PYTHON) scripts/seed_demo.py

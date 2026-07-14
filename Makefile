SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help setup dev test lint format benchmark-stt codex-worker smoke-test down migrate
help:
	@printf '%s\n' 'make setup | dev | test | lint | format | benchmark-stt | codex-worker | smoke-test | migrate | down'
setup:
	./scripts/bootstrap.sh
dev:
	./scripts/dev.sh
test:
	PYTHONPATH=backend:.python-packages python3 -m pytest backend/tests -q
	PYTHONPATH=backend:.python-packages python3 backend/tests/integration_check.py
	cd frontend && npm test
lint:
	PYTHONPATH=backend:.python-packages python3 -m ruff check backend
	PYTHONPATH=backend:.python-packages python3 -m mypy backend/app
	cd frontend && npm run build
format:
	PYTHONPATH=backend:.python-packages python3 -m ruff format backend
	cd frontend && npx prettier --write src
benchmark-stt:
	PYTHONPATH=backend:.python-packages python3 scripts/benchmark_stt.py
codex-worker:
	./scripts/run_codex_worker.sh
smoke-test:
	./scripts/smoke_test.sh
migrate:
	cd backend && PYTHONPATH=.:../.python-packages python3 -m alembic upgrade head
down:
	-docker compose down
	-pkill -f 'uvicorn app.main:app' || true
	-pkill -f 'vite --host 127.0.0.1' || true

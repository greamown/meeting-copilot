SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help setup dev dev-sqlite dev-tts test test-e2e lint format benchmark-stt codex-worker codex-login smoke-test down migrate
help:
	@printf '%s\n' 'make setup | dev | dev-sqlite | dev-tts | codex-login | test | lint | benchmark-stt | smoke-test | migrate | down'
setup:
	./scripts/bootstrap.sh
dev:
	./scripts/dev.sh
dev-sqlite:
	COMPOSE_FILE=docker-compose.yml:docker-compose.sqlite.yml ./scripts/docker_up.sh
dev-tts:
	./scripts/docker_up.sh
test:
	docker compose build backend
	docker compose run --rm --no-deps -e MC_DATABASE_URL=sqlite+aiosqlite:////tmp/tests.db -e MC_CODEX_WORKER_URL= -e MC_STT_WORKER_URL= backend python -m pytest -p no:cacheprovider backend/tests -q
	docker compose run --rm --no-deps -e MC_DATABASE_URL=sqlite+aiosqlite:////tmp/tests.db -e MC_CODEX_WORKER_URL= -e MC_STT_WORKER_URL= backend python backend/tests/integration_check.py
	docker build --target test -f frontend/Dockerfile .
	docker compose build frontend
test-e2e:
	docker compose --profile test build e2e
	docker compose --profile test run --rm e2e
lint:
	docker compose build backend
	docker compose run --rm --no-deps backend ruff check --no-cache backend
	docker compose run --rm --no-deps backend sh -c 'cd backend && mypy --cache-dir=/tmp/mypy app'
	docker compose build frontend
format:
	docker compose run --rm --no-deps backend ruff format backend
benchmark-stt:
	@mkdir -p runtime
	docker compose exec -T stt-worker python /app/scripts/benchmark_stt.py $(STT_BENCHMARK_ARGS) | tee runtime/stt-benchmark.json
codex-worker:
	./scripts/run_codex_worker.sh
codex-login:
	docker compose exec codex-worker codex login --device-auth
smoke-test:
	./scripts/smoke_test.sh
migrate:
	docker compose run --rm --no-deps backend /app/scripts/container_migrate.sh
down:
	docker compose down

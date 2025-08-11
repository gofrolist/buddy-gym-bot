SHELL := /usr/bin/env bash
export PYTHONUNBUFFERED=1

.PHONY: help
help:
	@echo "Targets:"
	@echo "  tools          - Install dev tools via uv tool (ruff, pyright, pre-commit, pytest)"
	@echo "  sync           - Install project deps with uv"
	@echo "  run            - Start bot locally (polling)"
	@echo "  test           - Run tests"
	@echo "  lint           - Ruff lint"
	@echo "  fmt            - Ruff format"
	@echo "  typecheck      - Pyright type checking"
	@echo "  precommit      - Run pre-commit on all files"
	@echo "  migrate        - Apply DB migration (requires DATABASE_URL)"
	@echo "  build          - Build Docker image"
	@echo "  deploy         - Deploy to Fly using GHCR image (requires FLY_API_TOKEN)"

.PHONY: tools
tools:
	uv tool install ruff pyright pre-commit pytest

.PHONY: sync
sync:
	uv sync

.PHONY: run
run:
	uv run python -m app.main

.PHONY: test
test:
	pytest -q

.PHONY: lint
lint:
	ruff check .

.PHONY: fmt
fmt:
	ruff format .

.PHONY: typecheck
typecheck:
	pyright

.PHONY: precommit
precommit:
	pre-commit run --all-files

.PHONY: migrate
migrate:
	uv run psycopg -c "$$(cat migrations/001_init.sql)" "$$DATABASE_URL"

IMAGE ?= ghcr.io/${USER}/gym-buddy-bot:dev

.PHONY: build
build:
	docker build -t $(IMAGE) .

.PHONY: deploy
deploy:
	flyctl deploy --image $(IMAGE) --remote-only
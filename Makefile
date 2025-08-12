SHELL := /usr/bin/env bash
export PYTHONUNBUFFERED=1

.PHONY: help
help:
	@echo "Targets:"
	@echo "  sync           - Install project deps with uv"
	@echo "  run            - Start bot locally (polling)"
	@echo "  test           - Run tests"
	@echo "  precommit      - Run pre-commit on all files"
	@echo "  build          - Build Docker image"
	@echo "  deploy         - Deploy to Fly using GHCR image (requires FLY_API_TOKEN)"
	@echo "  deploy-infra   - Setup and deploy Postgres and Redis"

.PHONY: sync
sync:
	uv sync --all-extras

.PHONY: run
run:
	uv run python -m buddy_gym_bot.main

.PHONY: test
test:
	uv run pytest

.PHONY: precommit
precommit:
	uv run pre-commit autoupdate
	uv run pre-commit run --all-files

IMAGE ?= ghcr.io/${USER}/buddy-gym-bot:dev
REGION ?= lax

.PHONY: build
build:
	docker build --platform linux/arm64 -t $(IMAGE) .

.PHONY: deploy
deploy:
	flyctl deploy --image $(IMAGE) --remote-only

.PHONY: deploy-infra
deploy-infra:
	flyctl volumes create pg_data --region $(REGION) --size 3 --yes || true
	flyctl launch --name buddy-gym-postgres --config infra/postgres/fly.toml
	flyctl deploy -c infra/postgres/fly.toml --remote-only
	flyctl volumes create redis_data --region $(REGION) --size 1 --yes || true
	flyctl deploy -c infra/redis/fly.toml --remote-only

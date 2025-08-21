SHELL := /usr/bin/env bash
export PYTHONUNBUFFERED=1

.PHONY: help
help:
	@echo "Targets:"
	@echo "  sync           - Install project deps with uv"
	@echo "  webapp-build   - Build webapp and copy to static directory"
	@echo "  run            - Start bot locally (polling)"
	@echo "  server         - Start FastAPI server with webapp"
	@echo "  test           - Run tests"
	@echo "  precommit      - Run pre-commit on all files"
	@echo "  build          - Build Docker image"
	@echo "  deploy         - Deploy to Fly using GHCR image (requires FLY_API_TOKEN)"
	@echo "  deploy-infra   - Setup and deploy Postgres and Redis"
	@echo "  update-exercises - Clone ExerciseDB repo and copy all data + GIFs"
	@echo "  upload-to-openai - Upload ExerciseDB data to OpenAI and update .env file"
	@echo "  set-fly-secret - Set OpenAI file_id as Fly.io secret (requires flyctl)"
	@echo "  update-all     - Update ExerciseDB data and upload to OpenAI"
	@echo "  deploy-openai  - Update ExerciseDB data, upload to OpenAI, and set Fly.io secret"

.PHONY: sync
sync:
	uv sync --all-extras

.PHONY: webapp-build
webapp-build:
	cd webapp && npm run build
	mkdir -p static/webapp
	cp -r webapp/dist/* static/webapp/

.PHONY: run
run:
	uv run python -m buddy_gym_bot.main

.PHONY: server
server:
	uv run uvicorn buddy_gym_bot.server.main:app --host 0.0.0.0 --port 8000 --reload

.PHONY: test
test:
	uv run pytest

.PHONY: precommit
precommit:
	uv run pre-commit autoupdate
	uv run pre-commit install-hooks
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

.PHONY: update-exercises
update-exercises:
	uv run python scripts/download_exercisedb.py

.PHONY: upload-to-openai
upload-to-openai:
	uv run python scripts/simple_openai_upload.py

.PHONY: set-fly-secret
set-fly-secret:
	@if [ -z "$(shell grep '^OPENAI_FILE_ID=' .env | tail -1 | cut -d'=' -f2)" ]; then \
		echo "❌ No OPENAI_FILE_ID found in .env file. Run 'make upload-to-openai' first."; \
		exit 1; \
	fi
	@echo "🔐 Setting OpenAI file_id as Fly.io secret..."
	@flyctl secrets set OPENAI_FILE_ID=$$(grep '^OPENAI_FILE_ID=' .env | tail -1 | cut -d'=' -f2)
	@echo "✅ Fly.io secret updated successfully!"

.PHONY: update-all
update-all: update-exercises upload-to-openai
	@echo "✅ Updated ExerciseDB data and uploaded to OpenAI"

.PHONY: deploy-openai
deploy-openai: update-exercises upload-to-openai set-fly-secret
	@echo "🚀 Complete OpenAI deployment completed!"
	@echo "   • ExerciseDB data updated"
	@echo "   • File uploaded to OpenAI"
	@echo "   • Fly.io secret updated"

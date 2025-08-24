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
	@echo "  update-exercises - Clone ExerciseDB repo and copy all data + GIFs"
	@echo "  upload-minified - Minify and upload ExerciseDB data to OpenAI"
	@echo "  set-fly-secret - Set OPENAI_VECTOR_STORE_ID as Fly.io secret"
	@echo "  set-openai-file-id - Set OPENAI_FILE_ID as Fly.io secret"
	@echo "  set-all-openai-secrets - Set all OpenAI secrets in Fly.io"
	@echo "  update-all     - Update ExerciseDB data and upload to OpenAI"
	@echo "  deploy-openai  - Update ExerciseDB data, upload to OpenAI, and set Fly.io secrets"

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

.PHONY: update-exercises
update-exercises:
	uv run python scripts/download_exercisedb.py

upload-minified:
	@echo "Minifying and uploading ExerciseDB data to OpenAI..."
	@uv run python scripts/simple_openai_upload.py

.PHONY: set-fly-secret
set-fly-secret:
	@if [ -z "$(shell grep '^OPENAI_VECTOR_STORE_ID=' .env | tail -1 | cut -d'=' -f2)" ]; then \
		echo "❌ No OPENAI_VECTOR_STORE_ID found in .env file. Run 'make upload-minified' first."; \
		exit 1; \
	fi
	@echo "🔐 Setting OpenAI vector store ID as Fly.io secret..."
	@flyctl secrets set OPENAI_VECTOR_STORE_ID=$$(grep '^OPENAI_VECTOR_STORE_ID=' .env | tail -1 | cut -d'=' -f2)
	@echo "✅ OPENAI_VECTOR_STORE_ID Fly.io secret updated successfully!"

.PHONY: set-openai-file-id
set-openai-file-id:
	@if [ -z "$(shell grep '^OPENAI_FILE_ID=' .env | tail -1 | cut -d'=' -f2)" ]; then \
		echo "❌ No OPENAI_FILE_ID found in .env file."; \
		exit 1; \
	fi
	@echo "🔐 Setting OpenAI file ID as Fly.io secret..."
	@flyctl secrets set OPENAI_FILE_ID=$$(grep '^OPENAI_FILE_ID=' .env | tail -1 | cut -d'=' -f2)
	@echo "✅ OPENAI_FILE_ID Fly.io secret updated successfully!"

.PHONY: set-all-openai-secrets
set-all-openai-secrets: set-fly-secret
	@echo "🔐 Setting all OpenAI secrets in Fly.io..."
	@if [ -n "$(shell grep '^OPENAI_FILE_ID=' .env | tail -1 | cut -d'=' -f2)" ]; then \
		$(MAKE) set-openai-file-id; \
	else \
		echo "ℹ️  No OPENAI_FILE_ID found, skipping..."; \
	fi
	@echo "✅ All OpenAI secrets updated in Fly.io!"

.PHONY: update-all
update-all: update-exercises upload-to-openai
	@echo "✅ Updated ExerciseDB data and uploaded to OpenAI"

.PHONY: deploy-openai
deploy-openai: upload-minified set-all-openai-secrets
	@echo "🚀 Complete OpenAI deployment completed!"
	@echo "   • ExerciseDB data updated"
	@echo "   • File minified and uploaded to OpenAI"
	@echo "   • All Fly.io secrets updated"

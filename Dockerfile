# Stage 1: Build with UV 0.8.8 + Python 3.13
FROM ghcr.io/astral-sh/uv:0.8.8-python3.13-bookworm as uv
WORKDIR /app
COPY pyproject.toml ./
# If you add a uv.lock later, copy it too for reproducible builds:
# COPY uv.lock ./
RUN uv sync

# Stage 2: Runtime
FROM python:3.13.6-slim-bookworm
WORKDIR /app
COPY --from=uv /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
COPY . .
CMD ["python", "-m", "app.main"]
FROM node:24-alpine AS webapp

WORKDIR /web

COPY webapp/package.json webapp/package-lock.json ./
RUN npm ci

COPY webapp ./
RUN npm run build

FROM python:3.12.11-alpine AS builder
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/

ENV UV_LINK_MODE=copy

WORKDIR /app

# Install build dependencies for psutil
RUN apk add --no-cache gcc python3-dev musl-dev linux-headers

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable

# Copy the project into the intermediate image
COPY . /app

# Sync the project (this installs all dependencies including Babel)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=cache,target=/root/.cache/pip \
    uv sync --locked --no-editable

FROM python:3.12.11-alpine AS runtime

WORKDIR /app

RUN apk add --no-cache ttf-dejavu tzdata
ENV TZ=Etc/UTC

# Copy the environment
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Compile locales
RUN pybabel compile -d .venv/lib/python3.12/site-packages/buddy_gym_bot/bot/locales/ -D messages -f

# Copy the webapp (Next.js static export)
COPY --from=webapp /web/out /app/static/webapp

# Run the application
EXPOSE 8080
# CMD ["/app/.venv/bin/python", "-m", "buddy_gym_bot.main"]
CMD ["uvicorn", "buddy_gym_bot.server.main:app", "--host", "0.0.0.0", "--port", "8080"]

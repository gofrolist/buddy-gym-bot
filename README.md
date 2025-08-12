# Buddy Gym Bot (Telegram)

A minimal, production-ready Telegram bot that acts as your gym buddy.

- Python **3.13.6**, UV **0.8.8**
- Fly.io deploy (webhook)
- GitHub Actions CI (tests, lint, typecheck) + CD (Fly deploy)
- Pre-commit (ruff + pyright)
- Evidence-informed defaults, progressive overload, PR tracking

## Quickstart

```bash
uv sync
uv tool install pre-commit ruff pyright pytest
pre-commit install

# Local run (polling)
export BOT_TOKEN=123:abc
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres
export ADMIN_CHAT_ID=123456789  # Telegram ID to receive quota alerts
uv run python -m app.main
```

### Logging

The bot uses Python's standard `logging` module. Logs are emitted at the
`INFO` level by default with timestamps, logger names and messages. Adjust the
log level via environment variables or in `main.py` if needed.

### Deploy to Fly

1) Create Postgres/Redis apps (optional), set secrets on bot:
```bash
fly secrets set   BOT_TOKEN=... OPENAI_API_KEY=... ADMIN_CHAT_ID=<telegram_id>   DATABASE_URL='postgresql://postgres:<pass>@<pg-app>.internal:5432/postgres'   REDIS_URL='redis://default:<pass>@<redis-app>.internal:6379/0'   WEBHOOK_URL='https://<bot-app>.fly.dev/bot'
```

2) Push to `main` → GitHub Actions builds and deploys.

### Migrations
```bash
uv run psycopg -c "$(cat migrations/001_init.sql)" "$DATABASE_URL"
```

### Commands
- `/start` – welcome & help
- `/plan [goal] [days] [equipment]` – create plan, e.g. `/plan strength 3 gym`
- `/today` – show today's workout
- `/log Bench 3x5 @ 60kg RPE7` – log a set
- `/stats` – show PRs
- `/ask <question>` – quick LLM advice

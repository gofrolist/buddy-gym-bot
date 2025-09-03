#!/bin/bash

# Development script for Gym Buddy Bot
# Starts both backend and frontend servers with health checks and safe cleanup

set -Eeuo pipefail

echo "🚀 Starting Gym Buddy Bot development environment..."

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

# Load local environment variables from .env if present (export all)
if [ -f .env ]; then
  echo "🔧 Loading environment from .env"
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

# Force local SQLite for dev regardless of .env
export DATABASE_URL="sqlite+aiosqlite:///./local_dev.db"
echo "🗄️  Using local SQLite DB: ${DATABASE_URL}"

# Defaults for local development (respect existing env values)
export BOT_TOKEN="${BOT_TOKEN:-test-token}"
export ADMIN_CHAT_ID="${ADMIN_CHAT_ID:-123456789}"

BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

# Expose backend origin to Next.js (browser-safe) if not already set
export NEXT_PUBLIC_BACKEND_ORIGIN="${NEXT_PUBLIC_BACKEND_ORIGIN:-http://localhost:${BACKEND_PORT}}"

# Helpers
is_port_busy() {
    local port="$1"
    if command -v lsof >/dev/null 2>&1; then
        lsof -iTCP -sTCP:LISTEN -P -n | grep -q ":${port} "
    else
        # Fallback: try nc if available
        if command -v nc >/dev/null 2>&1; then
            nc -z 127.0.0.1 "$port" >/dev/null 2>&1
        else
            return 1
        fi
    fi
}

wait_for_http() {
    local url="$1"
    local timeout="${2:-30}"
    local attempt=0
    until curl -sSf "$url" >/dev/null 2>&1; do
        attempt=$((attempt+1))
        if [ "$attempt" -ge "$timeout" ]; then
            echo "❌ Timed out waiting for $url"
            return 1
        fi
        sleep 1
    done
    return 0
}

# Function to cleanup on exit
BACKEND_PID=""; FRONTEND_PID=""
cleanup() {
    echo "\n🛑 Shutting down development servers..."
    if [ -n "${FRONTEND_PID}" ] && kill -0 "${FRONTEND_PID}" 2>/dev/null; then
        kill "${FRONTEND_PID}" 2>/dev/null || true
        wait "${FRONTEND_PID}" 2>/dev/null || true
    fi
    if [ -n "${BACKEND_PID}" ] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
        kill "${BACKEND_PID}" 2>/dev/null || true
        wait "${BACKEND_PID}" 2>/dev/null || true
    fi
}

# Set up signal handlers
trap cleanup EXIT INT TERM

# Pre-flight: check ports
if is_port_busy "$BACKEND_PORT"; then
    echo "❌ Port ${BACKEND_PORT} appears in use. Stop the existing process and retry."
    exit 1
fi
if is_port_busy "$FRONTEND_PORT"; then
    echo "❌ Port ${FRONTEND_PORT} appears in use. Stop the existing process and retry."
    exit 1
fi

echo "📦 Starting backend server on ${BACKEND_HOST}:${BACKEND_PORT}..."
uv run uvicorn buddy_gym_bot.server.main:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}" --reload &
BACKEND_PID=$!

echo "⏳ Waiting for backend to become ready..."
if ! wait_for_http "http://localhost:${BACKEND_PORT}/docs" 45; then
    echo "Hint: Check backend logs above."
    exit 1
fi

# Informative echo for frontend origin
echo "🌐 NEXT_PUBLIC_BACKEND_ORIGIN=${NEXT_PUBLIC_BACKEND_ORIGIN}"

echo "🌐 Starting frontend server..."
cd webapp
npm run dev &
FRONTEND_PID=$!
cd - >/dev/null 2>&1

echo "⏳ Waiting for frontend to become ready..."
if ! wait_for_http "http://localhost:${FRONTEND_PORT}" 60; then
    echo "Hint: Frontend logs may show why dev server failed to start."
    exit 1
fi

echo "✅ Development environment started!"
echo "📱 Frontend: http://localhost:${FRONTEND_PORT}"
echo "🔧 Backend: http://localhost:${BACKEND_PORT}"
echo "📊 API Docs: http://localhost:${BACKEND_PORT}/docs"
echo ""
echo "Press Ctrl+C to stop all servers"

# Wait for both processes
wait "$BACKEND_PID" "$FRONTEND_PID"

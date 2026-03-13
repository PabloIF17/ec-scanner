#!/bin/bash
set -e

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting API server..."
exec uvicorn src.api.main:app --host "${API_HOST:-0.0.0.0}" --port "${API_PORT:-8000}" --reload

#!/bin/bash

# Exit on error
set -e

echo "Running migrations..."
alembic upgrade head

echo "Starting server..."
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT

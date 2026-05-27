#!/usr/bin/env bash
# Initialize Aurora Database

set -euo pipefail

if [ -z "${AURORA_URL:-}" ]; then
  # Try to read from .env
  if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
  fi
fi

if [ -z "${AURORA_URL:-}" ]; then
  echo "Error: AURORA_URL environment variable is not set."
  echo "Please set it in your .env file or export it directly."
  echo "Example: postgresql://postgres:password@aurora-cluster-endpoint:5432/postgres"
  exit 1
fi

echo "Connecting to Aurora..."
echo "Applying initial schema..."
psql "$AURORA_URL" -f db/plain-init/001_initial_schema.sql

echo "Applying app users schema..."
psql "$AURORA_URL" -f db/plain-init/002_app_users.sql

echo "Database initialized successfully!"

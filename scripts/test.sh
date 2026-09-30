#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../backend"
if [[ -f ../.env ]]; then set -a; . ../.env; set +a; fi
export JANUS_TEST_DATABASE_URL="${JANUS_TEST_DATABASE_URL:-postgresql+psycopg://janus:${DB_JANUS_PASSWORD:-janus}@localhost:5432/janus_test}"
exec uv run --no-project --python 3.12 --with-requirements requirements-dev.txt pytest "$@"

#!/bin/sh
set -e
case "${1:-api}" in
  api)
    alembic upgrade head
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
    ;;
  worker)
    exec python -m app.worker
    ;;
  sentinel)
    exec /usr/local/bin/janus-sniff -m app.sentinel.main
    ;;
  scanner)
    exec python -m app.intel.scanner
    ;;
  *)
    exec "$@"
    ;;
esac

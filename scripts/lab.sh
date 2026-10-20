#!/bin/sh
set -eu
case "${1:-}" in
  start)
    docker compose up -d besu
    ;;
  test)
    docker compose run --rm --build verifier
    ;;
  stop)
    docker compose down --volumes --remove-orphans
    ;;
  reset)
    docker compose down --volumes --remove-orphans
    docker compose up -d besu
    ;;
  *)
    echo "Usage: sh scripts/lab.sh {start|test|stop|reset}" >&2
    exit 2
    ;;
esac

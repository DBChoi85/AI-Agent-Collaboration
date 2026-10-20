#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
case "${1:-}" in
  start)
    sh scripts/generate-besu-lab.sh
    docker compose up -d --force-recreate besu
    ;;
  test)
    docker compose run --rm --build verifier
    ;;
  contract-test)
    docker compose run --rm --build contract-test
    ;;
  stop)
    docker compose down --volumes --remove-orphans
    rm -rf local-besu-lab
    ;;
  reset)
    docker compose down --volumes --remove-orphans
    rm -rf local-besu-lab
    sh scripts/generate-besu-lab.sh
    docker compose up -d --force-recreate besu
    ;;
  *)
    echo "Usage: sh scripts/lab.sh {start|test|contract-test|stop|reset}" >&2
    exit 2
    ;;
esac

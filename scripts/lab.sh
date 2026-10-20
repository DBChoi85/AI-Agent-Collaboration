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
  a2a-test)
    docker compose up -d --build agent-a agent-b
    docker compose run --rm --build a2a-test
    ;;
  official-a2a-test)
    docker compose up -d --build sdk-agent-a sdk-agent-b
    docker compose run --rm --build official-a2a-test
    ;;
  integrated-test)
    docker compose up -d --build besu agent-a agent-b
    docker compose run --rm --build integrated-test
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
    echo "Usage: sh scripts/lab.sh {start|test|contract-test|a2a-test|integrated-test|official-a2a-test|stop|reset}" >&2
    exit 2
    ;;
esac

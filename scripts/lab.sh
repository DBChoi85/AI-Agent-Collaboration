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
    docker compose up -d --build --wait sdk-agent-a sdk-agent-b
    docker compose run --rm --no-deps --build official-a2a-test
    ;;
  authenticated-a2a-test)
    docker compose run --rm --build --no-deps identity-init
    docker compose --profile auth up -d --build --force-recreate --wait auth-agent-a auth-agent-b
    for service in auth-agent-a auth-agent-b; do
      actual="$(docker compose exec -T "$service" printenv A2A_REQUIRE_AUTH)"
      if [ "$actual" != "1" ]; then
        echo "FAIL CLOSED: $service A2A_REQUIRE_AUTH must be 1, got '$actual'" >&2
        exit 1
      fi
    done
    docker compose run --rm --build --no-deps authenticated-a2a-test
    ;;
  official-a2a-besu-test)
    sh scripts/lab.sh authenticated-a2a-test
    docker compose run --rm --build --no-deps official-a2a-besu-test
    ;;
  onchain-dpki-test)
    docker compose run --rm --build --no-deps identity-init
    docker compose run --rm --build --no-deps certificate-status
    A2A_REQUIRE_DLT_STATUS=1 docker compose --profile auth up -d --build --force-recreate --wait auth-agent-a auth-agent-b
    for service in auth-agent-a auth-agent-b; do
      actual="$(docker compose exec -T "$service" printenv A2A_REQUIRE_DLT_STATUS)"
      if [ "$actual" != "1" ]; then
        echo "FAIL CLOSED: $service DLT status gate is not active" >&2
        exit 1
      fi
    done
    docker compose run --rm --build --no-deps authenticated-a2a-test
    CERTIFICATE_STATUS_ACTION=revoke docker compose run --rm --build --no-deps certificate-status
    docker compose run --rm --build --no-deps onchain-revocation-test
    ;;
  benchmark)
    # Deliberately reset disposable Besu/identities; keep host benchmark-results.
    : "${BENCH_REPEATS:=100}"
    : "${BENCH_WARMUPS:=10}"
    : "${BENCH_RUN_ID:=$(date -u +%Y%m%dT%H%M%SZ)}"
    export BENCH_REPEATS BENCH_WARMUPS BENCH_RUN_ID
    mkdir -p benchmark-results
    echo "BENCH_RUN_ID=$BENCH_RUN_ID; repeats=$BENCH_REPEATS; warmups=$BENCH_WARMUPS"
    sh scripts/lab.sh reset
    docker compose up -d --build --wait sdk-agent-a sdk-agent-b
    BENCH_MODE=baseline docker compose --profile benchmark run --rm --no-deps --build a2a-benchmark
    docker compose run --rm --no-deps --build identity-init
    A2A_REQUIRE_DLT_STATUS=0 docker compose --profile auth up -d --build --force-recreate --wait auth-agent-a auth-agent-b
    BENCH_MODE=x509 docker compose --profile benchmark run --rm --no-deps a2a-benchmark
    docker compose run --rm --no-deps --build certificate-status
    A2A_REQUIRE_DLT_STATUS=1 docker compose --profile auth up -d --build --force-recreate --wait auth-agent-a auth-agent-b
    for service in auth-agent-a auth-agent-b; do
      actual="$(docker compose --profile auth exec -T "$service" printenv A2A_REQUIRE_DLT_STATUS)"
      if [ "$actual" != "1" ]; then
        echo "FAIL CLOSED: $service DLT gate not active" >&2
        exit 1
      fi
    done
    BENCH_MODE=x509-besu docker compose --profile benchmark run --rm --no-deps a2a-benchmark
    docker compose --profile auth ps --format json > "benchmark-results/containers-$BENCH_RUN_ID.json"
    docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.NetIO}}' \
      > "benchmark-results/resources-$BENCH_RUN_ID.csv"
    echo "PASS: benchmark CSV/JSON saved under benchmark-results (retained after stop)"
    ;;
  security-evaluation)
    python3 scripts/security_evaluation.py --reset
    ;;
  trust-test)
    docker compose run --rm --no-deps --build trust-test
    ;;
  integrated-test)
    docker compose up -d --build besu agent-a agent-b
    docker compose run --rm --build integrated-test
    ;;
  contract-test)
    docker compose run --rm --build contract-test
    ;;
  stop)
    docker compose --profile auth --profile test --profile benchmark down --volumes --remove-orphans
    rm -rf local-besu-lab
    ;;
  reset)
    docker compose --profile auth --profile test down --volumes --remove-orphans
    rm -rf local-besu-lab
    sh scripts/generate-besu-lab.sh
    docker compose up -d --force-recreate besu
    ;;
  *)
    echo "Usage: sh scripts/lab.sh {start|test|contract-test|a2a-test|integrated-test|official-a2a-test|authenticated-a2a-test|official-a2a-besu-test|onchain-dpki-test|benchmark|security-evaluation|trust-test|stop|reset}" >&2
    exit 2
    ;;
esac

# Disposable Besu Docker lab

This is a **single-node development network**, not a production permissioned consortium or cross-domain deployment. Docker Compose isolates Besu from host interfaces except loopback RPC. No external persistent files are needed; ledger data is in a Docker named volume.

## Requirements
Docker Engine + Compose v2.

## Run
```sh
sh scripts/lab.sh start
sh scripts/lab.sh test
sh scripts/lab.sh stop
```

`start` starts Besu; `test` waits for Besu JSON-RPC and runs all Python unit tests inside a clean container; `stop` removes containers, network and **all ledger data**. Use `reset` to rebuild the disposable chain.

Direct commands:
```sh
docker compose up -d besu
docker compose run --rm --build verifier
docker compose down -v --remove-orphans
```

## Important limitations
- The Solidity contract is **not yet compiled, deployed or exercised on-chain**. A Solidity toolchain and contract-level tests are required before marking #1 complete.
- DPKI and A2A integration, multi-domain containers, signed evidence and benchmarks are pending.
- `--network=dev` and permissive RPC/CORS/host settings are intended **only for isolated local research**; never expose the RPC port publicly.
- Besu image uses an explicit version tag; for long-term bitwise reproducibility, pin a tested immutable image digest.
- The lab currently uses a persistent named volume between `start` and `test`; `stop` deletes it. For independent benchmark repetitions, invoke `reset` between runs.
- Network access is needed initially to pull Docker images.

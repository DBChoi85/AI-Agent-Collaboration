# Disposable Besu contract E2E

This phase compiles the Solidity registry in a Docker image and deploys it to a disposable Besu development node. The script asserts lifecycle transitions, access restrictions, evidence anchoring, sequence/head, and expected reverts.

## Run

```sh
docker compose up -d besu
docker compose run --rm --build contract-test
docker compose down --volumes --remove-orphans
```

The contract-test image uses Node 22, ethers 6.15.0 and solc 0.8.30. Docker image and npm package versions should be pinned by immutable digests and a committed lockfile for strict reproducibility. No external signing key is embedded in the repository: this test uses unlocked accounts supplied by Besu's development network.

## Boundaries

This is **single-node EVM integration**, not DPKI or A2A integration. Besu dev RPC must remain loopback-only on the host. The on-chain owner is responsible for verifying agent identities off-chain. Evidence anchoring is not proof that an agent performed the action.

## Acceptance

The E2E runner exits nonzero on compiler errors, missing development accounts, unexpected success of unauthorized calls, or incorrect contract state. Runtime execution must be verified in a Docker-equipped environment before reporting PASS.

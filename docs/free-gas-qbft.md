# Disposable free-gas QBFT lab

Run `sh scripts/lab.sh reset` to delete old containers/volumes and generate a new QBFT genesis and one validator private key. `sh scripts/lab.sh contract-test` compiles Solidity, estimates deployment gas, deploys the registry, and checks the lifecycle. Run `sh scripts/lab.sh stop` to remove all chain data and generated keys.

This is an isolated **single-validator development network**, not a fault-tolerant production blockchain. The generated `local-besu-lab/` directory must never be committed. The chain config enables `zeroBaseFee`; Besu also runs with `--min-gas-price=0`. Gas accounting still applies, but gas payments are zero. The contract-test container resolves the latest compatible Solidity 0.8.x compiler at build time and prints the exact version. The EVM target is pinned to Cancun for Besu 25.9.0 compatibility. Use `docker compose logs besu` if startup fails.

# Official A2A SDK → X.509 → Besu Artifact Evidence (experimental)

Run:

```sh
git pull origin main
bash scripts/lab.sh reset
bash scripts/lab.sh official-a2a-besu-test
bash scripts/lab.sh stop
```

The runner creates independent CA and agent keys inside the disposable Docker identity volume, starts authentication-required official A2A SDK servers, verifies signed tasks in both directions and rejects tampered/stale/unsigned tasks. It exports **SHA-256 digests and byte counts only** from the authenticated artifact text into a disposable Docker evidence volume. A Node.js container then compiles and deploys `CollaborationRegistry.sol` to the local zero-gas Besu QBFT chain, registers two hashed source identities, anchors both digests, verifies the emitted `EvidenceAnchored` events, and closes the collaboration.

Expected markers: `PASS: authenticated official A2A SDK tasks accepted` and `PASS: authenticated official A2A artifact hashes anchored to Besu in both directions`. The result line `OFFICIAL_A2A_BESU_RESULT` includes block numbers and transaction-backed digests.

**Trust boundary:** This is post-execution anchoring of artifacts that passed the off-chain X.509 signed-envelope check. The registry does **not** verify CA status or a DPKI directory commitment, and the A2A executor does **not** consult Besu before authorizing a task. There is no replay cache. The output is a one-run integration smoke test, not a benchmark.

**Cleanup:** `lab.sh stop` uses both `auth` and `test` Compose profiles so authentication containers are also stopped and the evidence/identity volumes are removed. The previous `Network ... Resource is still in use` message was caused by profiled auth containers surviving the old cleanup.

# Integrated Docker agent HTTP exchange → Besu evidence

Start from a clean disposable network:

```sh
sh scripts/lab.sh reset
sh scripts/lab.sh integrated-test
sh scripts/lab.sh stop
```

Unlike the previous two independent test tracks, the integrated runner performs real HTTP requests to two independently running Docker agents, receives their task artifacts, checks SHA-256 over canonical JSON, deploys a fresh Solidity CollaborationRegistry to the zero-base-fee Besu QBFT chain, registers both agent identities, anchors the exact received artifact hashes, parses on-chain EvidenceAnchored logs, and rejects a locally tampered copy. It exercises A→B and B→A and prints one machine-readable INTEGRATED_RESULT JSON record.

**Security boundary:** Identity hashes in the contract are supplied by the trusted test runner, not independently verified DPKI credentials. There is no actual DPKI authorization, no signed Agent Cards, and no authenticated HTTP channel. The endpoints implement an A2A-inspired JSON-RPC subset, not complete official A2A 1.0 interoperability. The artifact itself remains off-chain. This is a functional single-run E2E integration test, not a repeated benchmark or full secure collaboration proof.

Future work: official A2A SDK transport; independently provisioned domain credentials and fail-closed DPKI verification; signed artifact provenance and anti-replay; repeated baseline vs anchored trials.

# Cross-domain artifact evidence experiment (v1)

Run:

```sh
sh scripts/lab.sh reset
sh scripts/lab.sh contract-test
sh scripts/lab.sh stop
```

The existing contract E2E first deploys the registry and exercises membership, authorization, evidence, and closure. The next experiment creates a new collaboration with a producer in domain A and a consumer in domain B. It creates a deterministic JSON task-result payload **off-chain**, computes SHA-256, anchors the digest using the registry, reads the `EvidenceAnchored` event, checks the original payload, and verifies that a one-byte modification no longer matches the anchored digest. It prints one machine-readable `EXPERIMENT_RESULT=` JSON line with create/join/anchor/close transaction wall-clock durations.

**Interpretation:** This is a single-run functional proof of digest integrity and contract evidence. Domain names are logical identifiers, not independently running Docker agents. It does **not** implement A2A Agent Card/Task/Message/Artifact transport, DPKI trust verification, artifact access control, repeated-sample statistics, or A2A-only comparison. Do not use these timings as paper benchmark results until repeated independent-domain experiments and controls are implemented.

The owner signer is wrapped in ethers `NonceManager` so the contract deployment and subsequent transactions use consecutive nonces on the free-gas chain. Revert assertions use static calls and do not consume transaction nonces.

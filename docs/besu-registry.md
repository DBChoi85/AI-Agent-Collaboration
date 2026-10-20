# Besu collaboration registry — phase 2

Contract: `contracts/CollaborationRegistry.sol` (Solidity ^0.8.24).

## On-chain semantics
- `create(id, ownerIdentity)`: register collaboration; id and identity are nonzero bytes32.
- `join(id, identity)`: owner-authorized participant admission.
- `leave(id, identity)`: owner-authorized participant removal.
- `anchor(id, identity, digest)`: owner submits an evidence commitment for a current member.
- `close(id)`: permanently close collaboration.
- Every transition advances a hash-linked event head and sequence.
- The contract records hashes and event metadata only, not Agent Cards, messages or artifacts.

## Security boundary
The EVM cannot verify DPKI certificates in this implementation. The transaction sender is the on-chain collaboration owner, who **must** verify the real DPKI identity and agent-to-hash binding before admitting participants or anchoring their events. Consequently the current contract does **not** cryptographically prove that the named agent performed an action. Off-chain signed event envelopes, independent validation, replay controls and a DPKI adapter are required in issues #2/#4.

## Execution
`BesuRpc` is a standard-library JSON-RPC *read-only* connectivity client. Example:

```python
from collaboration.chain import BesuRpc
print(BesuRpc("http://127.0.0.1:8545").status())
```

Compile/deploy the Solidity contract with a Solidity 0.8.24+ compiler and a configured EVM toolchain. Deployment scripts and live-chain contract integration are not yet included. No live Besu integration tests have been run for this PR.

## Follow-up
- Solidity compile + contract-level tests for all state transitions, permissions, events and invalid inputs.
- Deterministic deployment and readback against disposable Besu.
- DPKI-backed signed evidence and multi-domain A2A integration.

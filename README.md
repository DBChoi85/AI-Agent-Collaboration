# AI Agent Collaboration

Research prototype for **DLT-based trusted collaboration and information sharing among heterogeneous AI agents**.

## Scope
- DPKI: cross-domain trust anchor and identity verification (**real adapter pending**).
- A2A 1.0: Agent Card, Message, Task and Artifact transport (**integration pending**).
- DLT: collaboration membership and event commitments (**Besu integration pending**).
- Off-chain: shared data and task results with SHA-256 integrity.

This initial PR provides a **local reference core**, not a production DPKI/A2A/Besu integration. By default, unverified identities are rejected. The allowlist verifier exists only in tests.

## Test
```bash
python3 -m unittest discover -s tests -v
```

Python 3.11+, standard library only.

## Boundaries
No agent internal-state synchronization, PMI delegation, raw on-chain content or implicit resource authorization from collaboration membership.

See [architecture](docs/architecture.md) and issues #1–#6 for implementation milestones.

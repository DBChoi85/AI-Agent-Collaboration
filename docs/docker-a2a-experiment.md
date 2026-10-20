# Docker cross-domain agent exchange — first transport milestone

Run `sh scripts/lab.sh reset`, then `sh scripts/lab.sh a2a-test` and `sh scripts/lab.sh contract-test`. Finish with `sh scripts/lab.sh stop`.

The `agent-a` and `agent-b` containers independently expose an Agent Card-like discovery endpoint at `/.well-known/agent-card.json` and a JSON-RPC `message/send` endpoint at `/a2a`. The test container discovers each receiver, submits a task-result message in each direction, checks the returned artifact digest, and detects a changed payload. The transport output is `A2A_TRANSPORT_RESULT`. The contract-test independently verifies on-chain digest anchoring.

**Limitations:** The HTTP transport is a research-only A2A-inspired subset, **not certified A2A 1.0 interoperability**. It lacks full Agent Card security scheme fields, canonical A2A SDK models, authenticated messaging, persistence, and error semantics. The transport and chain test tracks are not yet connected into a single workflow; DPKI verification is not yet integrated. No production security or publication-ready benchmark claim is made.

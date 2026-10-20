# Official A2A SDK 1.0 migration (PR #18)

This track uses the official `a2a-sdk==1.0.3` Python library, its `DefaultRequestHandler`, `InMemoryTaskStore`, Agent Card routes, JSON-RPC routes, `AgentExecutor`, and official SDK client. It is distinct from the previous research-only HTTP subset, which remains available for comparison.

```sh
sh scripts/lab.sh reset
sh scripts/lab.sh official-a2a-test
sh scripts/lab.sh stop
```

The test discovers two independent Docker agent cards, checks JSON-RPC protocol binding and version, sends SDK `SendMessageRequest` messages in both directions, obtains task artifacts, verifies canonical JSON and detects tampering. It prints `OFFICIAL_A2A_RESULT`.

This PR does **not** replace the existing Besu integrated test: that runner still targets the legacy A2A-inspired endpoint. A follow-on PR must connect the official SDK artifacts to the existing on-chain anchor flow and DPKI trust checks. No authenticated transport, persistence, or statistically valid benchmark is claimed.

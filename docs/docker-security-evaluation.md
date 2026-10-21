# Docker-backed security evaluation for paper Section 4.3

Run from the repository root:

```sh
sh scripts/lab.sh security-evaluation
```

**Destructive lab reset:** this command explicitly calls `lab.sh reset` and
deletes the existing Compose lab volumes and local Besu chain. Run only against
the disposable `ai-agent-collaboration` Compose project. Existing
`benchmark-results/` files are retained.

The command reuses the existing `onchain-dpki-test` path:
1. Generate a fresh QBFT Besu lab.
2. Create disposable per-domain CA/agent identities.
3. Deploy and register certificates on Besu.
4. Start both official authenticated A2A agents with the DLT status gate active.
5. Check valid, tampered, stale and unsigned requests in **both** directions.
6. Revoke Domain A's certificate on-chain and check revoked A rejected and active B accepted.

The test fails if the Docker command exits nonzero, any structured scenario
record is missing/duplicated, the expected A2A task state is wrong, or a
rejected request produces an artifact. A skipped or unexecuted test is never
reported as a pass.

Evidence is retained under `benchmark-results/security-<timestamp>-<id>/`:
- `reset.log`, `integration.log`: Docker execution transcript
- `results.json`: completeness, errors, scenario outcomes
- `results.csv`: one row per observed scenario

The security test performs **10 checks**: eight authentication cases (four per
direction), plus two on-chain revocation checks. This is a functional
integration test, not a statistical performance benchmark. It does not
establish general replay protection or WAN/concurrency performance.

To remove the disposable lab after evidence collection:

```sh
sh scripts/lab.sh stop
```

The runner intentionally does not call `stop` automatically, to preserve
containers for debugging failures. The user must explicitly stop the lab.

**Publication rule:** only use PASS outcomes after the command has actually
run successfully. Adding this PR does not establish that tests have passed.

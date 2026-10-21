# A2A certificate-status security validation

This harness tests the **real receiver's acceptance boundary**, not a
standalone Boolean function. It does not supply a Besu deployment, certificates,
or an A2A transport; these must exist before results can be claimed.

## Scenarios

| Argument | Certificate/signature/request state | Expected accepted | Expected task_dispatched |
|---|---|---|---|
| `valid` | Active registered certificate, valid signature, fresh request | true | true |
| `revoked` | Previously valid certificate revoked on Besu and state update confirmed | false | false |
| `invalid_signature` | Active certificate, tampered signature or signed payload | false | false |
| `stale_request` | Active certificate and valid signature, freshness outside permitted window | false | false |

## Adapter contract

Create an executable runner (outside the repository if it holds secrets) and set
`A2A_SECURITY_RUNNER=/absolute/path/to/runner`. It receives one argument
from the table. It must (1) create fresh test certificates and signed requests,
(2) register/update certificate state via the **real** Besu contract, waiting for
transaction confirmation, (3) submit a request through the **actual** receiving
A2A gateway, (4) observe whether downstream task processing occurred, and
(5) emit exactly one JSON object to stdout:

```json
{"accepted": false, "task_dispatched": false, "reason": "revoked"}
```

Do not implement the adapter by returning hard-coded expected values: that
would only test the harness. Use stderr for diagnostics. Avoid storing private
keys or credentials in logs. Ensure teardown removes generated certificates,
containers and test state where supported; do not reset shared Besu networks.

## Execute

```bash
A2A_SECURITY_RUNNER=/absolute/path/to/runner A2A_SECURITY_REQUIRED=1 \
  python3 -m unittest discover -s tests -p 'test_a2a_security_acceptance.py' -v
```

Without a configured runner, tests are **SKIPPED**, not PASSED. Set
`A2A_SECURITY_REQUIRED=1` in a real integration environment to fail closed.

## Reporting

Only report scenarios as validated after the actual runner executes and all
assertions pass. Preserve the command, timestamp, commit SHA, Besu contract
address, and sanitized output for paper Table 3. The existing repository README
currently describes DPKI, official A2A and Besu integration as pending; this PR
does **not** claim to implement them.

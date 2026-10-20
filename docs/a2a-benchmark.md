# Reproducible three-track A2A benchmark

## Purpose

Compare **official A2A SDK 1.0** task round-trip latency in three configurations:

| Track | A2A | Signed X.509 envelope | Besu certificate-status lookup |
|---|---|---|---|
| `baseline` | Yes | No | No |
| `x509` | Yes | Yes | No |
| `x509-besu` | Yes | Yes | Yes |

The third track performs an on-chain **certificate digest active-status read** before producing an artifact. It is **not** a full decentralized PKI proof, consensus benchmark, or a blockchain write per task.

## Run

Requires Docker Compose v2 and an available local Docker daemon. From the repository root:

```sh
git pull origin main
BENCH_REPEATS=100 BENCH_WARMUPS=10 sh scripts/lab.sh benchmark
sh scripts/lab.sh stop
```

The benchmark **resets the disposable Besu network and identities at the start**. Do not run it against data you need to retain. Output files under `benchmark-results/` are host bind-mounted and **survive** `stop` and `reset`.

Optional `BENCH_RUN_ID=experiment-01` groups output files. Run IDs must be unique: the runner refuses to overwrite an existing task CSV. Run the benchmark multiple times with distinct IDs to evaluate between-run variability.

## Outputs

- `tasks-<run-id>-<mode>.csv`: each task (including marked warmups), source/receiver, elapsed milliseconds, artifact size, task status, success and error.
- `summary-<run-id>-<mode>.json`: successful measured-task mean/median/p95, measured count, and *sequential* throughput estimate.
- `containers-<run-id>.json`: final Compose service status snapshot.
- `resources-<run-id>.csv`: single Docker resource snapshot at the end, **not** peak memory or per-track utilization.

Each mode sends `BENCH_WARMUPS` warmup tasks followed by `BENCH_REPEATS` measured tasks in **both directions**, sequentially from one client. The timer wraps the official SDK `send_message` response stream and excludes Agent Card discovery, startup, contract deployment and certificate provisioning. All measured tasks must finish successfully or the command exits nonzero. CSV is written before failure exit for diagnosis.

## Interpretation and limitations

- The same task payload value and A2A SDK are used across tracks, but signed envelopes are larger than the unsigned baseline; differences reflect signing, verification, payload serialization, and Besu status reads together.
- The `x509-besu` track measures **read-only** `eth_call` status checks, not on-chain transaction confirmation latency.
- CPU/memory snapshot is collected only after all three tracks and must not be reported as per-mode peak usage. For rigorous resource comparison, add per-track time-series collection.
- The sequential throughput estimate `1000 / mean_latency_ms` is **not** concurrent throughput. Repeat runs, disclose host hardware and Docker resource allocation, and report variability before making statistical claims.
- These benchmarks measure the **active-certificate success path**. Revocation rejection is validated separately by `sh scripts/lab.sh onchain-dpki-test`.

"""Reproducible A2A SDK round-trip benchmark; one row per task, including warmups."""
import asyncio
import csv
import json
import os
from pathlib import Path
import statistics
import time

import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types.a2a_pb2 import Role, SendMessageRequest, TaskState
from collaboration.a2a_auth import sign_envelope

MODE = os.environ["BENCH_MODE"]
if MODE not in ("baseline", "x509", "x509-besu"):
    raise ValueError("unsupported BENCH_MODE")
REPEATS = int(os.getenv("BENCH_REPEATS", "100"))
WARMUPS = int(os.getenv("BENCH_WARMUPS", "10"))
if not (1 <= REPEATS <= 100000 and 0 <= WARMUPS <= 10000):
    raise ValueError("invalid benchmark sample count")
OUTPUT = Path(os.getenv("BENCH_OUTPUT", "/results"))
RUN_ID = os.getenv("BENCH_RUN_ID", "run")
FIELDNAMES = ["run_id", "mode", "source", "receiver", "iteration", "warmup",
              "latency_ms", "artifact_bytes", "status", "success", "error"]


async def run_one(client, source, iteration, warmup):
    if MODE == "baseline":
        payload = {"source": source, "task": "exchange", "value": 42}
    else:
        payload = sign_envelope(source, {"operation": "exchange", "value": 42})
    request = SendMessageRequest(message=new_text_message(
        json.dumps(payload, sort_keys=True), role=Role.ROLE_USER))
    status, texts = None, []
    start = time.perf_counter_ns()
    try:
        async for response in client.send_message(request):
            kind = response.WhichOneof("payload")
            if kind == "task":
                status = response.task.status.state
                for artifact in response.task.artifacts:
                    texts.extend(part.text for part in artifact.parts if part.text)
            elif kind == "status_update":
                status = response.status_update.status.state
            elif kind == "artifact_update":
                texts.extend(part.text for part in response.artifact_update.artifact.parts if part.text)
        elapsed = (time.perf_counter_ns() - start) / 1e6
        success = status == TaskState.TASK_STATE_COMPLETED and bool(texts)
        return elapsed, sum(len(t.encode("utf-8")) for t in texts), int(status) if status is not None else "", success, ""
    except Exception as exc:
        return (time.perf_counter_ns() - start) / 1e6, 0, "", False, type(exc).__name__ + ": " + str(exc)


async def main():
    if MODE == "baseline":
        pairs = [("domainA/producer", "http://sdk-agent-b:8080"),
                 ("domainB/consumer", "http://sdk-agent-a:8080")]
    else:
        pairs = [("domainA/producer", "http://auth-agent-b:8080"),
                 ("domainB/consumer", "http://auth-agent-a:8080")]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    file = OUTPUT / ("tasks-" + RUN_ID + "-" + MODE + ".csv")
    if file.exists():
        raise FileExistsError("refusing to overwrite benchmark run: " + str(file))
    rows = []
    async with httpx.AsyncClient(timeout=30) as http:
        for source, url in pairs:
            card = await A2ACardResolver(httpx_client=http, base_url=url).get_agent_card()
            client = await create_client(agent=card, client_config=ClientConfig(streaming=False))
            try:
                for i in range(WARMUPS + REPEATS):
                    warmup = i < WARMUPS
                    elapsed, size, status, success, error = await run_one(client, source, i - WARMUPS if not warmup else i, warmup)
                    row = dict(run_id=RUN_ID, mode=MODE, source=source, receiver=card.name,
                               iteration=i - WARMUPS if not warmup else i,
                               warmup=int(warmup), latency_ms=round(elapsed, 6),
                               artifact_bytes=size, status=status, success=int(success), error=error)
                    rows.append(row)
                    if not success:
                        print("BENCH_FAILURE=" + json.dumps(row), flush=True)
            finally:
                await client.close()
    with file.open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    measured = [r for r in rows if not r["warmup"]]
    good = [r["latency_ms"] for r in measured if r["success"]]
    if good:
        ordered = sorted(good)
        summary = dict(run_id=RUN_ID, mode=MODE, count=len(measured), passed=len(good),
                       mean_ms=round(statistics.mean(good), 3),
                       median_ms=round(statistics.median(good), 3),
                       p95_ms=round(ordered[max(0, (95 * len(ordered) + 99) // 100 - 1)], 3),
                       throughput_tasks_per_s=round(1000 / statistics.mean(good), 3),
                       caveat="sequential client throughput estimate, not concurrent system capacity")
    else:
        summary = dict(run_id=RUN_ID, mode=MODE, count=len(measured), passed=0)
    (OUTPUT / ("summary-" + RUN_ID + "-" + MODE + ".json")).write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("BENCH_RESULT=" + json.dumps(summary), flush=True)
    print("BENCH_CSV=" + str(file), flush=True)
    if len(good) != len(measured):
        raise SystemExit("FAIL: measured tasks did not all complete")


if __name__ == "__main__":
    asyncio.run(main())

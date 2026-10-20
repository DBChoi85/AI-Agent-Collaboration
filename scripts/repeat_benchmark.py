#!/usr/bin/env python3
"""Run independent A2A benchmark repetitions with randomized track order.

Usage: python3 scripts/repeat_benchmark.py --runs 10 --repeats 100 --warmups 10
Uses only Python stdlib on the host. Docker Compose v2 is required.
"""
import argparse
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent.parent
MODES = ("baseline", "x509", "x509-besu")


def command(args, env=None):
    print("+ " + " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, env={**os.environ, **(env or {})}, check=True)


def compose(*args, env=None):
    command(["docker", "compose", *args], env=env)


def summarize(values):
    mean = statistics.mean(values)
    sd = statistics.stdev(values) if len(values) > 1 else None
    ci = (1.96 * sd / math.sqrt(len(values))) if sd is not None else None
    return {"runs": len(values), "mean_ms": round(mean, 6),
            "run_sd_ms": round(sd, 6) if sd is not None else None,
            "approx_95ci_normal_ms": [round(mean - ci, 6), round(mean + ci, 6)] if ci is not None else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=100)
    parser.add_argument("--warmups", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20261021)
    parser.add_argument("--prefix", default=None)
    args = parser.parse_args()
    if not 2 <= args.runs <= 100 or not 1 <= args.repeats <= 100000 or not 0 <= args.warmups <= 10000:
        parser.error("invalid runs/repeats/warmups")
    prefix = args.prefix or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    if not all(c.isalnum() or c in "-_" for c in prefix):
        parser.error("prefix must contain only alphanumeric, dash or underscore")
    output = ROOT / "benchmark-results"
    output.mkdir(exist_ok=True)
    manifest = output / ("replications-" + prefix + ".json")
    if manifest.exists():
        parser.error("manifest already exists: " + str(manifest))
    rng = random.Random(args.seed)
    records = []
    complete = False
    try:
        for number in range(1, args.runs + 1):
            run_id = f"{prefix}-r{number:02d}"
            order = list(MODES)
            rng.shuffle(order)
            print(f"REPLICATION {number}/{args.runs} ORDER={order}", flush=True)
            # Every replication uses newly generated Besu chain and X.509 identities.
            command(["sh", "scripts/lab.sh", "stop"])
            command(["sh", "scripts/lab.sh", "reset"])
            compose("up", "-d", "--build", "--wait", "sdk-agent-a", "sdk-agent-b")
            compose("run", "--rm", "--no-deps", "--build", "identity-init")
            compose("run", "--rm", "--no-deps", "--build", "certificate-status")
            for mode in order:
                if mode != "baseline":
                    gate = "1" if mode == "x509-besu" else "0"
                    compose("--profile", "auth", "up", "-d", "--build",
                            "--force-recreate", "--wait", "auth-agent-a", "auth-agent-b",
                            env={"A2A_REQUIRE_DLT_STATUS": gate})
                    for service in ("auth-agent-a", "auth-agent-b"):
                        actual = subprocess.check_output(
                            ["docker", "compose", "--profile", "auth", "exec", "-T",
                             service, "printenv", "A2A_REQUIRE_DLT_STATUS"],
                            cwd=ROOT, text=True).strip()
                        if actual != gate:
                            raise RuntimeError(f"FAIL CLOSED: {service} expected DLT gate {gate}, got {actual!r}")
                compose("--profile", "benchmark", "run", "--rm", "--no-deps",
                        "--build", "a2a-benchmark",
                        env={"BENCH_MODE": mode, "BENCH_REPEATS": str(args.repeats),
                             "BENCH_WARMUPS": str(args.warmups), "BENCH_RUN_ID": run_id})
                csv_path = output / f"tasks-{run_id}-{mode}.csv"
                with csv_path.open(newline="", encoding="utf-8") as handle:
                    rows = list(csv.DictReader(handle))
                measured = [row for row in rows if row["warmup"] == "0"]
                if len(measured) != args.repeats * 2 or any(row["success"] != "1" for row in measured):
                    raise RuntimeError(f"invalid benchmark results: {csv_path}")
                mean = statistics.mean(float(row["latency_ms"]) for row in measured)
                records.append({"replication": number, "run_id": run_id,
                                "mode": mode, "order_position": order.index(mode) + 1,
                                "mean_ms": mean, "samples": len(measured),
                                "csv": csv_path.name})
            manifest.write_text(json.dumps({"complete": False, "seed": args.seed,
                "runs_requested": args.runs, "repeats_per_direction": args.repeats,
                "warmups_per_direction": args.warmups, "records": records}, indent=2) + "\n")
        complete = True
    finally:
        manifest.write_text(json.dumps({"complete": complete, "seed": args.seed,
            "runs_requested": args.runs, "repeats_per_direction": args.repeats,
            "warmups_per_direction": args.warmups, "records": records}, indent=2) + "\n")
    summary = {"prefix": prefix, "seed": args.seed, "runs": args.runs,
               "note": "normal-approximation 95% CI on independent run means; not task-level independent CI",
               "tracks": {}, "paired_differences_ms": {}}
    by_run = {(r["replication"], r["mode"]): r["mean_ms"] for r in records}
    for mode in MODES:
        summary["tracks"][mode] = summarize([by_run[i, mode] for i in range(1, args.runs + 1)])
    for a, b in (("x509", "baseline"), ("x509-besu", "x509"), ("x509-besu", "baseline")):
        summary["paired_differences_ms"][a + "_minus_" + b] = summarize(
            [by_run[i, a] - by_run[i, b] for i in range(1, args.runs + 1)])
    result = output / ("replication-summary-" + prefix + ".json")
    result.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("PASS: independent randomized replications complete")
    print("REPLICATION_MANIFEST=" + str(manifest))
    print("REPLICATION_SUMMARY=" + str(result))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, RuntimeError, OSError) as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        sys.exit(1)

#!/usr/bin/env python3
"""Run existing Docker A2A/Besu security checks and retain paper-ready evidence."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = {
    ("domainA/producer", "valid"): True,
    ("domainA/producer", "tampered"): False,
    ("domainA/producer", "stale"): False,
    ("domainA/producer", "unsigned"): False,
    ("domainB/consumer", "valid"): True,
    ("domainB/consumer", "tampered"): False,
    ("domainB/consumer", "stale"): False,
    ("domainB/consumer", "unsigned"): False,
}
REVOKED = {"domainA/producer": False, "domainB/consumer": True}


def execute(args, log_path):
    with log_path.open("w", encoding="utf-8") as out:
        process = subprocess.run(args, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT, check=False)
    if process.returncode:
        raise RuntimeError(f"Command failed ({process.returncode}): {' '.join(args)}; see {log_path}")
    return log_path.read_text(encoding="utf-8")


def extract(text, prefix):
    found = []
    for line in text.splitlines():
        if line.startswith(prefix):
            found.append(json.loads(line[len(prefix):]))
    return found


def evaluate_auth(text):
    records = extract(text, "AUTH_CASE=")
    if len(records) != len(EXPECTED):
        raise RuntimeError(f"Expected {len(EXPECTED)} AUTH_CASE records, got {len(records)}")
    results = []
    seen = set()
    for record in records:
        key = (record["source"], record["case"])
        if key not in EXPECTED or key in seen:
            raise RuntimeError(f"Unexpected or duplicate AUTH_CASE: {key}")
        seen.add(key)
        accepted = record.get("status") == 3 and record.get("artifacts", 0) > 0
        # A2A TaskState numeric values: COMPLETED=3, FAILED=4.
        rejected = record.get("status") == 4 and record.get("artifacts") == 0
        expected = EXPECTED[key]
        if not (accepted if expected else rejected):
            raise RuntimeError(f"Unexpected AUTH_CASE outcome: {record}")
        results.append({"phase": "authentication", "source": key[0], "scenario": key[1],
                        "expected_accept": expected, "observed_accept": accepted, "passed": True})
    return results


def evaluate_revocation(text):
    records = extract(text, "ONCHAIN_CASE=")
    if len(records) != len(REVOKED):
        raise RuntimeError(f"Expected {len(REVOKED)} ONCHAIN_CASE records, got {len(records)}")
    results = []
    seen = set()
    for record in records:
        source = record["source"]
        if source not in REVOKED or source in seen:
            raise RuntimeError(f"Unexpected or duplicate ONCHAIN_CASE: {source}")
        seen.add(source)
        expected = REVOKED[source]
        accepted = record.get("status") == 3 and record.get("artifactCount", 0) > 0
        rejected = record.get("status") == 4 and record.get("artifactCount") == 0
        if not (accepted if expected else rejected):
            raise RuntimeError(f"Unexpected ONCHAIN_CASE outcome: {record}")
        results.append({"phase": "onchain", "source": source,
                        "scenario": "active_after_revocation" if expected else "revoked",
                        "expected_accept": expected, "observed_accept": accepted, "passed": True})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true",
                        help="Explicitly destroy existing lab volumes and recreate disposable Besu state")
    args = parser.parse_args()
    if not args.reset:
        parser.error("--reset required: existing on-chain test revokes a certificate and changes lab state")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    output = ROOT / "benchmark-results" / ("security-" + run_id)
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    error = None
    try:
        execute(["sh", "scripts/lab.sh", "reset"], output / "reset.log")
        # Reuse existing full integration path, including identity generation,
        # contract deployment, active gate check, signed A2A and revocation.
        log = execute(["sh", "scripts/lab.sh", "onchain-dpki-test"], output / "integration.log")
        rows.extend(evaluate_auth(log))
        rows.extend(evaluate_revocation(log))
    except (RuntimeError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        error = str(exc)
    finally:
        result = {"run_id": run_id, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                  "complete": error is None and len(rows) == 10,
                  "cases_passed": len(rows), "cases_expected": 10,
                  "error": error, "cases": rows,
                  "note": "Real Docker A2A SDK and Besu integration; no latency measurement"}
        (output / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        with (output / "results.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["phase", "source", "scenario",
                              "expected_accept", "observed_accept", "passed"])
            writer.writeheader()
            writer.writerows(rows)
        print("SECURITY_EVIDENCE=" + str(output))
    if error or len(rows) != 10:
        raise SystemExit("FAIL: " + (error or "incomplete scenario set"))
    print("PASS: 10 observed A2A security cases across authentication and on-chain revocation")


if __name__ == "__main__":
    main()

"""Exercise two real Docker HTTP agents; verify off-chain task artifacts."""
from __future__ import annotations
from hashlib import sha256
from urllib.request import Request, urlopen
import json
import time


def get(url: str) -> dict:
    with urlopen(url, timeout=5) as r:
        return json.load(r)


def wait(url: str) -> None:
    for _ in range(40):
        try:
            if get(url + "/health")["status"] == "ready":
                return
        except OSError:
            time.sleep(1)
    raise RuntimeError("agent not ready: " + url)


def exchange(sender: str, receiver: str) -> dict:
    card = get(receiver + "/.well-known/agent-card.json")
    assert card["url"].endswith("/a2a")
    payload = {"jsonrpc": "2.0", "id": "experiment-1", "method": "message/send",
               "params": {"message": {"role": "user", "parts": [
                   {"data": {"source": sender, "task": "share-result", "value": 42}}
               ]}}}
    req = Request(receiver + "/a2a", data=json.dumps(payload).encode(),
                  headers={"Content-Type": "application/json"})
    start = time.perf_counter_ns()
    with urlopen(req, timeout=10) as r:
        response = json.load(r)
    latency_ms = (time.perf_counter_ns() - start) / 1e6
    task = response["result"]
    assert task["status"]["state"] == "completed"
    artifact = task["artifacts"][0]
    content = artifact["parts"][0]["data"]
    raw = json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    assert sha256(raw).hexdigest() == artifact["sha256"]
    tampered = dict(content, accepted=False)
    altered = json.dumps(tampered, sort_keys=True, separators=(",", ":")).encode()
    assert sha256(altered).hexdigest() != artifact["sha256"]
    return {"sender": sender, "receiver": card["name"], "taskId": task["id"],
            "artifactBytes": len(raw), "latencyMs": round(latency_ms, 3),
            "verified": True, "tamperDetected": True}


def main() -> None:
    a, b = "http://agent-a:8080", "http://agent-b:8080"
    wait(a)
    wait(b)
    results = [exchange("domainA/producer", b), exchange("domainB/consumer", a)]
    print("PASS: independent Docker agents exchanged task artifacts over HTTP in both directions")
    print("A2A_TRANSPORT_RESULT=" + json.dumps({"track": "docker-a2a-inspired-v1",
        "exchanges": results, "caveat": "A2A-inspired JSON-RPC subset; no DPKI or Besu anchoring in this track"}))


if __name__ == "__main__":
    main()

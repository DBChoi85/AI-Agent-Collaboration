"""Check Docker Besu connectivity and run local Python tests.

Does not deploy a smart contract or claim end-to-end A2A/DPKI integration.
"""
from __future__ import annotations
import os
import time
import unittest
from collaboration.chain import BesuRpc, RpcError


def wait_for_besu(url: str, attempts: int = 45, interval: float = 2.0) -> dict:
    client = BesuRpc(url, timeout=3)
    last_error = None
    for _ in range(attempts):
        try:
            status = client.status()
            if status["chain_id"] <= 0 or status["block_number"] < 0:
                raise RpcError("invalid Besu chain status")
            return status
        except (RpcError, OSError) as exc:
            last_error = exc
            time.sleep(interval)
    raise RuntimeError(f"Besu did not become ready after {attempts} attempts") from last_error


def main() -> None:
    url = os.environ.get("BESU_RPC_URL", "http://besu:8545")
    status = wait_for_besu(url)
    print(f"Besu ready: chain_id={status['chain_id']} block={status['block_number']}")
    suite = unittest.defaultTestLoader.discover("tests")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    print("Docker infrastructure smoke: PASS (RPC + Python tests only)")


if __name__ == "__main__":
    main()

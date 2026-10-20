"""Minimal JSON-RPC read-only Besu connectivity checks; no hidden deployment."""
from __future__ import annotations
import json
from urllib.request import Request, urlopen


class RpcError(RuntimeError):
    pass


class BesuRpc:
    def __init__(self, url: str, timeout: float = 5.0):
        if not url.startswith(("http://", "https://")):
            raise ValueError("HTTP(S) RPC endpoint required")
        self.url = url
        self.timeout = timeout

    def call(self, method: str, params: list | None = None):
        payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                              "params": [] if params is None else params}).encode()
        req = Request(self.url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=self.timeout) as response:
                result = json.load(response)
        except (OSError, ValueError) as exc:
            raise RpcError("RPC transport or JSON failure") from exc
        if result.get("jsonrpc") != "2.0" or result.get("id") != 1:
            raise RpcError("malformed JSON-RPC response")
        if "error" in result:
            raise RpcError(str(result["error"]))
        if "result" not in result:
            raise RpcError("missing result")
        return result["result"]

    def status(self) -> dict:
        return {"chain_id": int(self.call("eth_chainId"), 16),
                "block_number": int(self.call("eth_blockNumber"), 16)}

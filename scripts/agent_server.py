"""Independent Docker agent: minimal A2A-inspired JSON-RPC task/artifact transport.

Not a complete A2A 1.0 protocol implementation or authenticated endpoint.
"""
from __future__ import annotations
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from uuid import uuid4

DOMAIN = os.environ.get("AGENT_DOMAIN", "domain-unknown")
NAME = os.environ.get("AGENT_NAME", "agent")
URL = os.environ.get("AGENT_PUBLIC_URL", "http://localhost:8080")
TASKS: dict[str, dict] = {}


class Handler(BaseHTTPRequestHandler):
    def respond(self, status: int, data: dict) -> None:
        raw = json.dumps(data, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path == "/.well-known/agent-card.json":
            self.respond(200, {
                "name": NAME, "description": "Research-only task result exchange agent",
                "url": URL + "/a2a", "version": "0.1.0",
                "capabilities": {"streaming": False, "pushNotifications": False},
                "defaultInputModes": ["application/json"],
                "defaultOutputModes": ["application/json"],
                "skills": [{"id": "echo-result", "name": "Task result exchange",
                            "description": "Return a JSON task result", "tags": ["experiment"]}]
            })
        elif self.path == "/health":
            self.respond(200, {"domain": DOMAIN, "agent": NAME, "status": "ready"})
        else:
            self.respond(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/a2a":
            return self.respond(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 65536:
                return self.respond(413, {"error": "invalid payload size"})
            request = json.loads(self.rfile.read(length))
            if request.get("jsonrpc") != "2.0" or request.get("method") != "message/send":
                return self.respond(400, {"jsonrpc": "2.0", "id": request.get("id"),
                                           "error": {"code": -32601, "message": "method not supported"}})
            params = request.get("params", {})
            message = params.get("message", {})
            parts = message.get("parts", [])
            if not isinstance(parts, list) or not parts or not isinstance(parts[0].get("data"), dict):
                raise ValueError("JSON data part required")
            content = parts[0]["data"]
            task_id = str(uuid4())
            result = {"taskId": task_id, "receiver": DOMAIN + "/" + NAME,
                      "input": content, "accepted": True}
            raw = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
            artifact = {"artifactId": str(uuid4()), "name": "task-result",
                        "parts": [{"data": result}], "sha256": sha256(raw).hexdigest()}
            task = {"id": task_id, "status": {"state": "completed"}, "artifacts": [artifact]}
            TASKS[task_id] = task
            self.respond(200, {"jsonrpc": "2.0", "id": request.get("id"), "result": task})
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            self.respond(400, {"error": str(exc)})


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()

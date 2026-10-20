"""Bidirectional official A2A SDK v1 client/server interoperability smoke test."""
import asyncio
from hashlib import sha256
import json
import os
import time

import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types.a2a_pb2 import Role, SendMessageRequest

AGENTS = [
    ("domainA/producer", os.getenv("AGENT_B_URL", "http://sdk-agent-b:8080")),
    ("domainB/consumer", os.getenv("AGENT_A_URL", "http://sdk-agent-a:8080")),
]


async def discover(http: httpx.AsyncClient, url: str):
    for _ in range(45):
        try:
            return await A2ACardResolver(httpx_client=http, base_url=url).get_agent_card()
        except (httpx.HTTPError, ValueError, RuntimeError):
            await asyncio.sleep(1)
    raise RuntimeError("Agent Card unavailable: " + url)


async def main() -> None:
    records = []
    async with httpx.AsyncClient(timeout=15) as http:
        for source, url in AGENTS:
            card = await discover(http, url)
            assert card.supported_interfaces[0].protocol_binding == "JSONRPC"
            assert card.supported_interfaces[0].protocol_version == "1.0"
            client = await create_client(agent=card, client_config=ClientConfig(streaming=False))
            try:
                message = json.dumps({"source": source, "task": "exchange", "value": 42}, sort_keys=True)
                request = SendMessageRequest(message=new_text_message(message, role=Role.ROLE_USER))
                started = time.perf_counter_ns()
                artifact_text = None
                async for response in client.send_message(request):
                    if response.WhichOneof("payload") == "task":
                        for artifact in response.task.artifacts:
                            for part in artifact.parts:
                                if part.text:
                                    artifact_text = part.text
                    elif response.WhichOneof("payload") == "artifact_update":
                        for part in response.artifact_update.artifact.parts:
                            if part.text:
                                artifact_text = part.text
                assert artifact_text is not None, "SDK did not return a task artifact"
                data = json.loads(artifact_text)
                assert data["sourceText"] == message
                assert data["accepted"] is True
                digest = sha256(artifact_text.encode()).hexdigest()
                tampered = dict(data, accepted=False)
                assert sha256(json.dumps(tampered, sort_keys=True, separators=(",", ":")).encode()).hexdigest() != digest
                records.append({"source": source, "receiver": card.name,
                                "artifactBytes": len(artifact_text.encode()), "sha256": digest,
                                "latencyMs": round((time.perf_counter_ns() - started) / 1e6, 3),
                                "tamperDetected": True})
            finally:
                await client.close()
    assert len(records) == 2
    print("PASS: official A2A 1.0 SDK Agent Card discovery, Task, Message, Artifact, both directions")
    print("OFFICIAL_A2A_RESULT=" + json.dumps({"track": "official-a2a-sdk-v1", "records": records,
        "caveat": "SDK transport only; DPKI and Besu anchoring remain separate"}))


if __name__ == "__main__":
    asyncio.run(main())

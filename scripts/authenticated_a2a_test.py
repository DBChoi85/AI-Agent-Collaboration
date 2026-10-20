"""Official SDK authenticated task acceptance and rejection, in both directions."""
import asyncio
import json
import time
import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types.a2a_pb2 import Role, SendMessageRequest, TaskState
from collaboration.a2a_auth import sign_envelope

CASES = [
    ("domainA/producer", "http://sdk-agent-b:8080"),
    ("domainB/consumer", "http://sdk-agent-a:8080"),
]

async def send(client, envelope):
    request = SendMessageRequest(message=new_text_message(
        json.dumps(envelope, sort_keys=True), role=Role.ROLE_USER))
    status, artifacts = None, []
    async for response in client.send_message(request):
        kind = response.WhichOneof("payload")
        if kind == "task":
            status = response.task.status.state
            artifacts.extend(response.task.artifacts)
        elif kind == "status_update":
            status = response.status_update.status.state
        elif kind == "artifact_update":
            artifacts.append(response.artifact_update.artifact)
    return status, artifacts

async def main():
    records = []
    async with httpx.AsyncClient(timeout=15) as http:
        for source, url in CASES:
            card = await A2ACardResolver(httpx_client=http, base_url=url).get_agent_card()
            client = await create_client(agent=card, client_config=ClientConfig(streaming=False))
            try:
                signed = sign_envelope(source, {"operation": "exchange", "value": 42})
                status, artifacts = await send(client, signed)
                assert status == TaskState.TASK_STATE_COMPLETED and artifacts, (status, artifacts)
                altered = json.loads(json.dumps(signed))
                altered["body"]["payload"]["value"] = 43
                tampered_status, tampered_artifacts = await send(client, altered)
                assert tampered_status == TaskState.TASK_STATE_FAILED and not tampered_artifacts
                stale = sign_envelope(source, {"operation": "exchange"})
                stale["body"]["issuedAt"] = int(time.time()) - 300
                stale_status, stale_artifacts = await send(client, stale)
                assert stale_status == TaskState.TASK_STATE_FAILED and not stale_artifacts
                unsigned_status, unsigned_artifacts = await send(client, {"payload": "unsigned"})
                assert unsigned_status == TaskState.TASK_STATE_FAILED and not unsigned_artifacts
                records.append({"source": source, "receiver": card.name,
                    "validAccepted": True, "tamperedRejected": True,
                    "staleRejected": True, "unsignedRejected": True})
            finally:
                await client.close()
    print("PASS: authenticated official A2A SDK tasks accepted; unsigned/tampered/stale rejected")
    print("AUTHENTICATED_A2A_RESULT=" + json.dumps({"track": "a2a-x509-signed-envelope", "records": records,
        "caveat": "application-layer signature only; no replay cache, on-chain DPKI, or Besu anchoring"}))

if __name__ == "__main__":
    asyncio.run(main())

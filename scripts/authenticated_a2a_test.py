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
    status, artifacts, events = None, [], []
    async for response in client.send_message(request):
        kind = response.WhichOneof("payload")
        events.append({"kind": kind})
        if kind == "task":
            status = response.task.status.state
            events[-1]['status'] = int(status)
            artifacts.extend(response.task.artifacts)
        elif kind == "status_update":
            status = response.status_update.status.state
            events[-1]['status'] = int(status)
        elif kind == "artifact_update":
            artifacts.append(response.artifact_update.artifact)
        events[-1]['artifacts'] = len(artifacts)
    return status, artifacts, events

async def main():
    records = []
    async with httpx.AsyncClient(timeout=15) as http:
        for source, url in CASES:
            card = await A2ACardResolver(httpx_client=http, base_url=url).get_agent_card()
            client = await create_client(agent=card, client_config=ClientConfig(streaming=False))
            try:
                signed = sign_envelope(source, {"operation": "exchange", "value": 42})
                status, artifacts, valid_events = await send(client, signed)
                print("AUTH_CASE=" + json.dumps({"source": source, "case": "valid", "status": int(status) if status is not None else None, "artifacts": len(artifacts), "events": valid_events}), flush=True)
                assert status == TaskState.TASK_STATE_COMPLETED and artifacts, (status, artifacts)
                altered = json.loads(json.dumps(signed))
                altered["body"]["payload"]["value"] = 43
                tampered_status, tampered_artifacts, tampered_events = await send(client, altered)
                print("AUTH_CASE=" + json.dumps({"source": source, "case": "tampered", "status": int(tampered_status) if tampered_status is not None else None, "artifacts": len(tampered_artifacts), "events": tampered_events}), flush=True)
                assert tampered_status == TaskState.TASK_STATE_FAILED and not tampered_artifacts
                stale = sign_envelope(source, {"operation": "exchange"})
                stale["body"]["issuedAt"] = int(time.time()) - 300
                stale_status, stale_artifacts, stale_events = await send(client, stale)
                print("AUTH_CASE=" + json.dumps({"source": source, "case": "stale", "status": int(stale_status) if stale_status is not None else None, "artifacts": len(stale_artifacts), "events": stale_events}), flush=True)
                assert stale_status == TaskState.TASK_STATE_FAILED and not stale_artifacts
                unsigned_status, unsigned_artifacts, unsigned_events = await send(client, {"payload": "unsigned"})
                print("AUTH_CASE=" + json.dumps({"source": source, "case": "unsigned", "status": int(unsigned_status) if unsigned_status is not None else None, "artifacts": len(unsigned_artifacts), "events": unsigned_events}), flush=True)
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

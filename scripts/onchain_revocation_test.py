"""Verify Besu certificate revocation blocks actual official A2A task execution."""
import asyncio
import json
import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from collaboration.a2a_auth import sign_envelope
from scripts.authenticated_a2a_test import send
from a2a.types.a2a_pb2 import TaskState

async def main():
    async with httpx.AsyncClient(timeout=15) as http:
        for source, url, expected in [
            ("domainA/producer", "http://auth-agent-b:8080", TaskState.TASK_STATE_FAILED),
            ("domainB/consumer", "http://auth-agent-a:8080", TaskState.TASK_STATE_COMPLETED),
        ]:
            card = await A2ACardResolver(httpx_client=http, base_url=url).get_agent_card()
            client = await create_client(agent=card, client_config=ClientConfig(streaming=False))
            try:
                status, artifacts, events = await send(client, sign_envelope(source, {"operation":"exchange"}))
                assert status == expected, (source, status, events)
                assert bool(artifacts) == (expected == TaskState.TASK_STATE_COMPLETED), (source, events)
                print("ONCHAIN_CASE=" + json.dumps({"source":source,"status":int(status),
                    "artifactCount":len(artifacts)}),flush=True)
            finally:
                await client.close()
    print("PASS: revoked domainA rejected and active domainB accepted by official A2A SDK")

if __name__ == "__main__":
    asyncio.run(main())

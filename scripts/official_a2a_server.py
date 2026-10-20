"""Official A2A Python SDK 1.0 JSON-RPC server for disposable Docker experiments."""
import json
import logging
import os

import uvicorn
from collaboration.a2a_auth import verify_envelope
from collaboration.trust import TrustRejected
from a2a.helpers import get_message_text, new_task_from_user_message, new_text_message, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from a2a.types.a2a_pb2 import TaskState
from starlette.applications import Starlette

DOMAIN = os.environ.get("AGENT_DOMAIN", "unknown")
NAME = os.environ.get("AGENT_NAME", "agent")
LOG = logging.getLogger('a2a.auth')
PUBLIC_URL = os.environ.get("AGENT_PUBLIC_URL", "http://localhost:8080")


class ExchangeExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        if task is None:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue=event_queue, task_id=task.id, context_id=task.context_id)
        await updater.update_status(TaskState.TASK_STATE_WORKING, message=new_text_message("Working"))
        source_text = get_message_text(context.message)
        if os.environ.get("A2A_REQUIRE_AUTH") == "1":
            try:
                authenticated_source, payload = verify_envelope(json.loads(source_text))
                source_text = json.dumps({"authenticatedSource": authenticated_source,
                                          "payload": payload}, sort_keys=True)
            except (TrustRejected, ValueError, TypeError) as exc:
                LOG.warning('A2A_AUTH_REJECT receiver=%s/%s reason=%s', DOMAIN, NAME, type(exc).__name__)
                await updater.update_status(TaskState.TASK_STATE_FAILED,
                                            message=new_text_message("Authentication rejected"))
                return
            LOG.info("A2A_AUTH_ACCEPT receiver=%s/%s sender=%s", DOMAIN, NAME, authenticated_source)
        # The exact artifact returned by the SDK is canonical UTF-8 JSON text.
        result = {"receiver": f"{DOMAIN}/{NAME}", "sourceText": source_text, "accepted": True}
        artifact_text = json.dumps(result, sort_keys=True, separators=(",", ":"))
        await updater.add_artifact(parts=[new_text_part(text=artifact_text, media_type="application/json")])
        await updater.update_status(TaskState.TASK_STATE_COMPLETED, message=new_text_message("Completed"))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("Cancellation is not supported by this experiment")


def build_app() -> Starlette:
    card = AgentCard(
        name=NAME,
        description="Official A2A 1.0 SDK artifact exchange experiment",
        version="1.0.0",
        default_input_modes=["text/plain"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(streaming=False),
        supported_interfaces=[AgentInterface(
            protocol_binding="JSONRPC", url=PUBLIC_URL + "/a2a", protocol_version="1.0"
        )],
        skills=[AgentSkill(
            id="exchange-artifact", name="Exchange task artifact",
            description="Return a JSON text artifact for an A2A task",
            input_modes=["text/plain"], output_modes=["application/json"],
            tags=["collaboration", "artifact"],
        )],
    )
    handler = DefaultRequestHandler(
        agent_executor=ExchangeExecutor(), task_store=InMemoryTaskStore(), agent_card=card
    )
    return Starlette(routes=[
        *create_agent_card_routes(card),
        *create_jsonrpc_routes(handler, rpc_url="/a2a"),
    ])


if __name__ == "__main__":
    uvicorn.run(build_app(), host="0.0.0.0", port=8080)

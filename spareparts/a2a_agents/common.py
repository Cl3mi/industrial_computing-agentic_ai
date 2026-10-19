"""Shared A2A plumbing: agent card, a JSON-in/JSON-out executor and the Starlette app.

Request convention: one data part {"skill": "<skill id>", "input": {...}}. The reply is one data part
with the skill result, or {"error": "..."} so the caller (an LLM) can read and react to the failure.
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Awaitable, Callable

from a2a.helpers import get_data_parts, get_message_text, new_data_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill, Message
from google.protobuf.json_format import MessageToDict
from starlette.applications import Starlette

from .registration import register_with_retry

Skill = Callable[[dict], Awaitable[dict]]
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def make_card(name: str, description: str, url: str, skills: list[AgentSkill]) -> AgentCard:
    return AgentCard(
        name=name,
        description=description,
        version="0.1.0",
        supported_interfaces=[AgentInterface(url=url, protocol_binding="JSONRPC", protocol_version="1.0")],
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        skills=skills,
    )


def card_to_registry(card: AgentCard) -> dict:
    """Card as JSON for LiteLLM. LiteLLM routes on the top-level 'url' (A2A 0.3 field), so add it."""
    data = MessageToDict(card)
    data["url"] = card.supported_interfaces[0].url
    data["protocolVersion"] = "1.0"
    return data


def parse_request(message: Message) -> dict:
    data = get_data_parts(message.parts)
    if data:
        return data[0]
    text = get_message_text(message).strip()
    return json.loads(text) if text else {}


class SkillExecutor(AgentExecutor):
    def __init__(self, skills: dict[str, Skill]):
        self.skills = skills

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        try:
            request = parse_request(context.message)
            name = request.get("skill") or (next(iter(self.skills)) if len(self.skills) == 1 else None)
            if name not in self.skills:
                raise ValueError(f"unknown skill {name!r}; available: {sorted(self.skills)}")
            result = await self.skills[name](request.get("input", {}))
        except Exception as exc:
            log.warning("skill call failed: %r", exc)
            result = {"error": f"{type(exc).__name__}: {exc}"}
        await event_queue.enqueue_event(
            new_data_message(result, context_id=context.context_id, task_id=context.task_id)
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("skills answer immediately; nothing to cancel")


def build_app(card: AgentCard, skills: dict[str, Skill], agent_name: str) -> Starlette:
    handler = DefaultRequestHandler(
        agent_executor=SkillExecutor(skills), task_store=InMemoryTaskStore(), agent_card=card
    )

    @asynccontextmanager
    async def lifespan(app):
        task = None
        if os.environ.get("LITELLM_URL"):
            task = asyncio.create_task(register_with_retry(
                os.environ["LITELLM_URL"], os.environ["LITELLM_MASTER_KEY"], agent_name, card_to_registry(card)
            ))
        yield
        if task:
            task.cancel()

    routes = create_agent_card_routes(card) + create_jsonrpc_routes(handler, rpc_url="/", enable_v0_3_compat=True)
    return Starlette(routes=routes, lifespan=lifespan)

"""Orchestrator: discovers agents in the LiteLLM registry and solves a request with them.

python -m orchestrator.cli --list
python -m orchestrator.cli --call quote '{"sku": "BRG-6204", "unit_price": 3.4, "quantity": 800}'
python -m orchestrator.cli "A customer orders 800 x BRG-6204. Can we deliver, at what price?"
"""

import argparse
import asyncio
import json
import os

from agent.config import resolve_backend
from agent.loop import litellm_llm, run_agent

from .gateway import Gateway, connect
from .session import RegistryToolSession

ORCHESTRATOR_PROMPT = (
    "You are the orchestrator of a spare-parts procurement network. You know no stock levels, prices or "
    "rules yourself; remote specialist agents do. Your tools were discovered at runtime in the agent registry: "
    "each tool is one skill of one agent and takes input_json, a JSON object string with the fields named in "
    "the tool description. For an order: check stock first, then get a quote with the unit price from the "
    "stock check, then check the order with compliance (pass the quoted total and whether stock is "
    "sufficient), then log the outcome with event_type 'order_review'. If a stock check finds nothing, retry "
    "with a shorter keyword (only the part number) before giving up. Never invent numbers. Answer briefly "
    "with stock situation, total price, lead time and whether approval is needed."
)


def print_event(event: dict) -> None:
    kind = event["type"]
    if kind == "question":
        print(f"\nQUESTION: {event['text']}")
    elif kind == "thought":
        print(f"  [thought] {event['text']}")
    elif kind == "tool_call":
        print(f"  [act]     {event['agent']} -> {event['tool']}({json.dumps(event['arguments'])})")
    elif kind == "observation":
        print(f"  [observe] {event['agent']}: {event['text'][:300]}")
    elif kind == "answer":
        print(f"ANSWER: {event['text']}")


async def ask(question: str, on_event=print_event, llm=None, transport=None) -> str:
    if llm is None:
        llm = litellm_llm(*resolve_backend(os.environ))
    async with connect(transport) as client:
        session = RegistryToolSession(Gateway(client))

        def tagged(event: dict) -> None:
            if "tool" in event:
                event = {**event, "agent": session.routes.get(event["tool"], ("", "unknown"))[1]}
            on_event(event)

        return await run_agent(question, session, llm, max_steps=10, on_event=tagged,
                               system_prompt=ORCHESTRATOR_PROMPT)


async def list_agents() -> None:
    async with connect() as client:
        for agent in await Gateway(client).list_agents():
            card = agent["agent_card_params"]
            skills = ", ".join(s["id"] for s in card.get("skills", []))
            print(f"{agent['agent_name']:<18} {agent['agent_id']}  {card.get('url')}  skills: {skills}")


async def call_skill(skill: str, input_json: str) -> None:
    async with connect() as client:
        session = RegistryToolSession(Gateway(client))
        await session.list_tools()
        if skill not in session.routes:
            raise SystemExit(f"no registered agent offers skill {skill!r}; known: {sorted(session.routes)}")
        result = await session.call_tool(skill, {"input_json": input_json})
        print(f"{session.routes[skill][1]} -> {skill}: {result.content[0].text}")


def main() -> None:
    parser = argparse.ArgumentParser(description="A2A orchestrator over the LiteLLM agent registry")
    parser.add_argument("question", nargs="?")
    parser.add_argument("--list", action="store_true", help="List registered agents and their skills")
    parser.add_argument("--call", nargs=2, metavar=("SKILL", "JSON"), help="Call one skill directly, no LLM")
    args = parser.parse_args()
    if args.list:
        asyncio.run(list_agents())
    elif args.call:
        asyncio.run(call_skill(*args.call))
    elif args.question:
        asyncio.run(ask(args.question))
    else:
        parser.error("give a question, --list or --call")


if __name__ == "__main__":
    main()

"""Ask the procurement agent one question: python -m agent.cli "question" [--server-url URL]"""

import argparse
import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

from .config import resolve_backend
from .loop import litellm_llm, run_agent


def print_event(event: dict) -> None:
    kind = event["type"]
    if kind == "question":
        print(f"\nQUESTION: {event['text']}")
    elif kind == "thought":
        print(f"  [thought] {event['text']}")
    elif kind == "tool_call":
        print(f"  [act]     {event['tool']}({json.dumps(event['arguments'])})")
    elif kind == "observation":
        print(f"  [observe] {event['text'][:300]}")
    elif kind == "answer":
        print(f"ANSWER: {event['text']}")


async def ask(question: str, server_url: str | None, on_event=print_event) -> str:
    model, api_base = resolve_backend(os.environ)
    llm = litellm_llm(model, api_base)
    if server_url:
        async with streamablehttp_client(server_url) as (r, w, _):
            async with ClientSession(r, w) as session:
                await session.initialize()
                return await run_agent(question, session, llm, on_event=on_event)
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"], env=dict(os.environ))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            return await run_agent(question, session, llm, on_event=on_event)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--server-url", help="Use a running Streamable HTTP server, e.g. http://127.0.0.1:8000/mcp")
    args = parser.parse_args()
    asyncio.run(ask(args.question, args.server_url))


if __name__ == "__main__":
    main()

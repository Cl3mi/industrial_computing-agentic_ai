"""Run three different questions through the agent and store the full trace as evidence."""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from agent.cli import ask, print_event

QUESTIONS = [
    "How many 6204 bearings do we have in stock and which supplier delivers them?",
    "A customer wants 800 units of BRG-6204. What is the total price with the volume discount?",
    "Which parts are running low on stock (below 50 units)? Log an inquiry for the purchasing team.",
]


async def main() -> None:
    out = Path("execution_logs")
    out.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    events: list[dict] = []
    md = [f"# Demo run {stamp}", f"Model: `{os.environ.get('LLM_MODEL', 'ollama')}`", ""]

    def record(event: dict) -> None:
        events.append(event)
        print_event(event)
        if event["type"] == "question":
            md.append(f"## Question\n{event['text']}\n")
        elif event["type"] == "tool_call":
            md.append(f"- **act** `{event['tool']}` `{json.dumps(event['arguments'])}`")
        elif event["type"] == "observation":
            md.append(f"  - observe: `{event['text'][:200]}`")
        elif event["type"] == "answer":
            md.append(f"\n**Answer:** {event['text']}\n")

    for question in QUESTIONS:
        await ask(question, None, on_event=record)

    (out / f"demo-{stamp}.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
    (out / f"demo-{stamp}.md").write_text("\n".join(md) + "\n")
    print(f"\nWrote execution_logs/demo-{stamp}.jsonl and .md")


if __name__ == "__main__":
    asyncio.run(main())

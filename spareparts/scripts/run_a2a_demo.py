"""Run three order scenarios through the A2A network and store the full trace as evidence."""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from orchestrator.cli import ask, print_event

QUESTIONS = [
    "A customer orders 800 units of the 6204 bearing. Check stock, price it with the volume discount, "
    "check approval and lead time, and log the review.",
    "We need 40 hydraulic hoses HYD-HOSE-2M. Can we deliver from stock, what does it cost, and when can it arrive?",
    "A plant wants 1500 inductive sensors SNS-IND-M12. Price it, tell me who has to approve it and the lead time.",
]


async def main() -> None:
    out = Path("execution_logs")
    out.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    events: list[dict] = []
    md = [f"# A2A demo run {stamp}", f"Model: `{os.environ.get('LLM_MODEL', 'ollama')}`", ""]

    def record(event: dict) -> None:
        events.append(event)
        print_event(event)
        if event["type"] == "question":
            md.append(f"## Question\n{event['text']}\n")
        elif event["type"] == "tool_call":
            md.append(f"- **act** `{event['agent']}` -> `{event['tool']}` `{json.dumps(event['arguments'])}`")
        elif event["type"] == "observation":
            md.append(f"  - observe: `{event['text'][:200]}`")
        elif event["type"] == "answer":
            md.append(f"\n**Answer:** {event['text']}\n")

    for question in QUESTIONS:
        await ask(question, on_event=record)

    (out / f"a2a-demo-{stamp}.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
    (out / f"a2a-demo-{stamp}.md").write_text("\n".join(md) + "\n")
    print(f"\nWrote execution_logs/a2a-demo-{stamp}.jsonl and .md")


if __name__ == "__main__":
    asyncio.run(main())

"""ReAct tool-calling loop over an MCP ClientSession. The LLM is an injectable callable:
    llm(messages, tools) -> {"content": str | None, "tool_calls": [{"id", "name", "arguments": dict}]}
"""

import json

SYSTEM_PROMPT = (
    "You are a procurement assistant for an industrial spare-parts distributor. "
    "Work in a Reason-Act loop: decide which tool you need, call it, read the result, then continue. "
    "Always check the inventory before quoting, compute prices only with calculate_volume_discount, "
    "and call audit_log once with event_type 'quote' or 'inquiry' summarising the outcome before "
    "your final answer. If a lookup returns no results, retry with a shorter keyword (for example only "
    "the part number) before giving up. Never invent prices or stock levels. Answer briefly."
)


def mcp_tools_to_openai(tools) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {"name": t.name, "description": t.description or "", "parameters": t.inputSchema},
        }
        for t in tools
    ]


def _result_text(result) -> str:
    text = "\n".join(c.text for c in result.content if getattr(c, "type", "") == "text")
    if not text and getattr(result, "structuredContent", None) is not None:  # empty lists come without text
        text = json.dumps(result.structuredContent)
    return f"ERROR: {text}" if getattr(result, "isError", False) else text


async def run_agent(
    question, session, llm, max_steps: int = 8, on_event=lambda e: None, system_prompt: str = SYSTEM_PROMPT
) -> str:
    tools = mcp_tools_to_openai((await session.list_tools()).tools)
    known = {t["function"]["name"] for t in tools}
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}]
    on_event({"type": "question", "text": question})
    last_thought = ""

    for step in range(1, max_steps + 1):
        reply = llm(messages, tools)
        if not reply["tool_calls"]:
            # some models state the answer before their last tool call and then end with empty text
            answer = reply["content"] or last_thought
            on_event({"type": "answer", "text": answer})
            return answer
        if reply["content"]:
            last_thought = reply["content"]
            on_event({"type": "thought", "step": step, "text": reply["content"]})
        messages.append({
            "role": "assistant",
            "content": reply["content"],
            "tool_calls": [
                {"id": c["id"], "type": "function",
                 "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}}
                for c in reply["tool_calls"]
            ],
        })
        for call in reply["tool_calls"]:
            on_event({"type": "tool_call", "step": step, "tool": call["name"], "arguments": call["arguments"]})
            if call["name"] not in known:
                observation = f"ERROR: unknown tool '{call['name']}'. Available: {sorted(known)}"
            else:
                observation = _result_text(await session.call_tool(call["name"], call["arguments"]))
            on_event({"type": "observation", "step": step, "tool": call["name"], "text": observation})
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": observation})

    answer = f"Stopped: step limit of {max_steps} reached without a final answer."
    on_event({"type": "answer", "text": answer})
    return answer


def litellm_llm(model: str, api_base: str | None = None):
    import litellm

    def call(messages, tools):
        resp = litellm.completion(
            model=model, messages=messages, tools=tools, tool_choice="auto",
            api_base=api_base, temperature=0,
        )
        msg = resp.choices[0].message
        calls = [
            {"id": tc.id, "name": tc.function.name, "arguments": json.loads(tc.function.arguments or "{}")}
            for tc in (msg.tool_calls or [])
        ]
        return {"content": msg.content, "tool_calls": calls}

    return call

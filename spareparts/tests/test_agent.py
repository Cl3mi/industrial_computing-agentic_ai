import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent.config import resolve_backend
from agent.loop import run_agent


def test_openrouter_when_key_set():
    model, base = resolve_backend({"OPENROUTER_API_KEY": "k", "LLM_MODEL": "openrouter/x/y"})
    assert (model, base) == ("openrouter/x/y", None)


def test_ollama_fallback_without_key():
    model, base = resolve_backend({})
    assert model.startswith("ollama")
    assert base == "http://localhost:11434"


def test_ollama_overrides():
    model, base = resolve_backend({"OLLAMA_MODEL": "ollama_chat/m", "OLLAMA_API_BASE": "http://h:1"})
    assert (model, base) == ("ollama_chat/m", "http://h:1")


def _fake_llm():
    """Scripted LLM: look up, compute discount, log, answer. Checks that tool results are fed back."""
    step = {"n": 0}

    def llm(messages, tools):
        assert {t["function"]["name"] for t in tools} >= {"lookup_inventory", "audit_log"}
        step["n"] += 1
        if step["n"] == 1:
            return {"content": None, "tool_calls": [
                {"id": "c1", "name": "lookup_inventory", "arguments": {"query": "6204"}}]}
        if step["n"] == 2:
            assert messages[-1]["role"] == "tool" and "BRG-6204" in messages[-1]["content"]
            return {"content": None, "tool_calls": [
                {"id": "c2", "name": "calculate_volume_discount",
                 "arguments": {"unit_price": 3.4, "quantity": 800}}]}
        if step["n"] == 3:
            return {"content": None, "tool_calls": [
                {"id": "c3", "name": "audit_log",
                 "arguments": {"event_type": "quote", "details": "800 x BRG-6204"}}]}
        return {"content": "Total EUR 2448.00 with 10% discount.", "tool_calls": []}

    return llm


def test_react_loop_with_real_server(tmp_path):
    env = {**os.environ, "SPAREPARTS_DB": str(tmp_path / "i.db"), "SPAREPARTS_LOG": str(tmp_path / "a.log")}
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"], env=env)
    events = []

    async def go():
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                return await run_agent("Quote 800 x 6204", s, _fake_llm(), on_event=events.append)

    answer = asyncio.run(go())
    assert "2448" in answer
    assert [e["tool"] for e in events if e["type"] == "tool_call"] == [
        "lookup_inventory", "calculate_volume_discount", "audit_log"]
    assert "800 x BRG-6204" in (tmp_path / "a.log").read_text()


def test_loop_stops_at_max_steps():
    class FakeSession:
        async def list_tools(self):
            class R:
                tools = []
            return R()

    def looping_llm(messages, tools):
        return {"content": None, "tool_calls": [{"id": "x", "name": "nope", "arguments": {}}]}

    async def go():
        return await run_agent("q", FakeSession(), looping_llm, max_steps=2)

    # FakeSession has no call_tool: unknown tool names must be answered with an error, never sent to the session
    answer = asyncio.run(go())
    assert "step limit" in answer.lower()


def test_empty_list_result_is_visible_to_the_model():
    from types import SimpleNamespace

    from agent.loop import _result_text

    empty = SimpleNamespace(content=[], structuredContent={"result": []}, isError=False)
    assert _result_text(empty) == '{"result": []}'


def test_empty_final_reply_falls_back_to_last_thought():
    class FakeSession:
        async def list_tools(self):
            tool = type("T", (), {"name": "audit_log", "description": "", "inputSchema": {"type": "object"}})
            return type("R", (), {"tools": [tool]})()

        async def call_tool(self, name, args):
            content = [type("C", (), {"type": "text", "text": "logged"})()]
            return type("Res", (), {"content": content, "isError": False})()

    replies = iter([
        {"content": "1200 units from Nordlager GmbH.", "tool_calls": [{"id": "a", "name": "audit_log", "arguments": {}}]},
        {"content": None, "tool_calls": []},
    ])

    answer = asyncio.run(run_agent("q", FakeSession(), lambda messages, tools: next(replies)))
    assert answer == "1200 units from Nordlager GmbH."

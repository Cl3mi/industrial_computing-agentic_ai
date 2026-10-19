import asyncio
import json

import pytest

from a2a_agents import compliance_agent, inventory_agent, pricing_agent
from orchestrator.cli import ask
from orchestrator.gateway import Gateway, connect
from orchestrator.session import RegistryToolSession
from tests.fakes import FakeLiteLLM


@pytest.fixture
def network(tmp_path, monkeypatch):
    monkeypatch.setenv("SPAREPARTS_DB", str(tmp_path / "i.db"))
    monkeypatch.setenv("SPAREPARTS_LOG", str(tmp_path / "a.log"))
    monkeypatch.delenv("MCP_SERVER_URL", raising=False)
    return FakeLiteLLM({
        "id-inv": ("inventory-agent", inventory_agent),
        "id-pri": ("pricing-agent", pricing_agent),
        "id-com": ("compliance-agent", compliance_agent),
    })


def test_skills_become_tools(network):
    async def go():
        async with connect(network) as client:
            session = RegistryToolSession(Gateway(client))
            return (await session.list_tools()).tools, session.routes

    tools, routes = asyncio.run(go())
    assert {t.name for t in tools} == {"check_stock", "low_stock", "log_event", "quote", "check_order"}
    assert routes["quote"] == ("id-pri", "pricing-agent")
    assert all("input_json" in t.inputSchema["properties"] for t in tools)
    assert next(t for t in tools if t.name == "quote").description.startswith("[pricing-agent]")


def test_bad_json_is_reported_not_sent(network):
    async def go():
        async with connect(network) as client:
            session = RegistryToolSession(Gateway(client))
            await session.list_tools()
            return await session.call_tool("quote", {"input_json": "{not json"})

    result = asyncio.run(go())
    assert result.isError and "not valid JSON" in result.content[0].text
    assert network.calls == []


def _scripted_llm():
    """Plays the orchestrator LLM: stock -> quote -> compliance -> log -> answer, checking each observation."""
    step = {"n": 0}

    def llm(messages, tools):
        step["n"] += 1
        last = json.loads(messages[-1]["content"]) if messages[-1]["role"] == "tool" else None
        if step["n"] == 1:
            return _call("check_stock", {"query": "6204", "quantity": 800})
        if step["n"] == 2:
            part = last["parts"][0]
            assert part["sufficient"] is True
            return _call("quote", {"sku": part["sku"], "unit_price": part["unit_price"], "quantity": 800})
        if step["n"] == 3:
            assert last["total"] == 2448.0
            return _call("check_order", {"sku": "BRG-6204", "quantity": 800, "total": last["total"], "in_stock": True})
        if step["n"] == 4:
            assert last["approver"] == "purchasing manager"
            return _call("log_event", {"event_type": "order_review", "details": "800 x BRG-6204, EUR 2448, approval"})
        return {"content": "In stock; EUR 2448.00; 2 days; purchasing manager must approve.", "tool_calls": []}

    return llm


def _call(name, data):
    return {"content": None, "tool_calls": [{"id": name, "name": name, "arguments": {"input_json": json.dumps(data)}}]}


def test_orchestrator_end_to_end(network, tmp_path):
    events = []
    answer = asyncio.run(ask("Order 800 x 6204", on_event=events.append, llm=_scripted_llm(), transport=network))
    assert "2448" in answer
    acts = [(e["agent"], e["tool"]) for e in events if e["type"] == "tool_call"]
    assert acts == [("inventory-agent", "check_stock"), ("pricing-agent", "quote"),
                    ("compliance-agent", "check_order"), ("inventory-agent", "log_event")]
    assert network.calls == ["id-inv", "id-pri", "id-com", "id-inv"]
    assert "order_review" in (tmp_path / "a.log").read_text()

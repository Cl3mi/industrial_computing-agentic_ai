import asyncio

import httpx
import pytest

from a2a_agents import compliance_agent, inventory_agent, pricing_agent
from orchestrator.gateway import Gateway
from tests.fakes import FakeLiteLLM


@pytest.fixture
def mcp_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SPAREPARTS_DB", str(tmp_path / "i.db"))
    monkeypatch.setenv("SPAREPARTS_LOG", str(tmp_path / "a.log"))
    monkeypatch.delenv("MCP_SERVER_URL", raising=False)
    return tmp_path


def _send(module, payload):
    async def go():
        transport = FakeLiteLLM({"x": ("agent", module)})
        async with httpx.AsyncClient(base_url="http://proxy", transport=transport) as client:
            return await Gateway(client).send("x", payload)

    return asyncio.run(go())


def test_card_is_served_with_skills():
    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=inventory_agent.app), base_url="http://a") as c:
            return (await c.get("/.well-known/agent-card.json")).json()

    card = asyncio.run(go())
    assert card["name"] == "Inventory agent"
    assert [s["id"] for s in card["skills"]] == ["check_stock", "low_stock", "log_event"]
    assert card["supportedInterfaces"][0]["protocolBinding"] == "JSONRPC"


def test_pricing_quote():
    r = _send(pricing_agent, {"skill": "quote", "input": {"sku": "BRG-6204", "unit_price": 3.4, "quantity": 800}})
    assert r["total"] == 2448.0
    assert r["tier"] == "500+"
    assert r["sku"] == "BRG-6204"


def test_single_skill_agent_accepts_missing_skill_name():
    r = _send(pricing_agent, {"input": {"unit_price": 2.0, "quantity": 100}})
    assert r["discount_rate"] == 0.05


def test_errors_come_back_as_data():
    assert "ValueError" in _send(pricing_agent, {"skill": "quote", "input": {"unit_price": 0, "quantity": 5}})["error"]
    assert "unknown skill" in _send(inventory_agent, {"skill": "nope", "input": {}})["error"]
    assert "KeyError" in _send(pricing_agent, {"skill": "quote", "input": {}})["error"]


def test_compliance_check_order_coerces_types():
    r = _send(compliance_agent, {"skill": "check_order",
                                 "input": {"sku": "HYD-HOSE-2M", "quantity": "40", "total": "1940", "in_stock": "false"}})
    assert r["decision"] == "auto_approved"
    assert r["lead_time_days"] == 15
    assert r["in_stock"] is False


def test_inventory_check_stock_via_mcp(mcp_env):
    r = _send(inventory_agent, {"skill": "check_stock", "input": {"query": "6204", "quantity": 800}})
    part = r["parts"][0]
    assert part["sku"] == "BRG-6204"
    assert part["stock"] == 1200
    assert part["sufficient"] is True


def test_inventory_low_stock_and_log(mcp_env):
    low = _send(inventory_agent, {"skill": "low_stock", "input": {"threshold": 50}})
    assert low["parts"] and all(p["stock"] < 50 for p in low["parts"])
    rec = _send(inventory_agent, {"skill": "log_event", "input": {"event_type": "order_review", "details": "via a2a"}})
    assert rec["event_type"] == "order_review"
    assert "via a2a" in (mcp_env / "a.log").read_text()

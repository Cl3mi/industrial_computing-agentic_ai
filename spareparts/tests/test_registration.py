import asyncio
import json

import httpx

from a2a_agents.registration import register_with_retry, upsert_agent

CARD = {"name": "Pricing agent", "url": "http://pricing-agent:9102/", "skills": [{"id": "quote"}]}


def test_upsert_creates_new_agent():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path))
        assert request.headers["authorization"] == "Bearer sk-test"
        assert json.loads(request.content)["agent_card_params"] == CARD
        return httpx.Response(200, json={"agent_id": "a1"})

    async def go():
        return await register_with_retry("http://proxy", "sk-test", "pricing-agent", CARD,
                                         transport=httpx.MockTransport(handler))

    assert asyncio.run(go()) == "a1"
    assert seen == [("POST", "/v1/agents")]


def test_upsert_updates_existing_agent():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path))
        if request.method == "POST":
            return httpx.Response(400, json={"detail": "Agent with name pricing-agent already exists"})
        if request.method == "GET":
            return httpx.Response(200, json=[{"agent_id": "other", "agent_name": "x"},
                                             {"agent_id": "a7", "agent_name": "pricing-agent"}])
        return httpx.Response(200, json={"agent_id": "a7"})

    async def go():
        async with httpx.AsyncClient(base_url="http://proxy", transport=httpx.MockTransport(handler)) as c:
            return await upsert_agent(c, "pricing-agent", CARD)

    assert asyncio.run(go()) == "a7"
    assert seen == [("POST", "/v1/agents"), ("GET", "/v1/agents"), ("PUT", "/v1/agents/a7")]


def test_retries_until_proxy_is_up():
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise httpx.ConnectError("proxy not up yet")
        return httpx.Response(200, json={"agent_id": "a1"})

    async def go():
        return await register_with_retry("http://proxy", "k", "pricing-agent", CARD, delay=0,
                                         transport=httpx.MockTransport(handler))

    assert asyncio.run(go()) == "a1"
    assert attempts["n"] == 3


def test_gives_up_after_attempts():
    def handler(request):
        raise httpx.ConnectError("down")

    async def go():
        return await register_with_retry("http://proxy", "k", "pricing-agent", CARD, attempts=2, delay=0,
                                         transport=httpx.MockTransport(handler))

    assert asyncio.run(go()) is None

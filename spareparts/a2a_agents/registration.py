"""Self-registration of an agent card in the LiteLLM agent registry (create, or update if the name exists)."""

import asyncio
import logging

import httpx

log = logging.getLogger(__name__)


async def upsert_agent(client: httpx.AsyncClient, agent_name: str, card: dict) -> str:
    body = {"agent_name": agent_name, "agent_card_params": card}
    resp = await client.post("/v1/agents", json=body)
    if resp.status_code == 400 and "already exists" in resp.text:
        listing = await client.get("/v1/agents")
        listing.raise_for_status()
        agent_id = next(a["agent_id"] for a in listing.json() if a["agent_name"] == agent_name)
        resp = await client.put(f"/v1/agents/{agent_id}", json=body)
    resp.raise_for_status()
    return resp.json()["agent_id"]


async def register_with_retry(
    base_url: str, api_key: str, agent_name: str, card: dict,
    attempts: int = 60, delay: float = 2.0, transport: httpx.AsyncBaseTransport | None = None,
) -> str | None:
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=10, transport=transport) as client:
        for attempt in range(1, attempts + 1):
            try:
                agent_id = await upsert_agent(client, agent_name, card)
                log.info("registered %s in %s as %s", agent_name, base_url, agent_id)
                return agent_id
            except (httpx.HTTPError, StopIteration) as exc:
                log.warning("registration of %s failed (attempt %d/%d): %r", agent_name, attempt, attempts, exc)
                await asyncio.sleep(delay)
    log.error("giving up registering %s", agent_name)
    return None

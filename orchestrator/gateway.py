"""Client for the LiteLLM proxy in its role as A2A agent registry and gateway."""

import os
from uuid import uuid4

import httpx


def connect(transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=os.environ.get("LITELLM_URL", "http://127.0.0.1:4000"),
        headers={"Authorization": f"Bearer {os.environ.get('LITELLM_MASTER_KEY', 'sk-spareparts-local')}"},
        timeout=60,
        transport=transport,
    )


class Gateway:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def list_agents(self) -> list[dict]:
        resp = await self.client.get("/v1/agents")
        resp.raise_for_status()
        return resp.json()

    async def send(self, agent_id: str, payload: dict) -> dict:
        """Send one data part to an agent through the gateway (A2A 1.0 JSON-RPC) and return the reply data."""
        body = {
            "jsonrpc": "2.0",
            "id": str(uuid4()),
            "method": "SendMessage",
            "params": {"message": {"messageId": str(uuid4()), "role": "ROLE_USER", "parts": [{"data": payload}]}},
        }
        resp = await self.client.post(f"/a2a/{agent_id}", json=body, headers={"A2A-Version": "1.0"})
        resp.raise_for_status()
        reply = resp.json()
        if "error" in reply:
            return {"error": reply["error"].get("message", str(reply["error"]))}
        parts = reply["result"]["message"]["parts"]
        return next((p["data"] for p in parts if "data" in p), {"text": " ".join(p.get("text", "") for p in parts)})

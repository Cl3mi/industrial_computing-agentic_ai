"""In-process stand-in for the LiteLLM proxy: lists real agent cards and forwards A2A calls to the agent apps."""

import httpx

from a2a_agents.common import card_to_registry


class FakeLiteLLM(httpx.AsyncBaseTransport):
    def __init__(self, agents: dict):
        """agents: {agent_id: (agent_name, module with .app and .card)}"""
        self.agents = agents
        self.calls: list[str] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path == "/v1/agents":
            return httpx.Response(200, json=[
                {"agent_id": aid, "agent_name": name, "agent_card_params": card_to_registry(mod.card)}
                for aid, (name, mod) in self.agents.items()
            ])
        if request.method == "POST" and path.startswith("/a2a/"):
            agent_id = path.split("/")[2]
            self.calls.append(agent_id)
            app = self.agents[agent_id][1].app
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://agent") as client:
                resp = await client.post("/", content=await request.aread(),
                                         headers={"content-type": "application/json", "A2A-Version": "1.0"})
            return httpx.Response(resp.status_code, content=resp.content, headers={"content-type": "application/json"})
        return httpx.Response(404, json={"detail": "not found"})

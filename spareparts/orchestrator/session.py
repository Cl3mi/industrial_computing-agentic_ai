"""Makes the registry look like an MCP ClientSession, so agent.loop.run_agent can drive remote agents:
every skill of every registered agent becomes one tool, discovered at runtime."""

import json
from types import SimpleNamespace

INPUT_SCHEMA = {
    "type": "object",
    "properties": {"input_json": {"type": "string", "description": "JSON object with the fields named in the tool description"}},
    "required": ["input_json"],
}


def _result(text: str, error: bool = False):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], isError=error)


class RegistryToolSession:
    def __init__(self, gateway):
        self.gateway = gateway
        self.routes: dict[str, tuple[str, str]] = {}  # skill id -> (agent id, agent name)

    async def list_tools(self):
        tools, self.routes = [], {}
        for agent in await self.gateway.list_agents():
            for skill in agent["agent_card_params"].get("skills", []):
                self.routes[skill["id"]] = (agent["agent_id"], agent["agent_name"])
                tools.append(SimpleNamespace(
                    name=skill["id"],
                    description=f"[{agent['agent_name']}] {skill.get('description', '')}",
                    inputSchema=INPUT_SCHEMA,
                ))
        return SimpleNamespace(tools=tools)

    async def call_tool(self, name: str, arguments: dict):
        agent_id, _ = self.routes[name]
        try:
            data = json.loads(arguments.get("input_json") or "{}")
        except json.JSONDecodeError as exc:
            return _result(f"input_json is not valid JSON: {exc}", error=True)
        result = await self.gateway.send(agent_id, {"skill": name, "input": data})
        return _result(json.dumps(result), error="error" in result)

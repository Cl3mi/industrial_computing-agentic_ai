# Spare-Parts MCP Server and A2A Network (Industrial Computing, Homework 1 and 2, Option A)

MCP server for an industrial spare-parts distributor plus a ReAct agent that drives it through LiteLLM.

## Tools
| Tool | What it does |
|---|---|
| `lookup_inventory` | SQL lookup (sqlite3) in the product inventory by SKU, name or supplier |
| `calculate_volume_discount` | Tiered discount by order volume: 5 % from 100, 10 % from 500, 15 % from 1000 units |
| `audit_log` | Appends events to a local JSON-lines file; also readable as resource `audit://log` |
| `list_low_stock` | Parts below a stock threshold |

## Setup
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env   # add OPENROUTER_API_KEY, or run a local Ollama instead
set -a; . ./.env; set +a
pytest
```

On Debian/Ubuntu, `python3 -m venv` needs the `python3-venv` package. Without sudo, [uv](https://docs.astral.sh/uv/) works as well and installs the exact tested versions from `uv.lock`: `uv sync --extra dev && . .venv/bin/activate`.

## Run
```bash
# One question, server started over stdio by the agent
python -m agent.cli "A customer wants 800 units of BRG-6204. What is the total price?"

# Same server over Streamable HTTP
python -m mcp_server.server --transport streamable-http --port 8000
python -m agent.cli --server-url http://127.0.0.1:8000/mcp "Which parts are low on stock?"

# Three demo questions, traces saved to execution_logs/
python -m scripts.run_demo
```

## Evidence
See `execution_logs/` for full ReAct traces (thought, act, observe) of three different questions.

## Notes
LiteLLM is pinned to a current release (`>=1.105`) on purpose; old releases had a security incident.

## Homework 2: distributed A2A system

Three agents in separate containers, each with an A2A agent card, register themselves on startup in a LiteLLM proxy (agent registry + A2A gateway). The orchestrator looks them up at runtime and turns their skills into tools for its ReAct loop.

| Agent | Port | Skills |
|---|---|---|
| inventory-agent | 9101 | `check_stock`, `low_stock`, `log_event` (via the Homework 1 MCP server) |
| pricing-agent | 9102 | `quote` (tiered volume discount) |
| compliance-agent | 9103 | `check_order` (approval limits, lead times) |

```bash
docker compose up -d --build                      # db, litellm, mcp-server, 3 agents
docker compose run --rm orchestrator --list       # dynamic lookup in the registry
docker compose run --rm orchestrator --call quote '{"sku": "BRG-6204", "unit_price": 3.4, "quantity": 800}'
docker compose run --rm orchestrator "A customer orders 800 units of BRG-6204. Can we deliver, at what price, and who approves?"
docker compose run --rm --entrypoint python orchestrator -m scripts.run_a2a_demo   # traces to execution_logs/
docker compose down                               # add -v to wipe registry and inventory
```

Agent cards: `http://127.0.0.1:910{1,2,3}/.well-known/agent-card.json`. The orchestrator needs `OPENROUTER_API_KEY` (or Ollama) in `.env`; `--list` and `--call` work without an LLM.

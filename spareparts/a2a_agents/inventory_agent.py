"""Inventory agent: wraps the Homework 1 MCP server and talks MCP to it.
Uses Streamable HTTP when MCP_SERVER_URL is set (Docker), otherwise starts the server over stdio."""

import json
import os
import sys
from contextlib import asynccontextmanager

from a2a.types import AgentSkill
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

from .common import build_app, make_card


@asynccontextmanager
async def mcp_session():
    url = os.environ.get("MCP_SERVER_URL")
    if url:
        async with streamablehttp_client(url) as (r, w, _):
            async with ClientSession(r, w) as session:
                await session.initialize()
                yield session
    else:
        params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"], env=dict(os.environ))
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                yield session


async def call_tool(name: str, arguments: dict):
    async with mcp_session() as session:
        result = await session.call_tool(name, arguments)
    text = "\n".join(c.text for c in result.content if getattr(c, "type", "") == "text")
    if result.isError:
        raise RuntimeError(text)
    if result.structuredContent is not None:  # list results arrive as {"result": [...]}
        return result.structuredContent.get("result", result.structuredContent)
    return json.loads(text)


async def check_stock(data: dict) -> dict:
    rows = await call_tool("lookup_inventory", {"query": str(data["query"]), "limit": 5})
    quantity = int(data["quantity"]) if data.get("quantity") is not None else None
    if quantity is not None:
        for row in rows:
            row["sufficient"] = row["stock"] >= quantity
    return {"query": data["query"], "requested_quantity": quantity, "parts": rows}


async def low_stock(data: dict) -> dict:
    threshold = int(data.get("threshold", 50))
    return {"threshold": threshold, "parts": await call_tool("list_low_stock", {"threshold": threshold})}


async def log_event(data: dict) -> dict:
    return await call_tool("audit_log", {"event_type": str(data["event_type"]), "details": str(data["details"])})


card = make_card(
    name="Inventory agent",
    description="Stock levels, unit prices and suppliers from the spare-parts inventory (via MCP); audit logging.",
    url=os.environ.get("PUBLIC_URL", "http://127.0.0.1:9101/"),
    skills=[
        AgentSkill(
            id="check_stock",
            name="Stock check",
            description='Input: {"query": str (one short keyword: a part number such as 6204 or one word of the '
                        'name), "quantity": int (optional)}. '
                        "Returns matching parts with sku, name, stock, unit_price (EUR), supplier and, "
                        "if quantity is given, sufficient (stock covers the quantity).",
            tags=["inventory", "stock"],
            examples=['{"query": "6204", "quantity": 800}'],
        ),
        AgentSkill(
            id="low_stock",
            name="Low-stock list",
            description='Input: {"threshold": int (default 50)}. Returns parts whose stock is below the threshold.',
            tags=["inventory", "stock"],
            examples=['{"threshold": 50}'],
        ),
        AgentSkill(
            id="log_event",
            name="Audit log entry",
            description='Input: {"event_type": str, "details": str}. Appends an event to the procurement audit log.',
            tags=["audit", "log"],
            examples=['{"event_type": "order_review", "details": "800 x BRG-6204, EUR 2448, needs approval"}'],
        ),
    ],
)
app = build_app(card, {"check_stock": check_stock, "low_stock": low_stock, "log_event": log_event},
                agent_name="inventory-agent")

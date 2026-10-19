import asyncio
import json
import os
import socket
import subprocess
import sys
import time

import httpx

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _params(tmp_path):
    env = {**os.environ, "SPAREPARTS_DB": str(tmp_path / "i.db"), "SPAREPARTS_LOG": str(tmp_path / "a.log")}
    return StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"], env=env)


def test_stdio_roundtrip(tmp_path):
    async def go():
        async with stdio_client(_params(tmp_path)) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                tools = {t.name for t in (await s.list_tools()).tools}
                disc = await s.call_tool("calculate_volume_discount", {"unit_price": 3.4, "quantity": 800})
                found = await s.call_tool("lookup_inventory", {"query": "6204"})
                await s.call_tool("audit_log", {"event_type": "quote", "details": "test entry"})
                log = await s.read_resource("audit://log")
                return tools, disc, found, log

    tools, disc, found, log = asyncio.run(go())
    assert {"lookup_inventory", "calculate_volume_discount", "audit_log", "list_low_stock"} <= tools
    assert json.loads(disc.content[0].text)["total"] == 2448.0
    assert json.loads(found.content[0].text)["sku"] == "BRG-6204"
    assert "test entry" in log.contents[0].text


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_http_allowed_host(tmp_path):
    port = _free_port()
    env = {**os.environ, "SPAREPARTS_DB": str(tmp_path / "i.db"), "SPAREPARTS_LOG": str(tmp_path / "a.log")}
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_server.server", "--transport", "streamable-http", "--host", "127.0.0.1",
         "--port", str(port), "--allowed-host", "mcp-server:8000"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
    headers = {"Accept": "application/json, text/event-stream"}

    def post(host):
        return httpx.post(f"http://127.0.0.1:{port}/mcp", json=init, headers={**headers, "Host": host}, timeout=5)

    try:
        for _ in range(50):
            try:
                post(f"127.0.0.1:{port}")
                break
            except httpx.ConnectError:
                time.sleep(0.2)
        assert post("mcp-server:8000").status_code == 200
        assert post("evil.example:8000").status_code == 421
    finally:
        proc.terminate()
        proc.wait(timeout=10)

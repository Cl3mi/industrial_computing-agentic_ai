"""MCP server for spare-parts procurement. Thin wrapper over inventory, discount and auditlog."""

import argparse
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from . import auditlog, discount, inventory

mcp = FastMCP("spareparts")


def _db() -> Path:
    return Path(os.environ.get("SPAREPARTS_DB", "data/inventory.db"))


def _log() -> Path:
    return Path(os.environ.get("SPAREPARTS_LOG", "data/audit.log"))


@mcp.tool()
def lookup_inventory(query: str, limit: int = 10) -> list[dict]:
    """Search the product inventory by SKU, part name or supplier (substring match).
    Use one short keyword such as a part number ('6204') or a word ('hydraulic'); a longer phrase
    only matches if it appears verbatim. Returns sku, name, stock, unit_price (EUR) and supplier."""
    return inventory.lookup_inventory(_db(), query, limit)


@mcp.tool()
def calculate_volume_discount(unit_price: float, quantity: int) -> dict:
    """Compute the order total with tiered volume discount:
    5% from 100 units, 10% from 500, 15% from 1000. Prices in EUR."""
    return discount.calculate_volume_discount(unit_price, quantity)


@mcp.tool()
def audit_log(event_type: str, details: str) -> dict:
    """Append an event (for example 'quote' or 'inquiry') to the procurement audit log."""
    return auditlog.append_event(_log(), event_type, details)


@mcp.tool()
def list_low_stock(threshold: int = 50) -> list[dict]:
    """List parts whose stock is below the threshold, lowest first."""
    return inventory.list_low_stock(_db(), threshold)


@mcp.resource("audit://log")
def audit_log_resource() -> str:
    """The full audit log as JSON lines."""
    return auditlog.read_text(_log())


def main() -> None:
    parser = argparse.ArgumentParser(description="Spare-parts MCP server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--allowed-host", action="append", default=[],
        help="Extra Host header accepted over HTTP, e.g. mcp-server:8000 (repeatable)",
    )
    args = parser.parse_args()
    inventory.init_db(_db())
    if args.transport == "streamable-http":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        if args.allowed_host:  # FastMCP only accepts localhost Host headers by default
            mcp.settings.transport_security = TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", *args.allowed_host],
            )
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()

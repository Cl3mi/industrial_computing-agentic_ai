"""Compliance and logistics agent: approval limits and lead times for an order."""

import os

from a2a.types import AgentSkill

from . import compliance
from .common import build_app, make_card


def _as_bool(value) -> bool:
    return value if isinstance(value, bool) else str(value).strip().lower() in ("true", "1", "yes")


async def check_order(data: dict) -> dict:
    return compliance.check_order(
        sku=str(data["sku"]), quantity=int(data["quantity"]),
        total=float(data["total"]), in_stock=_as_bool(data["in_stock"]),
    )


card = make_card(
    name="Compliance agent",
    description="Checks orders against approval limits and estimates lead times.",
    url=os.environ.get("PUBLIC_URL", "http://127.0.0.1:9103/"),
    skills=[AgentSkill(
        id="check_order",
        name="Approval and lead-time check",
        description='Input: {"sku": str, "quantity": int, "total": float (EUR, after discount), '
                    '"in_stock": bool (true if stock covers the quantity)}. Returns approval_required, approver, '
                    "lead_time_days and decision. Orders from EUR 2000 need the purchasing manager, "
                    "from EUR 10000 the head of procurement.",
        tags=["compliance", "approval", "logistics", "lead-time"],
        examples=['{"sku": "BRG-6204", "quantity": 800, "total": 2448.0, "in_stock": true}'],
    )],
)
app = build_app(card, {"check_order": check_order}, agent_name="compliance-agent")

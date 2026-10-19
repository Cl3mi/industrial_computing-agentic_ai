"""Pricing agent: volume-discount quotes, reusing the Homework 1 discount engine."""

import os

from a2a.types import AgentSkill

from mcp_server import discount

from .common import build_app, make_card


async def quote(data: dict) -> dict:
    result = discount.calculate_volume_discount(float(data["unit_price"]), int(data["quantity"]))
    return {"sku": data.get("sku"), **result}


card = make_card(
    name="Pricing agent",
    description="Prices spare-part orders with tiered volume discounts (EUR).",
    url=os.environ.get("PUBLIC_URL", "http://127.0.0.1:9102/"),
    skills=[AgentSkill(
        id="quote",
        name="Volume discount quote",
        description='Input: {"sku": str, "unit_price": float, "quantity": int}. Returns tier, discount_rate, '
                    "gross, discount_amount and total in EUR. Tiers: 5% from 100, 10% from 500, 15% from 1000 units.",
        tags=["pricing", "discount"],
        examples=['{"sku": "BRG-6204", "unit_price": 3.4, "quantity": 800}'],
    )],
)
app = build_app(card, {"quote": quote}, agent_name="pricing-agent")

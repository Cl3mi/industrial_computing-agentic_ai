"""Tiered volume discount. Tiers are checked from the highest minimum quantity down."""

TIERS = [(1000, 0.15, "1000+"), (500, 0.10, "500+"), (100, 0.05, "100+"), (1, 0.0, "1+")]


def calculate_volume_discount(unit_price: float, quantity: int) -> dict:
    if unit_price <= 0:
        raise ValueError("unit_price must be greater than 0")
    if quantity <= 0:
        raise ValueError("quantity must be greater than 0")
    _, rate, label = next(tier for tier in TIERS if quantity >= tier[0])
    gross = round(unit_price * quantity, 2)
    discount_amount = round(gross * rate, 2)
    return {
        "unit_price": unit_price,
        "quantity": quantity,
        "tier": label,
        "discount_rate": rate,
        "gross": gross,
        "discount_amount": discount_amount,
        "total": round(gross - discount_amount, 2),
    }

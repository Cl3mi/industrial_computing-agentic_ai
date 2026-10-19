"""Order compliance rules: approval limits and lead times. Pure functions, no I/O."""

# Order totals (EUR) at or above a limit need that approver; checked from the highest limit down.
APPROVAL_LIMITS = [(10000.0, "head of procurement"), (2000.0, "purchasing manager")]
IN_STOCK_LEAD_DAYS = 2
BACKORDER_LEAD_DAYS = {"BRG": 10, "HYD": 15, "MOT": 20, "SNS": 7, "BLT": 5, "FLT": 5}
DEFAULT_BACKORDER_DAYS = 14


def required_approver(total: float) -> str | None:
    for limit, approver in APPROVAL_LIMITS:
        if total >= limit:
            return approver
    return None


def lead_time_days(sku: str, in_stock: bool) -> int:
    if in_stock:
        return IN_STOCK_LEAD_DAYS
    return BACKORDER_LEAD_DAYS.get(sku.split("-")[0].upper(), DEFAULT_BACKORDER_DAYS)


def check_order(sku: str, quantity: int, total: float, in_stock: bool) -> dict:
    if quantity <= 0:
        raise ValueError("quantity must be greater than 0")
    if total < 0:
        raise ValueError("total must not be negative")
    approver = required_approver(total)
    return {
        "sku": sku,
        "quantity": quantity,
        "total": total,
        "in_stock": in_stock,
        "approval_required": approver is not None,
        "approver": approver,
        "lead_time_days": lead_time_days(sku, in_stock),
        "decision": "needs_approval" if approver else "auto_approved",
    }

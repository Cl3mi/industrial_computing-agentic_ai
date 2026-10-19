import pytest

from a2a_agents import compliance


@pytest.mark.parametrize("total, approver", [
    (0.0, None), (1999.99, None), (2000.0, "purchasing manager"), (9999.99, "purchasing manager"),
    (10000.0, "head of procurement"), (50000.0, "head of procurement"),
])
def test_approval_limits(total, approver):
    assert compliance.required_approver(total) == approver


def test_lead_times():
    assert compliance.lead_time_days("HYD-HOSE-2M", in_stock=True) == 2
    assert compliance.lead_time_days("HYD-HOSE-2M", in_stock=False) == 15
    assert compliance.lead_time_days("XYZ-1", in_stock=False) == compliance.DEFAULT_BACKORDER_DAYS


def test_check_order_800_bearings():
    r = compliance.check_order("BRG-6204", 800, 2448.0, in_stock=True)
    assert r["decision"] == "needs_approval"
    assert r["approver"] == "purchasing manager"
    assert r["lead_time_days"] == 2


@pytest.mark.parametrize("qty, total", [(0, 10.0), (-1, 10.0), (5, -1.0)])
def test_check_order_rejects_invalid(qty, total):
    with pytest.raises(ValueError):
        compliance.check_order("BRG-6204", qty, total, in_stock=True)

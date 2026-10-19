import pytest

from mcp_server.discount import calculate_volume_discount


@pytest.mark.parametrize(
    "quantity, rate",
    [(1, 0.0), (99, 0.0), (100, 0.05), (499, 0.05), (500, 0.10), (999, 0.10), (1000, 0.15), (5000, 0.15)],
)
def test_tier_boundaries(quantity, rate):
    assert calculate_volume_discount(2.0, quantity)["discount_rate"] == rate


def test_800_bearings_at_3_40():
    r = calculate_volume_discount(3.40, 800)
    assert r["gross"] == 2720.0
    assert r["discount_amount"] == 272.0
    assert r["total"] == 2448.0
    assert r["tier"] == "500+"


@pytest.mark.parametrize("price, qty", [(0, 10), (-1, 10), (1.0, 0), (1.0, -5)])
def test_rejects_non_positive_input(price, qty):
    with pytest.raises(ValueError):
        calculate_volume_discount(price, qty)

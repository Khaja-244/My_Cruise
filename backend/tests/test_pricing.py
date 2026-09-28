"""Small unit tests for the booking price calculator."""

from app.services.pricing_service import calculate_price


def test_price_includes_extra_guest_and_port_fee():
    """A second guest adds the extra-guest charge plus the port fee."""
    result = calculate_price(
        inventory_prices=[10_000],
        extra_prices=[2_000],
        occupancies=[2],
        port_fee_per_guest_cents=500,
    )

    assert result == (12_000, 0, 13_000)

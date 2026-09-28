"""Small, deterministic booking price calculator."""

from decimal import Decimal, ROUND_HALF_UP

from app.core.config import settings


def calculate_price(
    inventory_prices: list[int],
    extra_prices: list[int],
    occupancies: list[int],
    port_fee_per_guest_cents: int,
):
    """Return subtotal, tax, and final total in cents.

    Each cabin contributes its inventory price plus an extra-guest charge for
    guests above the first guest in that cabin. Port fees are charged per guest.
    """
    subtotal = sum(
        price + max(0, occupancy - 1) * extra_price
        for price, extra_price, occupancy in zip(
            inventory_prices,
            extra_prices,
            occupancies,
        )
    )
    guest_count = sum(occupancies)
    port_fee = port_fee_per_guest_cents * guest_count
    tax = int(
        (Decimal(subtotal) * settings.TAX_RATE).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )

    return subtotal, tax, subtotal + port_fee + tax

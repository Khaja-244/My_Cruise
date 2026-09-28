"""Unit tests for human-friendly booking references."""

from app.services.booking_service import booking_ref


def test_reference_excludes_ambiguous_characters():
    """Booking references should avoid characters that are easy to confuse."""
    assert not set(booking_ref()) & set("01OI")

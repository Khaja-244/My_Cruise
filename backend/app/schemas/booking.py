"""Request and response models used by the booking workflow."""
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, model_validator

class GuestIn(BaseModel):
    """Passenger details required before a cabin can be held."""
    cabin_id: str
    full_name: str = Field(min_length=2, max_length=160)
    date_of_birth: date
    gender: str | None = Field(default=None, max_length=40)
    nationality: str = Field(min_length=2, max_length=100)
    passport_number: str = Field(min_length=5, max_length=30)
    is_lead_guest: bool = False

    @field_validator("full_name", "nationality", "passport_number")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This passenger field is required.")
        return value

    @field_validator("passport_number")
    @classmethod
    def normalize_passport(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_birth_date(self):
        if self.date_of_birth > date.today():
            raise ValueError("Date of birth cannot be in the future.")
        return self

class CabinSelection(BaseModel):
    """One selected cabin and the number of guests assigned to it."""
    cabin_id: str
    occupancy: int = Field(gt=0)

class HoldIn(BaseModel):
    """Payload used to temporarily hold cabins before payment."""
    sailing_id: str
    cabins: list[CabinSelection] = Field(min_length=1, max_length=20)
    guests: list[GuestIn] = Field(min_length=1, max_length=50)

    @model_validator(mode='after')
    def validate_guest_mapping(self):
        """Ensure every guest belongs to a selected cabin exactly as expected."""
        cabin_ids = {cabin.cabin_id for cabin in self.cabins}
        guest_ids = [guest.cabin_id for guest in self.guests]
        if any((cabin_id not in cabin_ids for cabin_id in guest_ids)):
            raise ValueError('Every guest must belong to a selected cabin.')
        expected = {cabin.cabin_id: cabin.occupancy for cabin in self.cabins}
        actual = {cabin_id: guest_ids.count(cabin_id) for cabin_id in cabin_ids}
        if any((actual[cabin_id] != occupancy for cabin_id, occupancy in expected.items())):
            raise ValueError('Guest count must match the occupancy selected for each cabin.')
        if sum((bool(guest.is_lead_guest) for guest in self.guests)) != 1:
            raise ValueError('Exactly one lead guest is required.')
        return self

class BookingOut(BaseModel):
    """Small booking response used immediately after a hold is created."""
    reference: str
    status: str
    sailing_id: str
    guest_count: int
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    currency: str
    hold_expires_at: str | None

class PaymentIntentIn(BaseModel):
    booking_reference: str

class PaymentIntentOut(BaseModel):
    client_secret: str

class CancelIn(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)

class RefundPreview(BaseModel):
    booking_reference: str
    total_cents: int
    refund_cents: int
    refund_percent: Decimal
    flat_fee_cents: int
    days_before_departure: int

class AdminCancelReview(BaseModel):
    final_refund_cents: int | None = None
    admin_note: str | None = None

class AdminReject(BaseModel):
    admin_note: str = Field(min_length=2)

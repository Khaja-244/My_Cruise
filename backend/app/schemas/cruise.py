"""Pydantic models for cruises, sailings, cabins, and availability."""
from datetime import date, datetime, time
from pydantic import BaseModel, Field

class CruiseCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    sailing_days: int = Field(gt=0)
    ship_id: str
    embark_port_id: str
    disembark_port_id: str
    base_price_cents: int = Field(ge=0)
    is_featured: bool = False

class CruisePatch(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    sailing_days: int | None = None
    base_price_cents: int | None = None
    is_featured: bool | None = None
    approval_status: str | None = None
    ship_id: str | None = None
    embark_port_id: str | None = None
    disembark_port_id: str | None = None

class ShipCreate(BaseModel):
    name: str
    operator_name: str
    deck_count: int = Field(gt=0)
    description: str | None = None

class PortCreate(BaseModel):
    name: str
    city: str
    country: str
    code: str
    timezone: str

class CabinTypeCreate(BaseModel):
    name: str
    description: str | None = None
    max_occupancy: int = Field(gt=0)
    base_price_cents: int = Field(ge=0)
    price_per_extra_guest_cents: int = Field(ge=0)

class DeckCreate(BaseModel):
    deck_number: int
    name: str

class CabinCreate(BaseModel):
    deck_id: str
    cabin_type_id: str
    cabin_number: str
    max_occupancy: int = Field(gt=0)

class SailingCreate(BaseModel):
    cruise_id: str
    departure_date: date
    return_date: date
    booking_closes_at: datetime
    port_fee_per_guest_cents: int = Field(ge=0)

class SailingPatch(BaseModel):
    status: str

class ImageCreate(BaseModel):
    url: str
    alt_text: str | None = None
    sort_order: int = 0
    is_cover: bool = False

class ItineraryItem(BaseModel):
    day_number: int
    port_id: str | None = None
    arrival_time: time | None = None
    departure_time: time | None = None
    description: str | None = None

class SailingUpdate(BaseModel):
    departure_date: date | None = None
    return_date: date | None = None
    booking_closes_at: datetime | None = None
    port_fee_per_guest_cents: int | None = Field(default=None, ge=0)
    status: str | None = None

class DeckUpdate(BaseModel):
    deck_number: int | None = None
    name: str | None = None

class CabinUpdate(BaseModel):
    deck_id: str | None = None
    cabin_type_id: str | None = None
    cabin_number: str | None = None
    max_occupancy: int | None = Field(default=None, gt=0)

class ImageUpdate(BaseModel):
    url: str | None = None
    alt_text: str | None = None
    sort_order: int | None = None
    is_cover: bool | None = None

class AvailabilityCabin(BaseModel):
    """One physical cabin and its live inventory status for a sailing."""
    cabin_id: str
    cabin_number: str
    status: str
    price_cents: int
    max_occupancy: int

class AvailabilityType(BaseModel):
    cabin_type_id: str
    name: str
    max_occupancy: int
    base_price_cents: int
    price_per_extra_guest_cents: int = 0
    amenities: list[dict]
    cabins: list[AvailabilityCabin]

class AvailabilityDeck(BaseModel):
    deck_id: str
    deck_number: int
    name: str
    cabin_types: list[AvailabilityType]

class AvailabilityOut(BaseModel):
    """Live deck plan data used by the traveler booking screen."""
    sailing_id: str
    departure_date: date
    return_date: date
    booking_closes_at: datetime
    port_fee_per_guest_cents: int = 0
    tax_rate: float = 0.0
    decks: list[AvailabilityDeck]
    summary: dict

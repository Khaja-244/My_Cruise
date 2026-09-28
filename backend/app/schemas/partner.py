from datetime import date
from pydantic import field_validator, model_validator, BaseModel, Field, HttpUrl, EmailStr

class PartnerApplicationCreate(BaseModel):
    business_name: str = Field(min_length=2, max_length=200)
    contact_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    documents: dict | None = None

class ReviewApplication(BaseModel):
    approved: bool
    reason: str | None = Field(default=None, max_length=1000)

class PartnerStatusUpdate(BaseModel):
    status: str

class AdminPartnerCreate(BaseModel):
    business_name: str = Field(min_length=2, max_length=200)
    contact_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)

class PartnerCruiseCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=220)
    description: str | None = None
    ship_id: str | None = None
    ship_name: str | None = Field(default=None, max_length=160)
    operator_name: str | None = Field(default=None, max_length=160)
    sailing_days: int = Field(gt=0)
    start_sailing_date: date | None = None
    return_date: date | None = None
    embark_port_id: str
    disembark_port_id: str
    base_price_cents: int = Field(ge=0)

class PartnerCruiseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    slug: str | None = Field(default=None, min_length=2, max_length=220)
    description: str | None = None
    sailing_days: int | None = Field(default=None, gt=0)
    start_sailing_date: date | None = None
    return_date: date | None = None
    base_price_cents: int | None = Field(default=None, ge=0)
    embark_port_id: str | None = None
    disembark_port_id: str | None = None

class PartnerShipCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    operator_name: str = Field(min_length=2, max_length=160)
    deck_count: int = Field(ge=1)
    description: str | None = None

class PartnerDeckCreate(BaseModel):
    deck_number: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=100)

class PartnerDeckUpdate(BaseModel):
    deck_number: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=100)

class PartnerCabinTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = None
    max_occupancy: int = Field(gt=0)
    base_price_cents: int = Field(ge=0)
    price_per_extra_guest_cents: int = Field(ge=0)
    amenity_ids: list[str] = Field(default_factory=list)

class PartnerCabinTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = None
    max_occupancy: int | None = Field(default=None, gt=0)
    base_price_cents: int | None = Field(default=None, ge=0)
    price_per_extra_guest_cents: int | None = Field(default=None, ge=0)
    amenity_ids: list[str] | None = None

class PartnerCabinCreate(BaseModel):
    deck_id: str
    cabin_type_id: str
    cabin_number: str = Field(min_length=1, max_length=40)
    max_occupancy: int = Field(gt=0)

class PartnerCabinUpdate(BaseModel):
    deck_id: str | None = None
    cabin_type_id: str | None = None
    cabin_number: str | None = Field(default=None, min_length=1, max_length=40)
    max_occupancy: int | None = Field(default=None, gt=0)

class PartnerImageCreate(BaseModel):
    url: str
    alt_text: str | None = None
    sort_order: int = 0
    is_cover: bool = False

class PartnerImageUpdate(BaseModel):
    url: str | None = None
    alt_text: str | None = None
    sort_order: int | None = None
    is_cover: bool | None = None

class PartnerItineraryItem(BaseModel):
    day_number: int = Field(gt=0)
    port_id: str | None = None
    arrival_time: str | None = None
    departure_time: str | None = None
    description: str | None = None

class PartnerSailingCreate(BaseModel):
    departure_date: date
    return_date: date
    booking_closes_at: str
    port_fee_per_guest_cents: int = Field(ge=0)

class PartnerSailingUpdate(BaseModel):
    departure_date: date | None = None
    return_date: date | None = None
    booking_closes_at: str | None = None
    port_fee_per_guest_cents: int | None = Field(default=None, ge=0)

class CommissionUpdate(BaseModel):
    commission_type: str
    commission_value: float = Field(ge=0)

class WebsiteCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    website_url: HttpUrl

class WebsiteStatusUpdate(BaseModel):
    integration_status: str

class ExposureUpdate(BaseModel):
    enabled: bool

class PartnerGuest(BaseModel):
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

class PartnerBookingCabin(BaseModel):
    cabin_id: str
    occupancy: int = Field(gt=0)

class PartnerBookingRequest(BaseModel):
    sailing_id: str
    cabin_ids: list[str] = Field(default_factory=list)
    cabins: list[PartnerBookingCabin] = Field(default_factory=list)
    guest_count: int = Field(gt=0)
    customer_name: str = Field(min_length=2, max_length=160)
    customer_email: EmailStr
    customer_phone: str | None = Field(default=None, max_length=40)
    guests: list[PartnerGuest] = Field(default_factory=list)

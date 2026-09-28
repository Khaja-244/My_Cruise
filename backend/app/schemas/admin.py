from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class AdminUserStatus(BaseModel):
    is_active: bool


class RefundRuleIn(BaseModel):
    """One refund-policy range configured by an administrator."""

    min_days_before_departure: int = Field(ge=0)
    max_days_before_departure: int | None = None
    refund_percent: Decimal = Field(
        ge=Decimal("0"),
        le=Decimal("100"),
    )
    flat_fee_cents: int = Field(ge=0)


class RefundPolicyPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None


class RefundPolicyCreate(BaseModel):
    name: str
    description: str | None = None
    is_default: bool = False
    is_active: bool = True
    rules: list[RefundRuleIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ranges(self):
        """Ensure refund ranges are valid and do not overlap."""
        ordered = sorted(
            self.rules,
            key=lambda rule: rule.min_days_before_departure,
        )

        for index, rule in enumerate(ordered):
            if (
                rule.max_days_before_departure is not None
                and rule.max_days_before_departure < rule.min_days_before_departure
            ):
                raise ValueError("Refund rule max days must be >= min days.")

            previous_rule = ordered[index - 1] if index else None
            if previous_rule and (
                previous_rule.max_days_before_departure is None
                or previous_rule.max_days_before_departure
                >= rule.min_days_before_departure
            ):
                raise ValueError("Refund policy ranges must not overlap.")

        return self

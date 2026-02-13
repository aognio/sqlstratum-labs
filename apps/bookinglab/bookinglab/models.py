from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class BookingStatus(str, Enum):
    requested = "requested"
    confirmed = "confirmed"
    canceled = "canceled"


class EventCreate(BaseModel):
    slug: str = Field(min_length=3, max_length=80)
    title: str = Field(min_length=3, max_length=200)
    description: Optional[str] = None
    location: Optional[str] = None
    starts_at: datetime
    ends_at: datetime
    capacity: int = Field(gt=0)
    price_cents: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_ends_after_starts(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class EventOut(BaseModel):
    id: int
    slug: str
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    starts_at: datetime
    ends_at: datetime
    capacity: int
    price_cents: int
    created_at: datetime
    seats_booked: int = 0
    revenue_cents: int = 0
    remaining_capacity: int = 0

    @field_validator("seats_booked", "revenue_cents", "remaining_capacity", mode="before")
    @classmethod
    def _coerce_none_ints(cls, value):
        return 0 if value is None else value


class AttendeeCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    phone: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, value: Optional[str]):
        if value is None or value == "":
            return None
        import re

        if not re.match(r"^[0-9+() .-]{7,20}$", value):
            raise ValueError("phone must be a valid phone-like string")
        return value


class AttendeeOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    created_at: datetime


class BookingCreate(BaseModel):
    event_id: int
    seats: int
    notes: Optional[str] = None
    attendees: List[AttendeeCreate]

    @field_validator("seats")
    @classmethod
    def _validate_seats(cls, value: int):
        if value <= 0 or value > 10:
            raise ValueError("seats must be between 1 and 10")
        return value


class BookingOut(BaseModel):
    id: int
    event_id: int
    booking_code: str
    status: BookingStatus
    seats: int
    notes: Optional[str] = None
    created_at: datetime
    event: EventOut
    attendees: List[AttendeeOut]

    @field_validator("booking_code")
    @classmethod
    def _validate_booking_code(cls, value: str):
        import re

        if not re.match(r"^BK[0-9A-Z]{6}$", value):
            raise ValueError("booking_code format is invalid")
        return value

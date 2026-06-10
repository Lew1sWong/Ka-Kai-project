from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Mode = Literal["price_dna", "economic_dna", "social_dna"]


class HeroCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    start_date: date
    end_date: date
    title: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("ticker is required")
        return normalized

    @field_validator("title", "notes")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class SearchRunCreate(BaseModel):
    mode: Mode = "price_dna"

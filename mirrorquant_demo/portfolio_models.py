"""ORM models for Module C — Portfolio Risk-Assistance Analysis.

A ``Portfolio`` is owned by a user and groups a set of ``Holding`` rows. Holdings
carry an optional target weight (0..1), share count, and sector. Weights drive the
risk-assistance analytics in :mod:`mirrorquant_demo.portfolio_service`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mirrorquant_demo.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
    )

    holdings: Mapped[list["Holding"]] = relationship(
        back_populates="portfolio",
        cascade="all, delete-orphan",
        order_by="Holding.id",
    )


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), index=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    shares: Mapped[float | None] = mapped_column(Float, nullable=True)
    sector: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    portfolio: Mapped[Portfolio] = relationship(back_populates="holdings")

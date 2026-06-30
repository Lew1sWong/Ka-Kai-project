"""Investment-Hypothesis Management models.

Two tables backing Module B:

  - ``Hypothesis`` — a research thesis on a ticker (optionally tied to a Hero),
    with its core assumptions, validation metrics, and falsification conditions.
  - ``HypothesisEvent`` — an append-only activity trail for a hypothesis
    (creation, notes, metric updates, status changes, reviews).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mirrorquant_demo.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Hypothesis(Base):
    __tablename__ = "hypotheses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    hero_id: Mapped[int | None] = mapped_column(ForeignKey("heroes.id"), nullable=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(255))
    thesis: Mapped[str] = mapped_column(Text)
    core_assumptions: Mapped[list] = mapped_column(JSON, default=list)
    validation_metrics: Mapped[list] = mapped_column(JSON, default=list)
    falsification_conditions: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="open")
    conviction: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
    )

    events: Mapped[list["HypothesisEvent"]] = relationship(
        back_populates="hypothesis",
        cascade="all, delete-orphan",
        order_by="desc(HypothesisEvent.created_at)",
    )


class HypothesisEvent(Base):
    __tablename__ = "hypothesis_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hypothesis_id: Mapped[int] = mapped_column(ForeignKey("hypotheses.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(Text)
    detail_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    hypothesis: Mapped[Hypothesis] = relationship(back_populates="events")

"""Data-diode staging model.

An :class:`IntelligencePacket` is a unit of *public* intelligence collected by
the External Intelligence Machine and held in the staging area. It can only ever
move in ONE direction — from the external machine into the internal knowledge
base — via the one-way transfer gate in :mod:`mirrorquant_demo.data_diode`.
There is deliberately no model or path for moving internal data outward.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from mirrorquant_demo.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IntelligencePacket(Base):
    """A staged unit of public external intelligence awaiting one-way transfer."""

    __tablename__ = "diode_packets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source: Mapped[str] = mapped_column(String(255), index=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    classification: Mapped[str] = mapped_column(String(32), default="public")
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    # staged -> transferred | rejected
    status: Mapped[str] = mapped_column(String(32), default="staged", index=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # kb_documents.id created when this packet is transferred inward
    document_id: Mapped[int | None] = mapped_column(ForeignKey("kb_documents.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    transferred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

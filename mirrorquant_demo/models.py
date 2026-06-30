from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mirrorquant_demo.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Hero(Base):
    __tablename__ = "heroes"
    __table_args__ = (
        UniqueConstraint("user_id", "ticker", "start_date", "end_date", name="uq_hero_user_ticker_window"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user: Mapped[User] = relationship(back_populates="heroes") # back_populates mean both hero and user are connected and can access each other's fields.
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    available_start_date: Mapped[date] = mapped_column(Date)
    available_end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
    )

    search_runs: Mapped[list["SearchRun"]] = relationship(
        back_populates="hero",
        cascade="all, delete-orphan",
        order_by="desc(SearchRun.created_at)",
    )


class SearchRun(Base):
    __tablename__ = "search_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hero_id: Mapped[int] = mapped_column(ForeignKey("heroes.id"), index=True)
    mode: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    search_backend: Mapped[str] = mapped_column(String(64))
    hero_regime_code: Mapped[str] = mapped_column(String(64))
    selected_window_json: Mapped[dict] = mapped_column(JSON)
    effective_window_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    hero_snapshot_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    hero: Mapped[Hero] = relationship(back_populates="search_runs")
    matches: Mapped[list["MatchResult"]] = relationship(
        back_populates="search_run",
        cascade="all, delete-orphan",
        order_by="MatchResult.rank",
    )


class MatchResult(Base):
    __tablename__ = "match_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_run_id: Mapped[int] = mapped_column(ForeignKey("search_runs.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(255))
    score: Mapped[float] = mapped_column(Float)
    regime_label: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str | None] = mapped_column(String(255), nullable=True)
    explanation: Mapped[str] = mapped_column(Text)
    matched_window_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    features_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    series_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    search_run: Mapped[SearchRun] = relationship(back_populates="matches")

class User(Base): 
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_verified: Mapped[bool] = mapped_column(default=False)
    verification_token_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verification_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    heroes: Mapped[list["Hero"]] = relationship (
        back_populates="user",
        cascade="all, delete-orphan", # If user is deleted, the heroes should be deleted as well.
                                      # Prevents orphan data not linked to a user/owner.
    )

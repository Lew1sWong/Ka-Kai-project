from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SQLITE_URL = f"sqlite:///{(BASE_DIR / 'data' / 'mirrorquant.db').resolve().as_posix()}"

load_dotenv()
DATABASE_URL = (
    os.getenv("MIRRORQUANT_DATABASE_URL")
    or os.getenv("DATABASE_URL")
    or DEFAULT_SQLITE_URL
)


class Base(DeclarativeBase):
    pass


def _build_engine():
    connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    return create_engine(
        DATABASE_URL,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


engine = _build_engine()
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_database():
    from mirrorquant_demo.models import MatchResult, Hero, SearchRun  # noqa: F401

    Base.metadata.create_all(bind=engine)

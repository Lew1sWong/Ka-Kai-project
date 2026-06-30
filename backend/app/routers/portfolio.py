"""Module C — Portfolio Risk-Assistance Analysis API.

Endpoints for managing portfolios, importing holdings, and running a
risk-assistance analysis. All routes are user-scoped via the auth deps; writes
require the ``analyst`` role and are audited. The risk endpoint wraps its output
in the compliance-alert layer (not-investment-advice disclaimer + sources).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.deps import (
    get_current_verified_user,
    record_audit,
    require_role,
)
from mirrorquant_demo import compliance
from mirrorquant_demo.database import get_session
from mirrorquant_demo.models import User
from mirrorquant_demo.permissions import ANALYST
from mirrorquant_demo import portfolio_service

router = APIRouter(prefix="/api/portfolios", tags=["portfolios"])


# --------------------------------------------------------------------------- #
# Request / response bodies
# --------------------------------------------------------------------------- #
class PortfolioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class HoldingIn(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=16)
    weight: float | None = Field(default=None, ge=0.0, le=1.0)
    shares: float | None = Field(default=None, ge=0.0)
    sector: str | None = Field(default=None, max_length=255)


class HoldingsImport(BaseModel):
    holdings: list[HoldingIn] = Field(..., min_length=1)


# --------------------------------------------------------------------------- #
# Serialization helpers
# --------------------------------------------------------------------------- #
def _serialize_holding(holding: Any) -> dict[str, Any]:
    return {
        "id": holding.id,
        "ticker": holding.ticker,
        "weight": holding.weight,
        "shares": holding.shares,
        "sector": holding.sector,
    }


def _serialize_portfolio(portfolio: Any) -> dict[str, Any]:
    return {
        "id": portfolio.id,
        "name": portfolio.name,
        "created_at": portfolio.created_at.isoformat() if portfolio.created_at else None,
        "updated_at": portfolio.updated_at.isoformat() if portfolio.updated_at else None,
        "holdings": [_serialize_holding(h) for h in portfolio.holdings],
    }


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@router.post("")
async def create_portfolio(
    body: PortfolioCreate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(ANALYST)),
) -> dict[str, Any]:
    try:
        portfolio = portfolio_service.create_portfolio(session, current_user.id, body.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_audit(
        session,
        user_id=current_user.id,
        action="portfolio.create",
        target_type="portfolio",
        target_id=portfolio.id,
        detail={"name": portfolio.name},
        request=request,
    )
    return _serialize_portfolio(portfolio)


@router.get("")
async def list_portfolios(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
) -> list[dict[str, Any]]:
    portfolios = portfolio_service.list_portfolios(session, current_user.id)
    return [_serialize_portfolio(p) for p in portfolios]


@router.get("/{pid}")
async def get_portfolio(
    pid: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
) -> dict[str, Any]:
    try:
        portfolio = portfolio_service.get_portfolio(session, current_user.id, pid)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _serialize_portfolio(portfolio)


@router.post("/{pid}/holdings")
async def import_holdings(
    pid: int,
    body: HoldingsImport,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(ANALYST)),
) -> dict[str, Any]:
    items = [h.model_dump() for h in body.holdings]
    try:
        portfolio = portfolio_service.import_holdings(session, current_user.id, pid, items)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_audit(
        session,
        user_id=current_user.id,
        action="portfolio.import_holdings",
        target_type="portfolio",
        target_id=portfolio.id,
        detail={"holdings_count": len(portfolio.holdings)},
        request=request,
    )
    return _serialize_portfolio(portfolio)


@router.get("/{pid}/risk")
async def portfolio_risk(
    pid: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
) -> dict[str, Any]:
    try:
        summary = portfolio_service.analyze_portfolio(session, current_user.id, pid)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return compliance.attach_compliance(
        summary,
        sources=[compliance.source("dataset", "prices.csv")],
    )

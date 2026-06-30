"""API router for Investment-Hypothesis Management + IC-material generation.

Endpoints (prefix ``/api/hypotheses``):
  - POST   ''                     create a hypothesis           (analyst+)
  - GET    ''                     list mine
  - GET    '/{hid}'               fetch one (with events)
  - PATCH  '/{hid}'               update fields/status          (analyst+)
  - POST   '/{hid}/events'        add a note/review event       (analyst+)
  - POST   '/{hid}/archive'       archive                       (analyst+)
  - POST   '/generate-ic-material'  synthesise an IC pack       (analyst+)

Every analytical/generated output is wrapped with ``compliance.attach_compliance``
before returning, and every write/generate call records an audit-log entry.
``LookupError`` maps to 404 and ``ValueError`` to 400.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.deps import get_current_verified_user, record_audit, require_role
from mirrorquant_demo import compliance, hypothesis_service
from mirrorquant_demo.database import get_session
from mirrorquant_demo.models import User
from mirrorquant_demo.permissions import ANALYST

router = APIRouter(prefix="/api/hypotheses", tags=["hypotheses"])


# --- request bodies ---------------------------------------------------------

class HypothesisCreate(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=16)
    title: str = Field(..., min_length=1, max_length=255)
    thesis: str = Field(..., min_length=1)
    hero_id: int | None = None
    core_assumptions: list[str] = Field(default_factory=list)
    validation_metrics: list[str] = Field(default_factory=list)
    falsification_conditions: list[str] = Field(default_factory=list)
    conviction: int = Field(default=3, ge=1, le=5)
    status: str = Field(default="open", max_length=32)


class HypothesisUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    thesis: str | None = None
    core_assumptions: list[str] | None = None
    validation_metrics: list[str] | None = None
    falsification_conditions: list[str] | None = None
    conviction: int | None = Field(default=None, ge=1, le=5)
    status: str | None = Field(default=None, max_length=32)


class EventCreate(BaseModel):
    event_type: str = Field(default="note", max_length=32)
    summary: str = Field(..., min_length=1)
    detail: dict | None = None


class ICMaterialRequest(BaseModel):
    hero_id: int | None = None
    title: str | None = Field(default=None, max_length=255)


# --- endpoints --------------------------------------------------------------

@router.post("")
async def create_hypothesis(
    body: HypothesisCreate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(ANALYST)),
) -> dict:
    try:
        hypothesis = hypothesis_service.create_hypothesis(
            session,
            current_user.id,
            ticker=body.ticker,
            title=body.title,
            thesis=body.thesis,
            hero_id=body.hero_id,
            core_assumptions=body.core_assumptions,
            validation_metrics=body.validation_metrics,
            falsification_conditions=body.falsification_conditions,
            conviction=body.conviction,
            status=body.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_audit(
        session,
        user_id=current_user.id,
        action="hypothesis.create",
        target_type="hypothesis",
        target_id=hypothesis.id,
        detail={"ticker": hypothesis.ticker, "title": hypothesis.title},
        request=request,
    )
    return hypothesis_service.serialize_hypothesis(hypothesis, include_events=True)


@router.get("")
async def list_hypotheses(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
    status: str | None = None,
    ticker: str | None = None,
) -> list[dict]:
    rows = hypothesis_service.list_hypotheses(
        session, current_user.id, status=status, ticker=ticker
    )
    return [hypothesis_service.serialize_hypothesis(h) for h in rows]


@router.get("/{hid}")
async def get_hypothesis(
    hid: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
) -> dict:
    try:
        hypothesis = hypothesis_service.get_hypothesis(session, current_user.id, hid)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return hypothesis_service.serialize_hypothesis(hypothesis, include_events=True)


@router.patch("/{hid}")
async def update_hypothesis(
    hid: int,
    body: HypothesisUpdate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(ANALYST)),
) -> dict:
    try:
        hypothesis = hypothesis_service.update_hypothesis(
            session,
            current_user.id,
            hid,
            title=body.title,
            thesis=body.thesis,
            core_assumptions=body.core_assumptions,
            validation_metrics=body.validation_metrics,
            falsification_conditions=body.falsification_conditions,
            conviction=body.conviction,
            status=body.status,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_audit(
        session,
        user_id=current_user.id,
        action="hypothesis.update",
        target_type="hypothesis",
        target_id=hypothesis.id,
        detail={"status": hypothesis.status},
        request=request,
    )
    return hypothesis_service.serialize_hypothesis(hypothesis, include_events=True)


@router.post("/{hid}/events")
async def add_event(
    hid: int,
    body: EventCreate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(ANALYST)),
) -> dict:
    try:
        event = hypothesis_service.add_event(
            session,
            current_user.id,
            hid,
            event_type=body.event_type,
            summary=body.summary,
            detail=body.detail,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_audit(
        session,
        user_id=current_user.id,
        action="hypothesis.add_event",
        target_type="hypothesis",
        target_id=hid,
        detail={"event_type": event.event_type},
        request=request,
    )
    return hypothesis_service.serialize_event(event)


@router.post("/{hid}/archive")
async def archive_hypothesis(
    hid: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(ANALYST)),
) -> dict:
    try:
        hypothesis = hypothesis_service.archive_hypothesis(session, current_user.id, hid)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_audit(
        session,
        user_id=current_user.id,
        action="hypothesis.archive",
        target_type="hypothesis",
        target_id=hid,
        request=request,
    )
    return hypothesis_service.serialize_hypothesis(hypothesis, include_events=True)


@router.post("/generate-ic-material")
async def generate_ic_material(
    body: ICMaterialRequest,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(ANALYST)),
) -> dict:
    try:
        material = await hypothesis_service.generate_ic_material(
            session,
            current_user.id,
            hero_id=body.hero_id,
            title=body.title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_audit(
        session,
        user_id=current_user.id,
        action="hypothesis.generate_ic_material",
        target_type="ic_material",
        target_id=body.hero_id,
        detail={"source": material.get("source"), "title": material.get("title")},
        request=request,
    )

    sources = [
        compliance.source(
            "internal",
            "hypotheses+heroes+search_runs",
            f"user {current_user.id} research context",
        ),
        compliance.source("llm", material.get("source", "template"), "IC material synthesis"),
    ]
    return compliance.attach_compliance(material, sources=sources)

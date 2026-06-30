"""One-Way Data Transfer Mechanism API (contract Articles 2.2/2.3/3.3/10.4).

Exposes the External Intelligence Machine staging area and the one-way transfer
gate into the internal knowledge base. There is no endpoint that moves internal
data outward — by design.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.deps import get_current_verified_user, record_audit, require_role
from mirrorquant_demo import compliance, data_diode
from mirrorquant_demo.data_diode import serialize_packet
from mirrorquant_demo.database import get_session
from mirrorquant_demo.models import User
from mirrorquant_demo.permissions import ANALYST

router = APIRouter(prefix="/api/diode", tags=["data-diode"])


class IngestPacket(BaseModel):
    source: str = Field(..., min_length=1, max_length=255)
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    source_url: str | None = Field(default=None, max_length=1024)
    classification: str = Field(default="public", max_length=32)


@router.get("/policy")
async def get_policy():
    return compliance.attach_compliance(
        {"policy": data_diode.policy()},
        sources=[compliance.source("policy", "one-way-transfer")],
    )


@router.post("/ingest")
async def ingest_packet(
    body: IngestPacket,
    request: Request,
    current_user: User = Depends(require_role(ANALYST)),
    session: Session = Depends(get_session),
):
    try:
        packet = data_diode.submit_packet(
            session,
            current_user.id,
            source=body.source,
            title=body.title,
            content=body.content,
            source_url=body.source_url,
            classification=body.classification,
        )
    except data_diode.DiodeDisabled as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    record_audit(
        session,
        user_id=current_user.id,
        action="diode.ingest",
        target_type="diode_packet",
        target_id=packet.id,
        detail={"source": packet.source, "status": packet.status},
        request=request,
    )
    return compliance.attach_compliance(
        {"packet": serialize_packet(packet)},
        sources=[compliance.source("external", packet.source)],
    )


@router.get("")
async def list_packets(
    status: str | None = None,
    current_user: User = Depends(get_current_verified_user),
    session: Session = Depends(get_session),
):
    return {"packets": data_diode.list_packets(session, current_user.id, status=status)}


@router.post("/packets/{packet_id}/transfer")
async def transfer_packet(
    packet_id: int,
    request: Request,
    confirm: bool = False,
    current_user: User = Depends(require_role(ANALYST)),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        result = data_diode.transfer_packet(session, current_user.id, packet_id, confirm=confirm)
    except data_diode.DiodeDisabled as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        record_audit(
            session,
            user_id=current_user.id,
            action="diode.transfer.blocked",
            target_type="diode_packet",
            target_id=packet_id,
            detail={"reason": str(exc)},
            request=request,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_audit(
        session,
        user_id=current_user.id,
        action="diode.transfer",
        target_type="diode_packet",
        target_id=packet_id,
        detail={"knowledge_base_document_id": result.get("knowledge_base_document_id")},
        request=request,
    )
    return compliance.attach_compliance(result, sources=[compliance.source("policy", "one-way-transfer")])

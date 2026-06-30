"""One-Way Data Transfer Mechanism (software-defined "data diode").

Implements the contract's core security architecture (Articles 2.2/2.3/3.3/10.4):

    External public information
        -> External Intelligence Machine (staging: IntelligencePacket)
        -> One-Way Transfer Gate (this module)
        -> Internal Knowledge Base (knowledge_base.ingest_document)

Enforced invariants:
  * Data only EVER moves external -> internal. There is no function in this
    module (or anywhere) that moves internal data outward.
  * Only ``public``-classified packets may enter the external machine or be
    transferred inward; content scanned for internal/confidential markers is
    rejected (internal data must never sit in the external machine).
  * Sources may be restricted to a configurable whitelist.
  * Every submit / transfer / reject is audited by the caller.

Honesty note (contract Article 10.4): this is a SOFTWARE-defined one-way trust
channel using classification, whitelisting, content scanning and audit. It is
NOT equivalent to a physical one-way data diode and provides no physical
link-level isolation guarantee.
"""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from mirrorquant_demo import knowledge_base
from mirrorquant_demo.data_diode_models import IntelligencePacket

TRANSFER_DIRECTION = "external_to_internal_only"
ALLOWED_CLASSIFICATION = "public"

# Markers that indicate the content is internal/confidential and therefore must
# never be present in the external machine or cross the gate.
_INTERNAL_MARKERS = [
    r"\bconfidential\b",
    r"\binternal[\s-]*only\b",
    r"\bmnpi\b",
    r"material non-public",
    r"\bholdings?\b",
    r"\bposition sheet\b",
    r"\btrading plan\b",
    r"\bstrategy parameters?\b",
    r"内部(资料|材料|使用)?",
    r"机密",
    r"内幕",
    r"持仓",
    r"交易计划",
]
_INTERNAL_RE = [re.compile(p, re.IGNORECASE) for p in _INTERNAL_MARKERS]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _source_whitelist() -> list[str]:
    raw = os.getenv("MIRRORQUANT_DIODE_SOURCE_WHITELIST", "").strip()
    return [s.strip().lower() for s in raw.split(",") if s.strip()]


def _source_allowed(source: str) -> tuple[bool, str]:
    whitelist = _source_whitelist()
    if not whitelist:
        return True, "whitelist not configured (allow-all)"
    src = (source or "").strip().lower()
    if any(allowed in src for allowed in whitelist):
        return True, "source whitelisted"
    return False, f"source '{source}' not in whitelist"


def scan_internal(text: str) -> list[str]:
    """Return the internal/confidential markers found in ``text`` (empty = clean)."""
    if not text:
        return []
    found = []
    for pattern in _INTERNAL_RE:
        if pattern.search(text):
            found.append(pattern.pattern)
    return found


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def serialize_packet(packet: IntelligencePacket) -> dict:
    return {
        "id": packet.id,
        "source": packet.source,
        "source_url": packet.source_url,
        "classification": packet.classification,
        "title": packet.title,
        "status": packet.status,
        "reason": packet.reason,
        "document_id": packet.document_id,
        "content_preview": (packet.content or "")[:280],
        "created_at": packet.created_at.isoformat() if packet.created_at else None,
        "transferred_at": packet.transferred_at.isoformat() if packet.transferred_at else None,
    }


def submit_packet(
    session: Session,
    user_id: int,
    *,
    source: str,
    title: str,
    content: str,
    source_url: str | None = None,
    classification: str = "public",
) -> IntelligencePacket:
    """External Intelligence Machine submits a public packet into staging.

    Rejects (and stores as ``rejected``) anything non-public or containing
    internal/confidential markers — internal data must never enter the external
    machine.
    """
    classification = (classification or "public").strip().lower()
    packet = IntelligencePacket(
        user_id=user_id,
        source=source,
        source_url=source_url,
        classification=classification,
        title=title,
        content=content or "",
        content_hash=_hash(content),
    )

    if classification != ALLOWED_CLASSIFICATION:
        packet.status = "rejected"
        packet.reason = f"only '{ALLOWED_CLASSIFICATION}' classification may enter the external machine"
    else:
        markers = scan_internal(f"{title}\n{content}")
        if markers:
            packet.status = "rejected"
            packet.reason = f"internal/confidential markers detected: {', '.join(markers[:3])}"
        else:
            packet.status = "staged"

    session.add(packet)
    session.commit()
    session.refresh(packet)
    return packet


def transfer_packet(session: Session, user_id: int, packet_id: int) -> dict:
    """The one-way gate: push a staged public packet INTO the internal KB.

    Re-validates classification, source whitelist and content scan at the gate.
    On success the packet content is ingested as an internal knowledge-base
    document (the only direction data ever flows). Raises ``LookupError`` /
    ``ValueError`` on missing/invalid packets.
    """
    packet = session.get(IntelligencePacket, packet_id)
    if packet is None or packet.user_id != user_id:
        raise LookupError(f"intelligence packet {packet_id} not found")

    if packet.status == "transferred":
        raise ValueError("packet already transferred")

    # Gate checks (defence-in-depth — re-checked even though submit_packet did).
    if packet.classification != ALLOWED_CLASSIFICATION:
        packet.status = "rejected"
        packet.reason = "blocked at gate: non-public classification"
        session.commit()
        raise ValueError(packet.reason)

    allowed, why = _source_allowed(packet.source)
    if not allowed:
        packet.status = "rejected"
        packet.reason = f"blocked at gate: {why}"
        session.commit()
        raise ValueError(packet.reason)

    markers = scan_internal(f"{packet.title}\n{packet.content}")
    if markers:
        packet.status = "rejected"
        packet.reason = f"blocked at gate: internal markers {', '.join(markers[:3])}"
        session.commit()
        raise ValueError(packet.reason)

    # One-way flow: external -> internal knowledge base.
    document = knowledge_base.ingest_document(
        session,
        user_id=user_id,
        title=f"[diode] {packet.title}",
        text=packet.content,
        kind="text",
        source_name=packet.source,
    )

    packet.status = "transferred"
    packet.document_id = document.id
    packet.transferred_at = _utcnow()
    packet.reason = None
    session.commit()
    session.refresh(packet)

    return {
        "transferred": True,
        "direction": TRANSFER_DIRECTION,
        "packet": serialize_packet(packet),
        "knowledge_base_document_id": document.id,
    }


def list_packets(session: Session, user_id: int, status: str | None = None) -> list[dict]:
    stmt = select(IntelligencePacket).where(IntelligencePacket.user_id == user_id)
    if status:
        stmt = stmt.where(IntelligencePacket.status == status)
    stmt = stmt.order_by(IntelligencePacket.created_at.desc())
    return [serialize_packet(p) for p in session.scalars(stmt).all()]


def policy() -> dict:
    """The enforced one-way policy — surfaced to clients for transparency."""
    return {
        "transfer_direction": TRANSFER_DIRECTION,
        "allowed_classification": ALLOWED_CLASSIFICATION,
        "source_whitelist": _source_whitelist() or "not configured (allow-all)",
        "internal_marker_rules": len(_INTERNAL_RE),
        "internal_egress_supported": False,
        "software_defined": True,
        "physical_diode_equivalent": False,
        "note": (
            "Software-defined one-way trust channel. Per contract Article 10.4 this is "
            "NOT equivalent to a physical one-way data diode and provides no physical "
            "link-level isolation guarantee. Internal data has no path outward."
        ),
    }

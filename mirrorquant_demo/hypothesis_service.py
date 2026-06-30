"""Service layer for Investment-Hypothesis Management + IC-material generation.

All public functions take ``(session, user_id, ...)`` and scope every read/write
to the owning user, so a router can pass the current user's id and never leak
another user's research. Serializers return plain JSON-ready dicts.

``generate_ic_material`` gathers the user's heroes, recent search runs, and open
hypotheses and asks the LLM to synthesise an Investment-Committee pack. If the
LLM is not configured (or raises ``LLMUnavailable``) it degrades gracefully to a
deterministic template built from the same gathered data — a missing API key
must never break the endpoint.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mirrorquant_demo import llm
from mirrorquant_demo.hypothesis_models import Hypothesis, HypothesisEvent
from mirrorquant_demo.models import Hero, SearchRun


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Fields a caller may set on create/update and how to normalise them.
_LIST_FIELDS = ("core_assumptions", "validation_metrics", "falsification_conditions")
_VALID_STATUSES = {"open", "validated", "falsified", "archived"}


def _clean_str_list(value: Any) -> list[str]:
    """Coerce an incoming value into a clean list of non-empty strings."""
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def _clamp_conviction(value: Any, default: int = 3) -> int:
    try:
        conviction = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(5, conviction))


# --- serialization ----------------------------------------------------------

def serialize_event(event: HypothesisEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "hypothesis_id": event.hypothesis_id,
        "event_type": event.event_type,
        "summary": event.summary,
        "detail": event.detail_json,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def serialize_hypothesis(
    hypothesis: Hypothesis,
    *,
    include_events: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": hypothesis.id,
        "user_id": hypothesis.user_id,
        "hero_id": hypothesis.hero_id,
        "ticker": hypothesis.ticker,
        "title": hypothesis.title,
        "thesis": hypothesis.thesis,
        "core_assumptions": hypothesis.core_assumptions or [],
        "validation_metrics": hypothesis.validation_metrics or [],
        "falsification_conditions": hypothesis.falsification_conditions or [],
        "status": hypothesis.status,
        "conviction": hypothesis.conviction,
        "created_at": hypothesis.created_at.isoformat() if hypothesis.created_at else None,
        "updated_at": hypothesis.updated_at.isoformat() if hypothesis.updated_at else None,
    }
    if include_events:
        payload["events"] = [serialize_event(e) for e in hypothesis.events]
    return payload


# --- CRUD -------------------------------------------------------------------

def create_hypothesis(
    session: Session,
    user_id: int,
    *,
    ticker: str,
    title: str,
    thesis: str,
    hero_id: int | None = None,
    core_assumptions: Any = None,
    validation_metrics: Any = None,
    falsification_conditions: Any = None,
    conviction: Any = 3,
    status: str = "open",
) -> Hypothesis:
    """Create a hypothesis owned by ``user_id`` and seed a 'created' event."""
    ticker = (ticker or "").strip().upper()
    title = (title or "").strip()
    thesis = (thesis or "").strip()
    if not ticker:
        raise ValueError("ticker is required")
    if not title:
        raise ValueError("title is required")
    if not thesis:
        raise ValueError("thesis is required")

    normalized_status = (status or "open").strip().lower()
    if normalized_status not in _VALID_STATUSES:
        raise ValueError(f"invalid status: {status}")

    # If a hero is supplied, ensure it belongs to this user.
    if hero_id is not None:
        hero = session.get(Hero, hero_id)
        if hero is None or hero.user_id != user_id:
            raise ValueError("hero_id does not belong to the current user")

    hypothesis = Hypothesis(
        user_id=user_id,
        hero_id=hero_id,
        ticker=ticker,
        title=title,
        thesis=thesis,
        core_assumptions=_clean_str_list(core_assumptions),
        validation_metrics=_clean_str_list(validation_metrics),
        falsification_conditions=_clean_str_list(falsification_conditions),
        status=normalized_status,
        conviction=_clamp_conviction(conviction),
    )
    session.add(hypothesis)
    session.flush()  # assign id before building the event

    event = HypothesisEvent(
        hypothesis_id=hypothesis.id,
        event_type="created",
        summary=f"Hypothesis created for {ticker}: {title}",
        detail_json={"status": normalized_status, "conviction": hypothesis.conviction},
    )
    session.add(event)
    session.commit()
    session.refresh(hypothesis)
    return hypothesis


def get_hypothesis(session: Session, user_id: int, hid: int) -> Hypothesis:
    """Return the user's hypothesis or raise ``LookupError`` if not found."""
    hypothesis = session.get(Hypothesis, hid)
    if hypothesis is None or hypothesis.user_id != user_id:
        raise LookupError(f"hypothesis {hid} not found")
    return hypothesis


def list_hypotheses(
    session: Session,
    user_id: int,
    *,
    status: str | None = None,
    ticker: str | None = None,
) -> list[Hypothesis]:
    """List the user's hypotheses, newest first, with optional filters."""
    stmt = select(Hypothesis).where(Hypothesis.user_id == user_id)
    if status:
        stmt = stmt.where(Hypothesis.status == status.strip().lower())
    if ticker:
        stmt = stmt.where(Hypothesis.ticker == ticker.strip().upper())
    stmt = stmt.order_by(Hypothesis.updated_at.desc(), Hypothesis.created_at.desc())
    return list(session.scalars(stmt).all())


def add_event(
    session: Session,
    user_id: int,
    hid: int,
    *,
    event_type: str,
    summary: str,
    detail: dict | None = None,
) -> HypothesisEvent:
    """Append an event to the user's hypothesis (validates ownership)."""
    hypothesis = get_hypothesis(session, user_id, hid)
    event_type = (event_type or "note").strip().lower()
    summary = (summary or "").strip()
    if not summary:
        raise ValueError("summary is required")

    event = HypothesisEvent(
        hypothesis_id=hypothesis.id,
        event_type=event_type,
        summary=summary,
        detail_json=detail,
    )
    session.add(event)
    # Touch the parent so updated_at moves with new activity.
    hypothesis.updated_at = _utcnow()
    session.add(hypothesis)
    session.commit()
    session.refresh(event)
    return event


def update_hypothesis(
    session: Session,
    user_id: int,
    hid: int,
    *,
    title: str | None = None,
    thesis: str | None = None,
    core_assumptions: Any = None,
    validation_metrics: Any = None,
    falsification_conditions: Any = None,
    conviction: Any = None,
    status: str | None = None,
) -> Hypothesis:
    """Update fields and/or status. A status change appends an event."""
    hypothesis = get_hypothesis(session, user_id, hid)

    if title is not None:
        cleaned = title.strip()
        if not cleaned:
            raise ValueError("title cannot be empty")
        hypothesis.title = cleaned
    if thesis is not None:
        cleaned = thesis.strip()
        if not cleaned:
            raise ValueError("thesis cannot be empty")
        hypothesis.thesis = cleaned
    if core_assumptions is not None:
        hypothesis.core_assumptions = _clean_str_list(core_assumptions)
    if validation_metrics is not None:
        hypothesis.validation_metrics = _clean_str_list(validation_metrics)
    if falsification_conditions is not None:
        hypothesis.falsification_conditions = _clean_str_list(falsification_conditions)
    if conviction is not None:
        hypothesis.conviction = _clamp_conviction(conviction, default=hypothesis.conviction)

    if status is not None:
        new_status = status.strip().lower()
        if new_status not in _VALID_STATUSES:
            raise ValueError(f"invalid status: {status}")
        old_status = hypothesis.status
        if new_status != old_status:
            hypothesis.status = new_status
            session.add(
                HypothesisEvent(
                    hypothesis_id=hypothesis.id,
                    event_type="status_change",
                    summary=f"Status changed: {old_status} -> {new_status}",
                    detail_json={"from": old_status, "to": new_status},
                )
            )

    hypothesis.updated_at = _utcnow()
    session.add(hypothesis)
    session.commit()
    session.refresh(hypothesis)
    return hypothesis


def archive_hypothesis(session: Session, user_id: int, hid: int) -> Hypothesis:
    """Convenience wrapper: set status to 'archived' (records an event)."""
    return update_hypothesis(session, user_id, hid, status="archived")


# --- IC-material generation --------------------------------------------------

def _gather_context(
    session: Session,
    user_id: int,
    *,
    hero_id: int | None = None,
) -> dict[str, Any]:
    """Collect heroes, recent search runs, and open hypotheses for the user."""
    hero_stmt = select(Hero).where(Hero.user_id == user_id)
    if hero_id is not None:
        hero_stmt = hero_stmt.where(Hero.id == hero_id)
    hero_stmt = hero_stmt.order_by(Hero.updated_at.desc(), Hero.created_at.desc())
    heroes = list(session.scalars(hero_stmt).all())

    hero_ids = [h.id for h in heroes]
    runs: list[SearchRun] = []
    if hero_ids:
        run_stmt = (
            select(SearchRun)
            .where(SearchRun.hero_id.in_(hero_ids))
            .order_by(SearchRun.created_at.desc())
            .limit(20)
        )
        runs = list(session.scalars(run_stmt).all())

    open_hypotheses = [
        h for h in list_hypotheses(session, user_id) if h.status in ("open", "validated")
    ]

    return {"heroes": heroes, "runs": runs, "hypotheses": open_hypotheses}


def _summarize_hero(hero: Hero) -> dict[str, Any]:
    return {
        "id": hero.id,
        "ticker": hero.ticker,
        "name": hero.name,
        "title": hero.title,
        "window": f"{hero.start_date.isoformat()} -> {hero.end_date.isoformat()}",
        "status": hero.status,
    }


def _summarize_run(run: SearchRun) -> dict[str, Any]:
    snapshot = run.hero_snapshot_json or {}
    return {
        "id": run.id,
        "hero_id": run.hero_id,
        "mode": run.mode,
        "status": run.status,
        "regime_code": run.hero_regime_code,
        "ticker": snapshot.get("ticker") if isinstance(snapshot, dict) else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def _build_template_ic_material(context: dict[str, Any]) -> dict[str, Any]:
    """Deterministic, non-LLM IC pack built purely from gathered data."""
    heroes = context["heroes"]
    runs = context["runs"]
    hypotheses = context["hypotheses"]

    hero_lines = [
        f"{h.ticker} ({h.name}) — {h.title}; window {h.start_date.isoformat()} to {h.end_date.isoformat()}"
        for h in heroes
    ]
    mode_counts: dict[str, int] = {}
    for run in runs:
        mode_counts[run.mode] = mode_counts.get(run.mode, 0) + 1
    run_lines = [f"{mode}: {count} run(s)" for mode, count in sorted(mode_counts.items())]

    market_change_summary = (
        f"Tracking {len(heroes)} reference target(s) with "
        f"{len(runs)} recent mirror-search run(s). "
        "Generated without LLM synthesis (deterministic template)."
        if heroes or runs
        else "No reference targets or recent search runs on record yet."
    )

    key_target_changes = hero_lines or ["No reference targets recorded."]

    performance_attribution_notes = run_lines or [
        "No mirror-search activity to attribute performance from."
    ]

    risk_alerts: list[str] = []
    for hypo in hypotheses:
        for cond in (hypo.falsification_conditions or []):
            risk_alerts.append(f"[{hypo.ticker}] watch falsifier: {cond}")
    if not risk_alerts:
        risk_alerts = ["No explicit falsification conditions flagged across open hypotheses."]

    discussion_topics = [
        f"Review conviction on {h.ticker} ({h.title})" for h in hypotheses[:5]
    ] or ["No open hypotheses to discuss; consider seeding new theses."]

    hypothesis_changes = [
        {
            "ticker": h.ticker,
            "title": h.title,
            "status": h.status,
            "conviction": h.conviction,
            "open_questions": h.validation_metrics or [],
        }
        for h in hypotheses
    ]

    follow_ups = [
        f"Validate metrics for {h.ticker}: {', '.join(h.validation_metrics)}"
        for h in hypotheses
        if h.validation_metrics
    ] or ["Define validation metrics for open hypotheses."]

    return {
        "market_change_summary": market_change_summary,
        "key_target_changes": key_target_changes,
        "performance_attribution_notes": performance_attribution_notes,
        "risk_alerts": risk_alerts,
        "discussion_topics": discussion_topics,
        "hypothesis_changes": hypothesis_changes,
        "follow_ups": follow_ups,
    }


_IC_SECTIONS = (
    "market_change_summary",
    "key_target_changes",
    "performance_attribution_notes",
    "risk_alerts",
    "discussion_topics",
    "hypothesis_changes",
    "follow_ups",
)


def _coerce_ic_material(raw: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    """Ensure every expected section exists; backfill from the template."""
    out: dict[str, Any] = {}
    for key in _IC_SECTIONS:
        value = raw.get(key) if isinstance(raw, dict) else None
        out[key] = value if value not in (None, "", [], {}) else fallback[key]
    return out


async def generate_ic_material(
    session: Session,
    user_id: int,
    *,
    hero_id: int | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """Synthesise an Investment-Committee material pack for the user.

    Uses the LLM when configured; otherwise degrades to a deterministic template.
    Returns a plain dict (the router attaches compliance + sources).
    """
    context = _gather_context(session, user_id, hero_id=hero_id)
    template = _build_template_ic_material(context)

    pack_title = (title or "").strip() or "Investment Committee Material"
    generated_at = _utcnow().isoformat()

    heroes_summary = [_summarize_hero(h) for h in context["heroes"]]
    runs_summary = [_summarize_run(r) for r in context["runs"]]
    hypotheses_summary = [
        serialize_hypothesis(h) for h in context["hypotheses"]
    ]

    meta = {
        "title": pack_title,
        "generated_at": generated_at,
        "hero_id": hero_id,
        "source": "template",
        "counts": {
            "heroes": len(heroes_summary),
            "search_runs": len(runs_summary),
            "open_hypotheses": len(hypotheses_summary),
        },
    }

    if not llm.is_configured():
        return {**meta, **template}

    system = (
        "You are an equity research assistant preparing an internal Investment "
        "Committee (IC) discussion pack. Synthesise the provided data into a "
        "concise, factual briefing. Do NOT give buy/sell recommendations, price "
        "targets, or guaranteed-return language. Output a single JSON object with "
        "these keys: market_change_summary (string), key_target_changes (list of "
        "strings), performance_attribution_notes (list of strings), risk_alerts "
        "(list of strings), discussion_topics (list of strings), hypothesis_changes "
        "(list of objects), follow_ups (list of strings)."
    )
    user_payload = {
        "pack_title": pack_title,
        "reference_targets": heroes_summary,
        "recent_search_runs": runs_summary,
        "open_hypotheses": hypotheses_summary,
    }
    user = (
        "Prepare the IC pack from the following research context. "
        "Be specific and reference the tickers provided.\n\n"
        f"{user_payload}"
    )

    try:
        raw = await llm.complete_json(system, user, temperature=0.3, max_tokens=1800)
        material = _coerce_ic_material(raw, template)
        meta["source"] = "llm"
        return {**meta, **material}
    except llm.LLMUnavailable:
        return {**meta, **template}
    except Exception:  # pragma: no cover - any LLM failure degrades gracefully
        return {**meta, **template}

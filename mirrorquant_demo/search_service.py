from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from mirrorquant_demo.economic_data import (
    build_hero_economic_dna,
    classify_macro_regime,
    find_stock_feature_matches,
    format_api_matches,
    load_prices as load_economic_prices,
)
from mirrorquant_demo.features import compute_window_features
from mirrorquant_demo.models import Hero, MatchResult, SearchRun
from mirrorquant_demo.schemas import HeroCreate, Mode
from mirrorquant_demo.social_data import (
    COMPANY_METADATA,
    build_hero_social_dna,
    find_social_matches,
    format_api_matches as format_social_api_matches,
    load_social_profiles,
    load_social_signals,
)
from mirrorquant_demo.vqvae_search import find_vqvae_mirrors

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PRICES_PATH = DATA_DIR / "prices.csv"
SOCIAL_PROFILES_PATH = DATA_DIR / "social_profiles.json"
SOCIAL_SIGNALS_PATH = DATA_DIR / "social_signals.csv"
CURATED_HEROES_PATH = DATA_DIR / "heroes.json"


@lru_cache(maxsize=1)
def _load_curated_heroes() -> dict[str, dict[str, Any]]:
    if not CURATED_HEROES_PATH.exists():
        return {}
    with CURATED_HEROES_PATH.open("r", encoding="utf-8") as handle:
        heroes = json.load(handle)
    return {str(hero["ticker"]).upper(): hero for hero in heroes}


def _load_prices(path: Path = PRICES_PATH) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    return df.sort_values(["ticker", "date"]).copy()


def _get_price_window(
    df: pd.DataFrame,
    ticker: str,
    start_date: str | date | pd.Timestamp,
    end_date: str | date | pd.Timestamp,
) -> pd.DataFrame:
    return df[
        (df["ticker"] == ticker.upper())
        & (df["date"] >= pd.to_datetime(start_date))
        & (df["date"] <= pd.to_datetime(end_date))
    ].sort_values("date").copy()


def _serialize_close_series(window_df: pd.DataFrame) -> list[dict[str, str | float]]:
    return [
        {
            "date": row.date.strftime("%Y-%m-%d"),
            "close": float(row.close),
        }
        for row in window_df.itertuples(index=False)
    ]


def _to_json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _to_json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_to_json_ready(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def _company_name_for_ticker(ticker: str) -> str:
    normalized = ticker.upper()
    curated = _load_curated_heroes().get(normalized)
    if curated:
        return str(curated.get("name") or normalized)
    metadata = COMPANY_METADATA.get(normalized)
    if metadata:
        return str(metadata.get("name") or normalized)
    return normalized


def _company_sector_for_ticker(ticker: str) -> str:
    metadata = COMPANY_METADATA.get(ticker.upper())
    if metadata:
        return str(metadata.get("sector") or "Unknown")
    return "Unknown"


def _default_hero_title(ticker: str, start_date: date, end_date: date) -> str:
    return f"{ticker.upper()} window {start_date.isoformat()} to {end_date.isoformat()}"


def _default_hero_summary(hero: Hero) -> str:
    return (
        hero.notes
        or f"User-defined hero window for {hero.ticker} from "
        f"{hero.start_date.isoformat()} to {hero.end_date.isoformat()}."
    )


def validate_hero_window(
    ticker: str,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")

    normalized = ticker.upper()
    df = _load_prices()
    ticker_df = df[df["ticker"] == normalized].sort_values("date").copy()
    if ticker_df.empty:
        raise LookupError(f"No price series found for {normalized}")

    window_df = _get_price_window(df, normalized, start_date, end_date)
    if window_df.empty:
        raise LookupError(
            f"No price series found for {normalized} from {start_date.isoformat()} "
            f"to {end_date.isoformat()}"
        )

    if len(window_df) < 10:
        raise ValueError("Hero window must contain at least 10 trading sessions")

    return {
        "ticker": normalized,
        "name": _company_name_for_ticker(normalized),
        "available_start_date": ticker_df["date"].iloc[0].date(),
        "available_end_date": ticker_df["date"].iloc[-1].date(),
        "row_count": int(len(window_df)),
    }


def _hero_snapshot(hero: Hero) -> dict[str, Any]:
    return {
        "id": hero.id,
        "ticker": hero.ticker,
        "name": hero.name,
        "title": hero.title,
        "notes": hero.notes,
        "summary": _default_hero_summary(hero),
        "window_label": hero.title,
        "start_date": hero.start_date.isoformat(),
        "end_date": hero.end_date.isoformat(),
    }


def _hero_response(hero: Hero) -> dict[str, Any]:
    return {
        "id": hero.id,
        "ticker": hero.ticker,
        "name": hero.name,
        "title": hero.title,
        "notes": hero.notes,
        "summary": _default_hero_summary(hero),
        "start_date": hero.start_date.isoformat(),
        "end_date": hero.end_date.isoformat(),
        "available_start_date": hero.available_start_date.isoformat(),
        "available_end_date": hero.available_end_date.isoformat(),
        "status": hero.status,
        "created_at": hero.created_at.isoformat(),
        "updated_at": hero.updated_at.isoformat(),
    }


def _price_dna_traits(window_df: pd.DataFrame) -> list[str]:
    features = compute_window_features(window_df)
    traits: list[str] = []

    if features["total_return"] >= 0.12:
        traits.append("Strong breakout return profile")
    elif features["total_return"] > 0:
        traits.append("Positive price follow-through")
    else:
        traits.append("Weak price follow-through")

    if features["volatility"] <= 0.025:
        traits.append("Contained day-to-day volatility")
    else:
        traits.append("Elevated short-horizon volatility")

    if features["volume_trend"] >= 0.10:
        traits.append("Rising participation into the window")
    else:
        traits.append("Stable participation profile")

    if features["max_drawdown"] > -0.08 and len(traits) < 3:
        traits.append("Controlled pullback structure")

    return traits[:3]


def _build_price_dna_run(hero: Hero) -> dict[str, Any]:
    selected_start = hero.start_date.isoformat()
    selected_end = hero.end_date.isoformat()
    df = _load_prices()
    hero_window = _get_price_window(df, hero.ticker, hero.start_date, hero.end_date)

    results, hero_code, selected_window, effective_window = find_vqvae_mirrors(
        hero_ticker=hero.ticker,
        start=selected_start,
        end=selected_end,
        top_k=5,
    )

    matches = []
    for row in results.head(5).itertuples(index=False):
        match_start = row.start_date.strftime("%Y-%m-%d")
        match_end = row.end_date.strftime("%Y-%m-%d")
        match_window = _get_price_window(df, row.ticker, row.start_date, row.end_date)
        matches.append(
            {
                "ticker": row.ticker,
                "name": _company_name_for_ticker(row.ticker),
                "score": float(row.similarity),
                "regime_label": f"VQ-VAE Price DNA match ({match_start} to {match_end})",
                "sector": _company_sector_for_ticker(row.ticker),
                "explanation": (
                    f"{row.ticker} matched a learned latent regime similar to "
                    f"{hero.ticker}'s encoded hero window. "
                    f"Matched window: {match_start} to {match_end}."
                ),
                "matched_window": {
                    "start_date": match_start,
                    "end_date": match_end,
                },
                "series": _serialize_close_series(match_window),
            }
        )

    regime_code = f"PRICE_CODE_{int(hero_code):02d}"
    hero_snapshot = _hero_snapshot(hero)
    hero_snapshot["price_dna"] = {
        "regime_code": regime_code,
        "confidence": round(float(matches[0]["score"]) if matches else 0.0, 2),
        "traits": _price_dna_traits(hero_window),
    }

    return {
        "mode": "price_dna",
        "hero": hero_snapshot,
        "hero_regime_code": regime_code,
        "selected_window": {
            "start_date": selected_window["start_date"].strftime("%Y-%m-%d"),
            "end_date": selected_window["end_date"].strftime("%Y-%m-%d"),
            "row_count": selected_window["row_count"],
        },
        "effective_hero_window": {
            "start_date": effective_window["start_date"].strftime("%Y-%m-%d"),
            "end_date": effective_window["end_date"].strftime("%Y-%m-%d"),
            "window_size": effective_window["window_size"],
        },
        "matches": matches,
        "search_backend": "vqvae",
    }


def _economic_traits(hero_dna: dict[str, Any]) -> list[str]:
    macro_features = hero_dna["macro_features"]
    stock_features = hero_dna["stock_features"]
    traits: list[str] = []

    if macro_features.get("cpi_yoy") is not None:
        traits.append(
            "Cooling inflation" if macro_features["cpi_yoy"] < 0.03 else "Elevated inflation"
        )

    if macro_features.get("fedfunds_6m_change") is not None and len(traits) < 3:
        traits.append(
            "Falling rate pressure"
            if macro_features["fedfunds_6m_change"] <= 0
            else "Rising rate pressure"
        )

    if stock_features.get("max_drawdown") is not None and len(traits) < 3:
        traits.append(
            "Controlled drawdown"
            if stock_features["max_drawdown"] > -0.08
            else "Deep drawdown risk"
        )

    if stock_features.get("total_return") is not None and len(traits) < 3:
        traits.append(
            "Positive return profile"
            if stock_features["total_return"] > 0
            else "Negative return profile"
        )

    return traits[:3]


def _build_economic_dna_run(hero: Hero) -> dict[str, Any]:
    prices_df = load_economic_prices(str(DATA_DIR / "prices.csv"))
    macro_df = pd.read_csv(str(DATA_DIR / "macro_series.csv"), parse_dates=["date"])

    matches = find_stock_feature_matches(
        macro_df=macro_df,
        prices_df=prices_df,
        hero_ticker=hero.ticker,
        start_date=hero.start_date.isoformat(),
        end_date=hero.end_date.isoformat(),
    )
    api_matches = format_api_matches(matches)[:5]
    hero_dna = build_hero_economic_dna(
        macro_df=macro_df,
        prices_df=prices_df,
        ticker=hero.ticker,
        start_date=hero.start_date.isoformat(),
        end_date=hero.end_date.isoformat(),
    )

    regime_code = classify_macro_regime(hero_dna["macro_features"])
    hero_snapshot = _hero_snapshot(hero)
    hero_snapshot["economic_dna"] = {
        "regime_code": regime_code,
        "confidence": round(1 / (1 + (matches[0]["distance"] if matches else 1.0)), 2),
        "traits": _economic_traits(hero_dna),
    }

    return {
        "mode": "economic_dna",
        "hero": hero_snapshot,
        "hero_regime_code": regime_code,
        "selected_window": {
            "start_date": hero.start_date.isoformat(),
            "end_date": hero.end_date.isoformat(),
            "row_count": len(
                _get_price_window(prices_df, hero.ticker, hero.start_date, hero.end_date)
            ),
        },
        "effective_hero_window": None,
        "matches": api_matches,
        "search_backend": "economic_live",
    }


def _build_social_dna_run(hero: Hero) -> dict[str, Any]:
    prices_df = load_economic_prices(str(DATA_DIR / "prices.csv"))
    profiles = load_social_profiles(SOCIAL_PROFILES_PATH)
    signals_df = load_social_signals(SOCIAL_SIGNALS_PATH)

    matches = find_social_matches(
        prices_df=prices_df,
        profiles=profiles,
        hero_ticker=hero.ticker,
        start_date=hero.start_date.isoformat(),
        end_date=hero.end_date.isoformat(),
        signals_df=signals_df,
    )
    hero_dna = build_hero_social_dna(
        prices_df=prices_df,
        profiles=profiles,
        ticker=hero.ticker,
        start_date=hero.start_date.isoformat(),
        end_date=hero.end_date.isoformat(),
        signals_df=signals_df,
    )

    hero_snapshot = _hero_snapshot(hero)
    hero_snapshot["social_dna"] = {
        "regime_code": hero_dna["regime_code"],
        "confidence": round(1 / (1 + (matches[0]["distance"] if matches else 1.0)), 2),
        "traits": hero_dna["traits"],
    }

    return {
        "mode": "social_dna",
        "hero": hero_snapshot,
        "hero_regime_code": hero_dna["regime_code"],
        "selected_window": {
            "start_date": hero.start_date.isoformat(),
            "end_date": hero.end_date.isoformat(),
            "row_count": len(
                _get_price_window(prices_df, hero.ticker, hero.start_date, hero.end_date)
            ),
        },
        "effective_hero_window": None,
        "matches": format_social_api_matches(matches)[:5],
        "search_backend": "social_live" if not signals_df.empty else "social_mvp",
    }


def create_or_update_hero(session: Session, payload: HeroCreate) -> dict[str, Any]:
    validation = validate_hero_window(
        ticker=payload.ticker,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )

    existing = session.scalar(
        select(Hero).where(
            Hero.ticker == payload.ticker,
            Hero.start_date == payload.start_date,
            Hero.end_date == payload.end_date,
        )
    )

    title = payload.title or _default_hero_title(
        payload.ticker,
        payload.start_date,
        payload.end_date,
    )

    if existing is not None:
        existing.title = title
        if payload.notes is not None:
            existing.notes = payload.notes
        existing.name = validation["name"]
        existing.available_start_date = validation["available_start_date"]
        existing.available_end_date = validation["available_end_date"]
        existing.status = "active"
        session.commit()
        session.refresh(existing)
        return _hero_response(existing)

    hero = Hero(
        ticker=payload.ticker,
        name=validation["name"],
        title=title,
        notes=payload.notes,
        start_date=payload.start_date,
        end_date=payload.end_date,
        available_start_date=validation["available_start_date"],
        available_end_date=validation["available_end_date"],
        status="active",
    )
    session.add(hero)
    session.commit()
    session.refresh(hero)
    return _hero_response(hero)


def list_saved_heroes(session: Session) -> list[dict[str, Any]]:
    heroes = session.scalars(select(Hero).order_by(Hero.updated_at.desc(), Hero.created_at.desc())).all()
    return [_hero_response(hero) for hero in heroes]


def get_saved_hero(session: Session, hero_id: int) -> dict[str, Any] | None:
    hero = session.get(Hero, hero_id)
    if hero is None:
        return None
    return _hero_response(hero)


def _serialize_match(match: MatchResult) -> dict[str, Any]:
    return {
        "ticker": match.ticker,
        "name": match.name,
        "score": match.score,
        "regime_label": match.regime_label,
        "sector": match.sector or "Unknown",
        "explanation": match.explanation,
        "matched_window": match.matched_window_json,
        "features": match.features_json,
        "series": match.series_json,
    }


def _serialize_search_run(run: SearchRun) -> dict[str, Any]:
    ordered_matches = sorted(run.matches, key=lambda item: item.rank)
    return {
        "id": run.id,
        "hero_id": run.hero_id,
        "mode": run.mode,
        "status": run.status,
        "search_backend": run.search_backend,
        "hero_regime_code": run.hero_regime_code,
        "selected_window": run.selected_window_json,
        "effective_hero_window": run.effective_window_json,
        "hero": run.hero_snapshot_json,
        "matches": [_serialize_match(match) for match in ordered_matches],
        "created_at": run.created_at.isoformat(),
        "completed_at": run.completed_at.isoformat(),
    }


def list_search_runs_for_hero(session: Session, hero_id: int) -> list[dict[str, Any]]:
    runs = session.scalars(
        select(SearchRun)
        .where(SearchRun.hero_id == hero_id)
        .options(selectinload(SearchRun.matches))
        .order_by(SearchRun.created_at.desc())
    ).all()

    summaries = []
    for run in runs:
        ordered_matches = sorted(run.matches, key=lambda item: item.rank)
        top_match = ordered_matches[0] if ordered_matches else None
        summaries.append(
            {
                "id": run.id,
                "hero_id": run.hero_id,
                "mode": run.mode,
                "status": run.status,
                "search_backend": run.search_backend,
                "hero_regime_code": run.hero_regime_code,
                "created_at": run.created_at.isoformat(),
                "top_match": (
                    {
                        "ticker": top_match.ticker,
                        "name": top_match.name,
                        "score": top_match.score,
                    }
                    if top_match is not None
                    else None
                ),
            }
        )
    return summaries


def get_search_run(session: Session, search_run_id: int) -> dict[str, Any] | None:
    run = session.scalar(
        select(SearchRun)
        .where(SearchRun.id == search_run_id)
        .options(selectinload(SearchRun.matches))
    )
    if run is None:
        return None
    return _serialize_search_run(run)


def _build_search_payload(hero: Hero, mode: Mode) -> dict[str, Any]:
    validate_hero_window(hero.ticker, hero.start_date, hero.end_date)

    if mode == "price_dna":
        return _build_price_dna_run(hero)
    if mode == "economic_dna":
        return _build_economic_dna_run(hero)
    if mode == "social_dna":
        return _build_social_dna_run(hero)
    raise ValueError(f"Unsupported search mode: {mode}")


def run_search_for_hero(session: Session, hero_id: int, mode: Mode) -> dict[str, Any]:
    hero = session.get(Hero, hero_id)
    if hero is None:
        raise LookupError(f"Hero {hero_id} was not found")

    payload = _build_search_payload(hero, mode)

    search_run = SearchRun(
        hero_id=hero.id,
        mode=mode,
        status="completed",
        search_backend=str(payload["search_backend"]),
        hero_regime_code=str(payload["hero_regime_code"]),
        selected_window_json=_to_json_ready(payload["selected_window"]),
        effective_window_json=_to_json_ready(payload["effective_hero_window"]),
        hero_snapshot_json=_to_json_ready(payload["hero"]),
    )
    session.add(search_run)
    session.flush()

    for index, item in enumerate(payload["matches"], start=1):
        session.add(
            MatchResult(
                search_run_id=search_run.id,
                rank=index,
                ticker=str(item["ticker"]),
                name=str(item.get("name") or item["ticker"]),
                score=float(item.get("score") or 0.0),
                regime_label=str(item.get("regime_label") or ""),
                sector=str(item.get("sector") or "Unknown"),
                explanation=str(item.get("explanation") or ""),
                matched_window_json=_to_json_ready(item.get("matched_window")),
                features_json=_to_json_ready(item.get("features")),
                series_json=_to_json_ready(item.get("series")),
            )
        )

    session.commit()
    return get_search_run(session, search_run.id)


def seed_sample_heroes(session: Session) -> None:
    has_heroes = session.scalar(select(Hero.id).limit(1))
    if has_heroes is not None:
        return

    for hero_data in _load_curated_heroes().values():
        try:
            create_or_update_hero(
                session,
                HeroCreate(
                    ticker=str(hero_data["ticker"]).upper(),
                    title=str(hero_data.get("window_label") or ""),
                    notes=str(hero_data.get("summary") or ""),
                    start_date=date.fromisoformat(str(hero_data["start_date"])),
                    end_date=date.fromisoformat(str(hero_data["end_date"])),
                ),
            )
        except (LookupError, ValueError):
            session.rollback()

def archive_hero(session: Session, hero_id: int) -> dict[str, Any]:
    hero = session.get(Hero, hero_id)
    if hero is None: 
        raise LookupError(f"Hero {hero_id} was not found")
    
    hero.status = "archived"
    session.commit()
    session.refresh(hero)
    return _hero_response(hero)

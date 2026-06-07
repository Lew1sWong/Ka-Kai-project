# Backend: server
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from mirrorquant_demo.database import SessionLocal, get_session, init_database
from mirrorquant_demo.schemas import HeroCreate, SearchRunCreate
from mirrorquant_demo.search_service import (
    create_or_update_hero,
    get_saved_hero,
    get_search_run,
    list_saved_heroes,
    list_search_runs_for_hero,
    run_search_for_hero,
    seed_sample_heroes,
    validate_hero_window,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
PRICES_PATH = DATA_DIR / "prices.csv"
MARKET_WATCH_PRICES_PATH = DATA_DIR / "market_watch_prices.csv"
MARKET_WATCH_SYMBOLS = {
    "SPY": "US Equities",
    "QQQ": "Growth Leadership",
    "IWM": "Small-Cap Breadth",
    "TLT": "Duration / Rates",
    "HYG": "Credit Appetite",
}


def _load_json(filename: str):
    with (DATA_DIR / filename).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_prices(path: Path = PRICES_PATH) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    return df.sort_values(["ticker", "date"]).copy()


def _get_price_window(
    df: pd.DataFrame,
    ticker: str,
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
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


def _trend_status(change_pct: float) -> str:
    if change_pct >= 0.05:
        return "Uptrend"
    if change_pct <= -0.05:
        return "Drawdown"
    return "Range-bound"


def _market_watch_headline(changes: dict[str, float]) -> str:
    positive_count = sum(change > 0 for change in changes.values())
    if (
        changes.get("SPY", 0) > 0
        and changes.get("QQQ", 0) > 0
        and changes.get("HYG", 0) > 0
    ):
        return "Risk-on with broad support"
    if positive_count <= 1 and changes.get("TLT", 0) < 0:
        return "Risk-off with rate pressure"
    return "Mixed tape with selective leadership"


def _build_live_market_watch() -> dict | None:
    if not MARKET_WATCH_PRICES_PATH.exists():
        return None

    df = _load_prices(MARKET_WATCH_PRICES_PATH)
    indicators = []
    changes: dict[str, float] = {}

    for ticker, label in MARKET_WATCH_SYMBOLS.items():
        window_df = df[df["ticker"] == ticker].sort_values("date").tail(40).copy()
        if len(window_df) < 2:
            continue

        first_close = float(window_df["close"].iloc[0])
        last_close = float(window_df["close"].iloc[-1])
        change_pct = (last_close / first_close) - 1.0
        changes[ticker] = change_pct

        indicators.append(
            {
                "symbol": ticker,
                "name": label,
                "value": f"{last_close:.2f}",
                "status": _trend_status(change_pct),
                "insight": (
                    f"{ticker} moved {change_pct * 100:+.1f}% over the latest "
                    f"{len(window_df)} sessions, giving a live read on {label.lower()}."
                ),
                "series": _serialize_close_series(window_df),
                "change_pct": round(change_pct * 100, 2),
                "as_of": window_df["date"].iloc[-1].strftime("%Y-%m-%d"),
            }
        )

    if not indicators:
        return None

    as_of = max(indicator["as_of"] for indicator in indicators)
    return {
        "as_of": as_of,
        "headline_regime": _market_watch_headline(changes),
        "indicators": indicators,
    }


app = FastAPI(
    title="MirrorQuant API",
    version="0.1.0",
    description="API for the MirrorQuant product workflow.",
)


@app.on_event("startup")
def startup():
    init_database()
    with SessionLocal() as session:
        seed_sample_heroes(session)


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/static/{asset_path:path}", include_in_schema=False)
async def static_files(asset_path: str):
    asset = STATIC_DIR / asset_path
    if not asset.exists() or not asset.is_file():
        raise HTTPException(status_code=404, detail="Static asset not found")
    return FileResponse(asset)


@app.get("/health")
async def health():
    return {"status": "ok", "app": "mirrorquant"}


@app.get("/api/heroes")
async def list_heroes(session: Session = Depends(get_session)):
    return {"heroes": list_saved_heroes(session)}


@app.post("/api/heroes")
async def create_hero(payload: HeroCreate, session: Session = Depends(get_session)):
    try:
        return create_or_update_hero(session, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/heroes/{hero_id}")
async def get_hero(hero_id: int, session: Session = Depends(get_session)):
    hero = get_saved_hero(session, hero_id)
    if hero is None:
        raise HTTPException(status_code=404, detail=f"Hero {hero_id} was not found")
    return hero


@app.get("/api/heroes/{hero_id}/search-runs")
async def list_hero_search_runs(hero_id: int, session: Session = Depends(get_session)):
    hero = get_saved_hero(session, hero_id)
    if hero is None:
        raise HTTPException(status_code=404, detail=f"Hero {hero_id} was not found")
    return {"search_runs": list_search_runs_for_hero(session, hero_id)}


@app.post("/api/heroes/{hero_id}/search-runs")
async def create_search_run(
    hero_id: int,
    payload: SearchRunCreate,
    session: Session = Depends(get_session),
):
    try:
        return run_search_for_hero(session, hero_id, payload.mode)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/search-runs/{search_run_id}")
async def get_saved_search_run(search_run_id: int, session: Session = Depends(get_session)):
    run = get_search_run(session, search_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Search run {search_run_id} was not found")
    return run


@app.get("/api/price-series")
async def get_price_series(ticker: str, start_date: str, end_date: str):
    try:
        validate_hero_window(
            ticker=ticker.upper(),
            start_date=pd.to_datetime(start_date).date(),
            end_date=pd.to_datetime(end_date).date(),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    df = _load_prices()
    ticker_df = df[df["ticker"] == ticker.upper()].sort_values("date").copy()
    window_df = _get_price_window(df, ticker, start_date, end_date)

    return {
        "ticker": ticker.upper(),
        "available_start_date": ticker_df["date"].iloc[0].strftime("%Y-%m-%d"),
        "available_end_date": ticker_df["date"].iloc[-1].strftime("%Y-%m-%d"),
        "start_date": start_date,
        "end_date": end_date,
        "series": _serialize_close_series(ticker_df),
        "window_series": _serialize_close_series(window_df),
    }


@app.get("/api/market-watch")
async def get_market_watch():
    live_market_watch = _build_live_market_watch()
    if live_market_watch is not None:
        return live_market_watch
    return _load_json("market_watch.json")


@app.get("/api/industry-chain/{ticker}")
async def get_industry_chain(ticker: str):
    chain_data = _load_json("industry_chain.json")
    normalized = ticker.upper()
    return {"ticker": normalized, "relationships": chain_data.get(normalized, [])}

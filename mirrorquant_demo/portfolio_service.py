"""Module C — Portfolio Risk-Assistance Analysis service layer.

Pure-Python / pandas analytics over a user's portfolios. No FastAPI coupling:
the router calls these functions, maps exceptions to HTTP codes, and attaches the
compliance block. Functions are user-scoped — every read/write is filtered by
``user_id`` so one analyst can never touch another's portfolio.

The risk analysis loads ``data/prices.csv`` and computes, over the latest ~120
trading sessions:

  - per-holding normalized weights and grouped sector exposure,
  - concentration (max weight, top holding, Herfindahl-Hirschman Index),
  - correlation (average pairwise correlation + most-correlated pairs),
  - recent performance (per-ticker window return + portfolio weighted return),
  - risk alerts for high concentration, high correlation, and deep drawdowns.

Tickers missing from ``prices.csv`` are skipped (and reported under ``notes``) so
a single bad symbol never breaks the analysis.
"""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from mirrorquant_demo.portfolio_models import Holding, Portfolio

DATA_DIR = Path(__file__).resolve().parent / "data"
PRICES_PATH = DATA_DIR / "prices.csv"

# Number of most-recent trading sessions used for the rolling analysis window.
WINDOW_SESSIONS = 120

# Risk-alert thresholds.
HHI_THRESHOLD = 0.25
MAX_WEIGHT_THRESHOLD = 0.40
AVG_CORRELATION_THRESHOLD = 0.70
DRAWDOWN_THRESHOLD = -0.20


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# CRUD helpers (all user-scoped)
# --------------------------------------------------------------------------- #
def create_portfolio(session: Session, user_id: int, name: str) -> Portfolio:
    """Create a new, empty portfolio owned by ``user_id``."""
    clean = (name or "").strip()
    if not clean:
        raise ValueError("Portfolio name must not be empty.")
    portfolio = Portfolio(user_id=user_id, name=clean)
    session.add(portfolio)
    session.commit()
    session.refresh(portfolio)
    return portfolio


def get_portfolio(session: Session, user_id: int, portfolio_id: int) -> Portfolio:
    """Fetch one portfolio (with holdings) scoped to ``user_id``.

    Raises ``LookupError`` if it does not exist or belongs to another user.
    """
    stmt = (
        select(Portfolio)
        .where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
        .options(selectinload(Portfolio.holdings))
    )
    portfolio = session.execute(stmt).scalar_one_or_none()
    if portfolio is None:
        raise LookupError(f"Portfolio {portfolio_id} not found.")
    return portfolio


def list_portfolios(session: Session, user_id: int) -> list[Portfolio]:
    """All portfolios owned by ``user_id``, newest first, with holdings loaded."""
    stmt = (
        select(Portfolio)
        .where(Portfolio.user_id == user_id)
        .options(selectinload(Portfolio.holdings))
        .order_by(Portfolio.created_at.desc(), Portfolio.id.desc())
    )
    return list(session.execute(stmt).scalars().all())


def import_holdings(
    session: Session,
    user_id: int,
    portfolio_id: int,
    items: list[dict[str, Any]],
) -> Portfolio:
    """Replace a portfolio's holdings with ``items``.

    Each item is ``{ticker, weight?, shares?, sector?}``. Resulting weights are
    normalized to sum to 1.0:

      - if any item provides a ``weight``, weights are taken from those values
        (missing -> 0) and normalized;
      - otherwise weights are derived from ``shares * latest_price`` and
        normalized (tickers with no price are treated as zero notional).

    Raises ``LookupError`` if the portfolio is missing, ``ValueError`` on bad input.
    """
    portfolio = get_portfolio(session, user_id, portfolio_id)

    if not items:
        raise ValueError("No holdings provided.")

    parsed: list[dict[str, Any]] = []
    for raw in items:
        ticker = str(raw.get("ticker", "")).strip().upper()
        if not ticker:
            raise ValueError("Each holding requires a 'ticker'.")
        entry: dict[str, Any] = {"ticker": ticker, "sector": _clean_sector(raw.get("sector"))}
        entry["weight"] = _coerce_float(raw.get("weight"), "weight")
        entry["shares"] = _coerce_float(raw.get("shares"), "shares")
        parsed.append(entry)

    use_weights = any(item["weight"] is not None for item in parsed)
    if use_weights:
        weights = [item["weight"] or 0.0 for item in parsed]
    else:
        latest = _latest_prices()
        weights = []
        for item in parsed:
            shares = item["shares"] or 0.0
            price = latest.get(item["ticker"], 0.0)
            weights.append(shares * price)

    total = sum(w for w in weights if w > 0)
    normalized: list[float | None]
    if total > 0:
        normalized = [(w / total if w and w > 0 else 0.0) for w in weights]
    else:
        # No usable weight/notional signal — fall back to equal weighting.
        equal = 1.0 / len(parsed)
        normalized = [equal] * len(parsed)

    # Replace existing holdings (cascade delete-orphan handles removal).
    portfolio.holdings.clear()
    session.flush()
    for item, weight in zip(parsed, normalized):
        portfolio.holdings.append(
            Holding(
                ticker=item["ticker"],
                weight=weight,
                shares=item["shares"],
                sector=item["sector"],
            )
        )
    portfolio.updated_at = _utcnow()
    session.commit()
    session.refresh(portfolio)
    return portfolio


# --------------------------------------------------------------------------- #
# Risk-assistance analysis
# --------------------------------------------------------------------------- #
def analyze_portfolio(
    session: Session,
    user_id: int,
    portfolio_id: int,
) -> dict[str, Any]:
    """Compute a risk-assistance summary for one portfolio.

    Returns a plain dict (the router attaches the compliance block). Never raises
    for analytical edge cases (missing prices, single holding) — it degrades and
    records human-readable ``notes`` instead.
    """
    portfolio = get_portfolio(session, user_id, portfolio_id)
    holdings = list(portfolio.holdings)

    notes: list[str] = []

    if not holdings:
        return {
            "portfolio_id": portfolio.id,
            "name": portfolio.name,
            "as_of": _utcnow().isoformat(),
            "window_sessions": WINDOW_SESSIONS,
            "holdings_count": 0,
            "weights": {},
            "sector_exposure": {},
            "concentration": {"max_weight": 0.0, "top_holding": None, "hhi": 0.0},
            "correlation": {"avg_pairwise_correlation": None, "most_correlated_pairs": []},
            "recent_performance": {"per_ticker": {}, "portfolio_weighted_return": None},
            "risk_alerts": [],
            "notes": ["Portfolio has no holdings; nothing to analyze."],
        }

    # Re-normalize stored weights defensively (treat missing as 0).
    raw_weights = {h.ticker: (h.weight or 0.0) for h in holdings}
    weight_total = sum(w for w in raw_weights.values() if w > 0)
    if weight_total > 0:
        weights = {t: (w / weight_total if w > 0 else 0.0) for t, w in raw_weights.items()}
    else:
        equal = 1.0 / len(holdings)
        weights = {h.ticker: equal for h in holdings}
        notes.append("No positive weights stored; assuming equal weighting.")

    sector_exposure = _sector_exposure(holdings, weights)

    # --- price-driven analytics -------------------------------------------- #
    returns = _load_returns(list(weights.keys()), notes)

    correlation = _correlation_summary(returns)
    recent_performance = _recent_performance(returns, weights, notes)

    concentration = _concentration_summary(weights)

    risk_alerts = _build_alerts(
        concentration=concentration,
        correlation=correlation,
        recent_performance=recent_performance,
    )

    return {
        "portfolio_id": portfolio.id,
        "name": portfolio.name,
        "as_of": _utcnow().isoformat(),
        "window_sessions": WINDOW_SESSIONS,
        "holdings_count": len(holdings),
        "weights": {t: round(w, 6) for t, w in weights.items()},
        "sector_exposure": sector_exposure,
        "concentration": concentration,
        "correlation": correlation,
        "recent_performance": recent_performance,
        "risk_alerts": risk_alerts,
        "notes": notes,
    }


# --------------------------------------------------------------------------- #
# Internal: pricing & math
# --------------------------------------------------------------------------- #
def _load_prices() -> pd.DataFrame:
    if not PRICES_PATH.exists():
        return pd.DataFrame(columns=["ticker", "date", "open", "high", "low", "close", "volume"])
    df = pd.read_csv(PRICES_PATH, parse_dates=["date"])
    df["ticker"] = df["ticker"].astype(str).str.upper()
    return df.sort_values(["ticker", "date"]).copy()


def _latest_prices() -> dict[str, float]:
    """Most recent close per ticker (uppercased)."""
    df = _load_prices()
    if df.empty:
        return {}
    latest = df.groupby("ticker").tail(1)
    return {row.ticker: float(row.close) for row in latest.itertuples(index=False)}


def _load_returns(tickers: list[str], notes: list[str]) -> pd.DataFrame:
    """Per-ticker daily simple returns over the latest ``WINDOW_SESSIONS`` sessions.

    Returns a DataFrame indexed by date with one column per *available* ticker.
    Tickers absent from prices.csv are skipped and reported via ``notes``.
    """
    df = _load_prices()
    available = set(df["ticker"].unique()) if not df.empty else set()

    series: dict[str, pd.Series] = {}
    for ticker in tickers:
        if ticker not in available:
            notes.append(f"{ticker}: no price history in prices.csv; skipped from price analytics.")
            continue
        closes = (
            df[df["ticker"] == ticker]
            .set_index("date")["close"]
            .astype(float)
            .tail(WINDOW_SESSIONS)
        )
        if len(closes) < 2:
            notes.append(f"{ticker}: insufficient price history; skipped from price analytics.")
            continue
        series[ticker] = closes

    if not series:
        return pd.DataFrame()

    closes_df = pd.DataFrame(series).sort_index()
    returns = closes_df.pct_change().dropna(how="all")
    return returns


def _concentration_summary(weights: dict[str, float]) -> dict[str, Any]:
    if not weights:
        return {"max_weight": 0.0, "top_holding": None, "hhi": 0.0}
    top_holding = max(weights, key=lambda t: weights[t])
    max_weight = weights[top_holding]
    hhi = sum(w * w for w in weights.values())
    return {
        "max_weight": round(max_weight, 6),
        "top_holding": top_holding,
        "hhi": round(hhi, 6),
    }


def _correlation_summary(returns: pd.DataFrame) -> dict[str, Any]:
    if returns.empty or returns.shape[1] < 2:
        return {"avg_pairwise_correlation": None, "most_correlated_pairs": []}

    corr = returns.corr()
    pairs: list[dict[str, Any]] = []
    values: list[float] = []
    for a, b in combinations(corr.columns, 2):
        value = corr.loc[a, b]
        if pd.isna(value):
            continue
        value = float(value)
        values.append(value)
        pairs.append({"pair": [a, b], "correlation": round(value, 4)})

    if not values:
        return {"avg_pairwise_correlation": None, "most_correlated_pairs": []}

    avg = sum(values) / len(values)
    top_pairs = sorted(pairs, key=lambda p: p["correlation"], reverse=True)[:3]
    return {
        "avg_pairwise_correlation": round(avg, 4),
        "most_correlated_pairs": top_pairs,
    }


def _recent_performance(
    returns: pd.DataFrame,
    weights: dict[str, float],
    notes: list[str],
) -> dict[str, Any]:
    if returns.empty:
        return {"per_ticker": {}, "portfolio_weighted_return": None}

    per_ticker: dict[str, dict[str, float]] = {}
    portfolio_return = 0.0
    weighted_coverage = 0.0
    for ticker in returns.columns:
        r = returns[ticker].dropna()
        if r.empty:
            continue
        # Cumulative window return and max drawdown of the cumulative curve.
        growth = (1.0 + r).cumprod()
        window_return = float(growth.iloc[-1] - 1.0)
        running_max = growth.cummax()
        drawdown = float((growth / running_max - 1.0).min())
        per_ticker[ticker] = {
            "window_return": round(window_return, 6),
            "max_drawdown": round(drawdown, 6),
        }
        weight = weights.get(ticker, 0.0)
        portfolio_return += weight * window_return
        weighted_coverage += weight

    if weighted_coverage <= 0:
        return {"per_ticker": per_ticker, "portfolio_weighted_return": None}

    # Re-scale by covered weight so skipped tickers don't dilute the figure.
    if weighted_coverage < 0.999:
        notes.append(
            f"Portfolio weighted return covers {round(weighted_coverage * 100, 1)}% of weight "
            "(remaining holdings lack price data)."
        )
        portfolio_return = portfolio_return / weighted_coverage

    return {
        "per_ticker": per_ticker,
        "portfolio_weighted_return": round(portfolio_return, 6),
    }


def _build_alerts(
    *,
    concentration: dict[str, Any],
    correlation: dict[str, Any],
    recent_performance: dict[str, Any],
) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []

    hhi = concentration.get("hhi") or 0.0
    max_weight = concentration.get("max_weight") or 0.0
    top_holding = concentration.get("top_holding")
    if hhi > HHI_THRESHOLD or max_weight > MAX_WEIGHT_THRESHOLD:
        alerts.append(
            {
                "level": "warning",
                "code": "high_concentration",
                "message": (
                    f"Portfolio is concentrated (HHI {hhi:.2f}, "
                    f"top holding {top_holding} at {max_weight:.0%}). "
                    "Consider whether single-name exposure is intended."
                ),
            }
        )

    avg_corr = correlation.get("avg_pairwise_correlation")
    if avg_corr is not None and avg_corr > AVG_CORRELATION_THRESHOLD:
        alerts.append(
            {
                "level": "warning",
                "code": "high_correlation",
                "message": (
                    f"Holdings move closely together (avg pairwise correlation {avg_corr:.2f}); "
                    "diversification benefit may be limited."
                ),
            }
        )

    per_ticker = recent_performance.get("per_ticker") or {}
    for ticker, stats in per_ticker.items():
        drawdown = stats.get("max_drawdown")
        if drawdown is not None and drawdown < DRAWDOWN_THRESHOLD:
            alerts.append(
                {
                    "level": "warning",
                    "code": "deep_drawdown",
                    "message": (
                        f"{ticker} drew down {drawdown:.0%} over the window; "
                        "review position sizing and risk tolerance."
                    ),
                }
            )

    if not alerts:
        alerts.append(
            {
                "level": "info",
                "code": "no_alerts",
                "message": "No concentration, correlation, or drawdown alerts triggered over the window.",
            }
        )

    return alerts


# --------------------------------------------------------------------------- #
# Internal: small helpers
# --------------------------------------------------------------------------- #
def _sector_exposure(holdings: list[Holding], weights: dict[str, float]) -> dict[str, float]:
    exposure: dict[str, float] = {}
    for holding in holdings:
        sector = holding.sector or "Unknown"
        exposure[sector] = exposure.get(sector, 0.0) + weights.get(holding.ticker, 0.0)
    return {sector: round(value, 6) for sector, value in exposure.items()}


def _clean_sector(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_float(value: Any, field: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid '{field}' value: {value!r}") from exc

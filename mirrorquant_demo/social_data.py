from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

from mirrorquant_demo.economic_data import (
    build_stock_window_features,
    get_latest_price_window,
    get_price_window,
    serialize_close_series,
)

BASE_PROFILE = {
    "base_sentiment": 0.62,
    "attention_base": 0.60,
    "controversy_base": 0.32,
    "analyst_attention": 0.60,
    "reliability": 0.58,
    "theme_ai": 0.30,
    "theme_innovation": 0.45,
    "defensive_credibility": 0.45,
}

COMPANY_METADATA = {
    "AAPL": {"name": "Apple", "sector": "Consumer Tech"},
    "AMD": {"name": "AMD", "sector": "Semiconductors"},
    "AVGO": {"name": "Broadcom", "sector": "Semiconductors"},
    "GOOGL": {"name": "Alphabet", "sector": "Internet"},
    "LLY": {"name": "Eli Lilly", "sector": "Pharma"},
    "META": {"name": "Meta", "sector": "Internet"},
    "MSFT": {"name": "Microsoft", "sector": "Software"},
    "NVDA": {"name": "NVIDIA", "sector": "Semiconductors"},
}

FEATURE_WEIGHTS = {
    "sentiment_level": 0.24,
    "attention_intensity": 0.20,
    "controversy_level": 0.16,
    "analyst_attention": 0.10,
    "theme_ai": 0.12,
    "theme_innovation": 0.08,
    "defensive_credibility": 0.05,
    "sentiment_persistence": 0.05,
}


def load_social_profiles(path: str | Path) -> dict[str, dict[str, float]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw_profiles = json.load(handle)

    normalized = {}
    for ticker, values in raw_profiles.items():
        profile = dict(BASE_PROFILE)
        profile.update({key: float(value) for key, value in values.items()})
        normalized[ticker.upper()] = profile

    return normalized


def load_social_signals(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        return pd.DataFrame()

    df = pd.read_csv(csv_path, parse_dates=["date"])
    if df.empty:
        return df

    df["ticker"] = df["ticker"].astype(str).str.upper()
    return df.sort_values(["ticker", "date"]).reset_index(drop=True)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _bounded_signal(value: float, scale: float) -> float:
    if scale == 0:
        return 0.0
    return float(math.tanh(value / scale))


def _round_feature_dict(features: dict[str, float]) -> dict[str, float]:
    rounded = {}
    for key, value in features.items():
        if isinstance(value, (int, float)):
            rounded[key] = round(float(value), 4)
        else:
            rounded[key] = value
    return rounded


def _profile_for_ticker(
    profiles: dict[str, dict[str, float]],
    ticker: str,
) -> dict[str, float]:
    profile = dict(BASE_PROFILE)
    profile.update(profiles.get(ticker.upper(), {}))
    return profile


def _build_proxy_features(
    window_df: pd.DataFrame,
    profile: dict[str, float],
) -> dict[str, float]:
    ordered = window_df.sort_values("date").copy()
    ordered["daily_return"] = ordered["close"].pct_change().fillna(0.0)
    ordered["volume_change"] = (
        ordered["volume"].pct_change().replace([math.inf, -math.inf], 0.0).fillna(0.0)
    )

    stock_features = build_stock_window_features(ordered)
    first_volume = float(ordered["volume"].head(min(5, len(ordered))).mean())
    last_volume = float(ordered["volume"].tail(min(5, len(ordered))).mean())
    volume_trend = (last_volume / max(first_volume, 1.0)) - 1.0
    up_day_ratio = float((ordered["daily_return"] > 0).mean())

    return_signal = _bounded_signal(stock_features["total_return"], 0.35)
    volume_signal = _bounded_signal(volume_trend, 0.75)
    volatility_penalty = _clamp01(stock_features["volatility"] / 0.05)
    drawdown_penalty = _clamp01(abs(stock_features["max_drawdown"]) / 0.20)

    sentiment_level = _clamp01(
        profile["base_sentiment"]
        + (0.16 * return_signal)
        - (0.10 * volatility_penalty)
        - (0.08 * drawdown_penalty)
    )
    attention_intensity = _clamp01(
        profile["attention_base"]
        + (0.14 * abs(return_signal))
        + (0.10 * max(volume_signal, 0.0))
    )
    controversy_level = _clamp01(
        profile["controversy_base"]
        + (0.18 * volatility_penalty)
        + (0.10 * max(-return_signal, 0.0))
        + (0.06 * drawdown_penalty)
    )
    analyst_attention = _clamp01(
        profile["analyst_attention"]
        + (0.06 * abs(return_signal))
        + (0.04 * max(volume_signal, 0.0))
    )
    sentiment_persistence = _clamp01(
        (0.40 * up_day_ratio)
        + (0.25 * (1 - volatility_penalty))
        + (0.20 * max(return_signal, 0.0))
        + (0.15 * profile["reliability"])
    )

    return {
        "sentiment_level": sentiment_level,
        "attention_intensity": attention_intensity,
        "controversy_level": controversy_level,
        "analyst_attention": analyst_attention,
        "theme_ai": _clamp01(profile["theme_ai"]),
        "theme_innovation": _clamp01(profile["theme_innovation"]),
        "defensive_credibility": _clamp01(profile["defensive_credibility"]),
        "sentiment_persistence": sentiment_persistence,
        "total_return": float(stock_features["total_return"]),
        "volatility": float(stock_features["volatility"]),
        "max_drawdown": float(stock_features["max_drawdown"]),
        "up_day_ratio": up_day_ratio,
        "volume_trend": float(volume_trend),
        "data_backend": "proxy",
    }


def _get_signal_window(
    signals_df: pd.DataFrame | None,
    ticker: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    if signals_df is None or signals_df.empty:
        return pd.DataFrame()

    return signals_df[
        (signals_df["ticker"] == ticker.upper())
        & (signals_df["date"] >= pd.to_datetime(start_date))
        & (signals_df["date"] <= pd.to_datetime(end_date))
    ].sort_values("date").copy()


def _build_signal_features(
    signal_window: pd.DataFrame,
    price_window: pd.DataFrame,
) -> dict[str, float]:
    weighted_count = signal_window["article_count"].clip(lower=1)
    total_articles = float(weighted_count.sum())
    total_days = max(len(price_window), 1)
    active_days = max(len(signal_window), 1)

    sentiment_mean = float(
        (signal_window["sentiment_score"] * weighted_count).sum() / total_articles
    )
    negative_mean = float(
        (signal_window["negative_share"] * weighted_count).sum() / total_articles
    )
    controversy_mean = float(
        (signal_window["controversy_score"] * weighted_count).sum() / total_articles
    )
    analyst_mean = float(
        (signal_window["analyst_attention"] * weighted_count).sum() / total_articles
    )
    theme_ai_mean = float((signal_window["theme_ai"] * weighted_count).sum() / total_articles)
    theme_innovation_mean = float(
        (signal_window["theme_innovation"] * weighted_count).sum() / total_articles
    )
    credibility_mean = float(
        (signal_window["credibility_score"] * weighted_count).sum() / total_articles
    )
    daily_article_rate = total_articles / total_days
    daily_source_rate = float(signal_window["source_count"].sum()) / total_days
    positive_day_ratio = float((signal_window["sentiment_score"] > 0.12).mean())
    attention_intensity = _clamp01(
        0.55 * min(daily_article_rate / 3.0, 1.0)
        + 0.25 * min(daily_source_rate / 2.5, 1.0)
        + 0.20 * float(signal_window["mention_intensity"].mean())
    )
    controversy_level = _clamp01((0.65 * controversy_mean) + (0.35 * negative_mean))
    sentiment_persistence = _clamp01(
        0.50 * positive_day_ratio
        + 0.25 * (1 - float(signal_window["sentiment_score"].std(ddof=0) or 0.0))
        + 0.25 * float(signal_window["positive_share"].mean())
    )

    return {
        "sentiment_level": _clamp01(0.5 + (0.5 * sentiment_mean)),
        "attention_intensity": attention_intensity,
        "controversy_level": controversy_level,
        "analyst_attention": _clamp01(analyst_mean),
        "theme_ai": _clamp01(theme_ai_mean),
        "theme_innovation": _clamp01(theme_innovation_mean),
        "defensive_credibility": _clamp01(credibility_mean * (1 - controversy_level / 2)),
        "sentiment_persistence": sentiment_persistence,
        "news_article_count": total_articles,
        "news_active_days": float(active_days),
        "data_backend": "news",
    }


def _merge_features(
    proxy_features: dict[str, float],
    signal_features: dict[str, float] | None,
) -> dict[str, float]:
    if not signal_features:
        return proxy_features

    total_articles = signal_features.get("news_article_count", 0.0)
    observed_weight = _clamp01(total_articles / 18.0)
    observed_weight = max(0.35, observed_weight)
    merged = dict(proxy_features)

    for key in FEATURE_WEIGHTS:
        merged[key] = _clamp01(
            ((1 - observed_weight) * proxy_features[key])
            + (observed_weight * signal_features[key])
        )

    merged["data_backend"] = "news_blend"
    merged["news_article_count"] = total_articles
    merged["news_active_days"] = signal_features.get("news_active_days", 0.0)
    return merged


def build_social_window_features(
    window_df: pd.DataFrame,
    profile: dict[str, float],
    signal_window: pd.DataFrame | None = None,
) -> dict[str, float]:
    if window_df.empty:
        raise ValueError("Cannot build Social DNA features from an empty window")

    proxy_features = _build_proxy_features(window_df, profile)
    if signal_window is None or signal_window.empty:
        return proxy_features

    signal_features = _build_signal_features(signal_window, window_df)
    return _merge_features(proxy_features, signal_features)


def build_social_traits(features: dict[str, float]) -> list[str]:
    traits: list[str] = []

    if features["theme_ai"] >= 0.75 and features["attention_intensity"] >= 0.75:
        traits.append("AI narrative drift")
    if features["theme_innovation"] >= 0.75 and features["controversy_level"] <= 0.40:
        traits.append("Credible innovation coverage")
    if features["defensive_credibility"] >= 0.72 and features["controversy_level"] <= 0.38:
        traits.append("Low-drama fundamental narrative")
    if features["analyst_attention"] >= 0.78:
        traits.append("High analyst attention")
    if features["attention_intensity"] >= 0.78:
        traits.append("High media attention")
    if features["sentiment_persistence"] >= 0.66:
        traits.append("Positive sentiment persistence")
    if features["controversy_level"] <= 0.32:
        traits.append("Low controversy relative to buzz")

    if len(traits) < 3 and features["sentiment_level"] >= 0.68:
        traits.append("Constructive sentiment tone")
    if len(traits) < 3 and features["defensive_credibility"] >= 0.60:
        traits.append("Fundamental narrative consistency")
    if len(traits) < 3:
        traits.append("Steady attention profile")

    return traits[:3]


def classify_social_regime(features: dict[str, float]) -> str:
    if features["theme_ai"] >= 0.82 and features["attention_intensity"] >= 0.80:
        return "THEME_DOMINANCE_08"
    if features["theme_ai"] >= 0.68 and features["sentiment_persistence"] >= 0.66:
        return "NARRATIVE_EXPANSION_05"
    if features["theme_innovation"] >= 0.80 and features["controversy_level"] <= 0.38:
        return "CREDIBLE_CATALYST_03"
    if features["defensive_credibility"] >= 0.72 and features["controversy_level"] <= 0.34:
        return "QUALITY_CONFIDENCE_04"
    return "ATTENTION_ROTATION_02"


def regime_label_from_code(regime_code: str) -> str:
    mapping = {
        "THEME_DOMINANCE_08": "Theme dominance",
        "NARRATIVE_EXPANSION_05": "Narrative expansion",
        "CREDIBLE_CATALYST_03": "Credible catalyst",
        "QUALITY_CONFIDENCE_04": "Quality confidence",
        "ATTENTION_ROTATION_02": "Attention rotation",
    }
    return mapping.get(regime_code, regime_code.replace("_", " ").title())


def build_hero_social_dna(
    prices_df: pd.DataFrame,
    profiles: dict[str, dict[str, float]],
    ticker: str,
    start_date: str,
    end_date: str,
    signals_df: pd.DataFrame | None = None,
) -> dict[str, object]:
    hero_window = get_price_window(
        prices_df,
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
    )
    if hero_window.empty:
        raise ValueError(
            f"No price series found for {ticker.upper()} from {start_date} to {end_date}"
        )

    features = build_social_window_features(
        hero_window,
        profile=_profile_for_ticker(profiles, ticker),
        signal_window=_get_signal_window(signals_df, ticker, start_date, end_date),
    )

    return {
        "ticker": ticker.upper(),
        "start_date": start_date,
        "end_date": end_date,
        "features": features,
        "regime_code": classify_social_regime(features),
        "traits": build_social_traits(features),
    }


def social_feature_distance(
    hero_features: dict[str, float],
    candidate_features: dict[str, float],
) -> float:
    squared_diffs = []
    for key, weight in FEATURE_WEIGHTS.items():
        hero_value = hero_features[key]
        candidate_value = candidate_features[key]
        squared_diffs.append(weight * ((hero_value - candidate_value) ** 2))

    return sum(squared_diffs) ** 0.5


def distance_to_score(distance: float) -> float:
    return 1 / (1 + distance)


def _closest_feature_labels(
    hero_features: dict[str, float],
    candidate_features: dict[str, float],
) -> list[str]:
    labels = {
        "sentiment_level": "sentiment tone",
        "attention_intensity": "attention intensity",
        "controversy_level": "controversy profile",
        "analyst_attention": "analyst coverage",
        "theme_ai": "AI narrative exposure",
        "theme_innovation": "innovation narrative",
        "defensive_credibility": "credibility profile",
        "sentiment_persistence": "sentiment persistence",
    }
    ranked = sorted(
        FEATURE_WEIGHTS,
        key=lambda key: abs(hero_features[key] - candidate_features[key]),
    )
    return [labels[key] for key in ranked[:3]]


def build_match_explanation(match: dict[str, object]) -> str:
    features = match["features"]
    closest_labels = _closest_feature_labels(match["hero_features"], features)
    backend = features.get("data_backend", "proxy")
    backend_text = (
        "news + proxy blend"
        if backend == "news_blend"
        else "news-derived"
        if backend == "news"
        else "proxy"
    )
    return (
        f"Closest on {', '.join(closest_labels[:2])}, with similar "
        f"{closest_labels[2]}. Social signal source: {backend_text}. "
        f"Proxy sentiment {features['sentiment_level']:.2f}, attention "
        f"{features['attention_intensity']:.2f}, controversy "
        f"{features['controversy_level']:.2f}."
    )


def find_social_matches(
    prices_df: pd.DataFrame,
    profiles: dict[str, dict[str, float]],
    hero_ticker: str,
    start_date: str,
    end_date: str,
    signals_df: pd.DataFrame | None = None,
) -> list[dict[str, object]]:
    hero_window = get_price_window(prices_df, hero_ticker, start_date, end_date)
    if hero_window.empty:
        raise ValueError(
            f"No price series found for {hero_ticker.upper()} from {start_date} to {end_date}"
        )

    hero_features = build_social_window_features(
        hero_window,
        profile=_profile_for_ticker(profiles, hero_ticker),
        signal_window=_get_signal_window(signals_df, hero_ticker, start_date, end_date),
    )
    window_size = len(hero_window)
    matches: list[dict[str, object]] = []

    for ticker in sorted(prices_df["ticker"].unique()):
        if ticker == hero_ticker.upper():
            continue

        candidate_window = get_latest_price_window(prices_df, ticker, window_size)
        if candidate_window.empty:
            continue

        candidate_start = candidate_window["date"].iloc[0].strftime("%Y-%m-%d")
        candidate_end = candidate_window["date"].iloc[-1].strftime("%Y-%m-%d")
        candidate_features = build_social_window_features(
            candidate_window,
            profile=_profile_for_ticker(profiles, ticker),
            signal_window=_get_signal_window(signals_df, ticker, candidate_start, candidate_end),
        )
        distance = social_feature_distance(hero_features, candidate_features)

        matches.append(
            {
                "ticker": ticker,
                "distance": float(distance),
                "hero_features": hero_features,
                "features": candidate_features,
                "regime_code": classify_social_regime(candidate_features),
                "matched_window": {
                    "start_date": candidate_start,
                    "end_date": candidate_end,
                },
                "series": serialize_close_series(candidate_window),
            }
        )

    matches.sort(key=lambda item: item["distance"])
    return matches


def format_api_matches(matches: list[dict[str, object]]) -> list[dict[str, object]]:
    formatted = []

    for item in matches:
        ticker = item["ticker"]
        metadata = COMPANY_METADATA.get(
            ticker,
            {"name": ticker, "sector": "Unknown"},
        )
        score = round(distance_to_score(item["distance"]), 4)
        regime_label = regime_label_from_code(item["regime_code"])
        formatted.append(
            {
                "ticker": ticker,
                "name": metadata["name"],
                "score": score,
                "regime_label": (
                    f"{regime_label} "
                    f"({item['matched_window']['start_date']} to "
                    f"{item['matched_window']['end_date']})"
                ),
                "sector": metadata["sector"],
                "explanation": build_match_explanation(item),
                "matched_window": item["matched_window"],
                "series": item["series"],
                "social_distance": round(float(item["distance"]), 4),
                "features": _round_feature_dict(item["features"]),
            }
        )

    return formatted

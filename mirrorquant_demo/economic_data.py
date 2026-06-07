import os
from dotenv import load_dotenv

import requests
import pandas as pd

# FRED_URL is the base URL for the Federal Reserve Economic Data (FRED) API, which provides access to a wide range of economic data series. We will be using this URL to fetch various macroeconomic indicators for our analysis.
# Economic_DNA does not use the same 40-day windows of stock price data as the VQ-VAE model, but instead focuses on summarizing the macroeconomic environment and the stock's performance over a specified period. The features we build for the economic DNA are designed to capture the broader economic context in which the stock is operating, as well as key characteristics of the stock's recent performance. This allows us to compare the "economic DNA" of different stocks based on their macroeconomic environment and recent performance, rather than just their price movements in fixed windows.

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"

def fetch_fred_series(series_id: str, api_key: str, start: str = "2018-01-01") -> pd.DataFrame: 
    response = requests.get(
        FRED_URL,
        params={
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json", 
            "observation_start": start, # Only fetch data from 2018 onwards to limit the dataset size
            "sort_order": "asc", # Sort oldest to newest for easier processing later
        },
        timeout=30,
    )
    response.raise_for_status() # Checks if the request succeeded
    payload = response.json() # Parses JSON, converts API response from JSON text into Python data

    rows = []
    for obs in payload["observations"]: 
        if obs["value"] == ".":
            continue 
        rows.append({
            "date": obs["date"],
            "value": float(obs["value"]),
        })

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date")

SERIES_MAP = {
    "cpi": "CPIAUCSL", # Consumer Price Index for All Urban Consumers: Higher values mean consumer prices have risen overall 
    "fedfunds": "FEDFUNDS", # Effective Federal Funds Rate: Interest rate banks charge each other for overnight loans: Higher values indicate tighter monetary policy
    "unrate": "UNRATE", # Unemployment Rate: Percentage of the labor force that is unemployed and actively seeking employment
    "yield_curve": "T10Y2Y", # 10-Year Treasury Constant Maturity Minus 2-Year Treasury Constant Maturity: Spread between long-term and short-term interest rates
    "credit_spread": "BAMLH0A0HYM2", # BofA Merrill Lynch High Yield Index: Spread between high-yield and investment-grade corporate bonds
    "retail_sales": "RSXFS", # Retail Sales: Total sales by retail establishments, excluding cars and gas stations (Indicator of consumer spending)
}

def fetch_all_macro_series(api_key: str, start: str = "2018-01-01") -> pd.DataFrame:
    frames = []

    for series_name, series_id in SERIES_MAP.items(): 
        df = fetch_fred_series(series_id=series_id, api_key=api_key, start=start)

        df["series_name"] = series_name
        df["series_id"] = series_id

        frames.append(df) # Append the DataFrame for this series to the list of frames

    combined = pd.concat(frames, ignore_index=True) # Combine all the individual DataFrames into one large DataFrames
    return combined.sort_values(["series_name", "date"]).reset_index(drop=True) 

def save_macro_data(df: pd.DataFrame, output_path: str) -> None:
    df.to_csv(output_path, index=False) # index=False means we don't want to save the DataFrame's index as a column in the CSV file

def build_macro_snapshot(df: pd.DataFrame, target_date: str) -> dict: 
    target = pd.to_datetime(target_date) # Convert the target date string into a pandas Timestamp object for easier comparison
    snapshot = {}

    for series_name in df["series_name"].unique():
        series_df=df[df["series_name"] == series_name].sort_values("date")
        eligible = series_df[series_df["date"] <= target] # Filter the DataFrame to only include rows where the date is on or before the target date

        if eligible.empty:
            snapshot[series_name] = None
        else:
            latest_row = eligible.iloc[-1] # iloc is pandas' way of selecting rows by integer position. -1 means we want the last row of the eligible DataFrame, which corresponds to the most recent observation on or before the target date
            snapshot[series_name] = latest_row["value"] # Extract the value from the latest row and add it to the snapshot dictionary under the key of the series name
    
    return snapshot

def build_macro_features(df: pd.DataFrame, target_date: str) -> dict:
    target = pd.to_datetime(target_date) # Converts the target date string into a pandas Timestamp

    cpi_df = df[df["series_name"] == "cpi"]
    fedfunds_df = df[df["series_name"] == "fedfunds"]
    unrate_df =  df[df["series_name"] == "unrate"]
    yield_curve_df =  df[df["series_name"] == "yield_curve"]
    credit_spread_df =  df[df["series_name"] == "credit_spread"]
    retail_sales_df =  df[df["series_name"] == "retail_sales"]

    current_cpi = latest_value_before(cpi_df, target)
    cpi_12m_ago = latest_value_before(cpi_df, target - pd.DateOffset(months=12))

    current_fedfunds = latest_value_before(fedfunds_df, target)
    fedfunds_6m_ago = latest_value_before(fedfunds_df, target - pd.DateOffset(months=6))

    current_unrate = latest_value_before(unrate_df, target)
    unrate_6m_ago = latest_value_before(unrate_df, target - pd.DateOffset(months=6))

    current_yield_curve = latest_value_before(yield_curve_df, target)
    current_credit_spread = latest_value_before(credit_spread_df, target)

    current_retail_sales = latest_value_before(retail_sales_df, target)
    retail_sales_12m_ago = latest_value_before(retail_sales_df, target - pd.DateOffset(months=12))

    return {
        "cpi_yoy": ((current_cpi / cpi_12m_ago) - 1) if current_cpi is not None and cpi_12m_ago is not None else None,
        "fedfunds_level": current_fedfunds,
        "fedfunds_6m_change": (current_fedfunds - fedfunds_6m_ago) if current_fedfunds is not None and fedfunds_6m_ago is not None else None,
        "unrate_level": current_unrate,
        "unrate_6m_change": (current_unrate - unrate_6m_ago) if current_unrate is not None and unrate_6m_ago is not None else None,
        "yield_curve_level": current_yield_curve,
        "credit_spread_level": current_credit_spread,
        "retail_sales_yoy": ((current_retail_sales / retail_sales_12m_ago) - 1) if current_retail_sales is not None and retail_sales_12m_ago is not None else None,
    }

def latest_value_before(series_df: pd.DataFrame, target: pd.Timestamp):
    eligible = series_df[series_df["date"] <= target].sort_values("date")

    if eligible.empty:
        return None

    return eligible.iloc[-1]["value"]

def format_macro_features(features: dict) -> dict:
    formatted = {}

    for key, value in features.items():
        if value is None: 
            formatted[key] = None
        else:
            formatted[key] = round(float(value), 4)
    
    return formatted 

def load_prices(path: str) -> pd.DataFrame: 
    df = pd.read_csv(path, parse_dates=["date"])
    return df.sort_values(["ticker", "date"]).reset_index(drop=True)


def serialize_close_series(window_df: pd.DataFrame) -> list[dict[str, str | float]]:
    return [
        {
            "date": row.date.strftime("%Y-%m-%d"),
            "close": float(row.close),
        }
        for row in window_df.itertuples(index=False)
    ]

def get_price_window(
    df: pd.DataFrame,
    ticker: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    window = df[
        (df["ticker"] == ticker.upper())
        & (df["date"] >= pd.to_datetime(start_date))
        & (df["date"] <= pd.to_datetime(end_date))
    ].sort_values("date").copy()

    return window

# max_drawdown measures the worst drop from a previous peak.
def max_drawdown(close_series: pd.Series) -> float: 
    running_max = close_series.cummax()
    drawdown = (close_series - running_max) / running_max
    return float(drawdown.min())

# This function takes one stock window and summarizes it with 3 numbers: total_return, volatility and max_drawdown.
def build_stock_window_features(window_df: pd.DataFrame) -> dict:
    ordered = window_df.sort_values("date").copy()
    ordered["daily_return"] = ordered["close"].pct_change()

    total_return = (ordered["close"].iloc[-1] / ordered["close"].iloc[0]) - 1
    volatility = ordered["daily_return"].dropna().std()
    mdd = max_drawdown(ordered["close"])

    return {
        "total_return": float(total_return),
        "volatility": float(volatility) if pd.notna(volatility) else 0.0,
        "max_drawdown": float(mdd),
    }

def build_hero_economic_dna(
        macro_df: pd.DataFrame, 
        prices_df: pd.DataFrame,
        ticker: str,
        start_date: str, 
        end_date: str,
) -> dict: 
    macro_features = build_macro_features(macro_df, end_date)

    hero_window = get_price_window(
        prices_df, 
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
    )

    stock_features = build_stock_window_features(hero_window)

    return {
        "ticker": ticker.upper(),
        "start_date": start_date,
        "end_date": end_date,
        "macro_features": macro_features,
        "stock_features": stock_features,
    }

# Build stock features for the latest window of any ticker.
def get_latest_price_window(
        df: pd.DataFrame, 
        ticker: str, 
        window_size: int,
        ) -> pd.DataFrame: 
    ticker_df = df[df["ticker"] == ticker.upper()].sort_values("date").copy()

    if (len(ticker_df) < window_size): 
        return pd.DataFrame()
    
    return ticker_df.tail(window_size).copy() # Returns then most recent 'window_size' rows for the specified ticker, which corresponds to the latest price window

# Similarity function that compares the hero's economic DNA to the latest window of another stock, and returns a similarity score based on how close the macro and stock features are. For simplicity, we can use a basic distance metric like Euclidean distance for both macro and stock features, and then combine them into an overall similarity score.
# Euclidean distance
def stock_feature_distance(hero_features: dict, candidate_features: dict) -> float: 
    keys = ["total_return", "volatility", "max_drawdown"] 

    squared_diffs = []
    for key in keys: 
        hero_value = hero_features[key]
        candidate_value = candidate_features[key]
        squared_diffs.append((hero_value - candidate_value) ** 2)

    return sum(squared_diffs) ** 0.5

# Similarity function that compares the macro features of the hero's economic DNA to the macro features of another stock, and returns a similarity score based on how close the macro features are. We can use a similar approach as the stock feature distance, but applied to the macro features instead.
# Euclidean distance
def macro_feature_distance(hero_macro: dict, candidate_macro: dict) -> float:
    keys = [
        "cpi_yoy",
        "fedfunds_level",
        "fedfunds_6m_change",
        "unrate_level",
        "unrate_6m_change",
        "yield_curve_level",    
        "retail_sales_yoy",
    ]

    squared_diffs = []
    for key in keys: 
        hero_value = hero_macro.get(key)
        candidate_value = candidate_macro.get(key)

        if hero_value is None or candidate_value is None:
            continue # Skip features where we don't have data for either the hero or the candidate

        squared_diffs.append((hero_value - candidate_value) ** 2)
    
    if not squared_diffs: 
        return float("inf") # If we don't have any comparable features, return infinite distance to indicate no similarity
    
    return sum(squared_diffs) ** 0.5

# Ranking function that takes a list of candidate stocks, computes their economic DNA, compares it to the hero's DNA, and returns a ranked list of candidates based on similarity.
def find_stock_feature_matches(
        macro_df: pd.DataFrame,
        prices_df: pd.DataFrame, 
        hero_ticker: str,
        start_date: str,
        end_date: str, 
) -> list: 
    hero_window = get_price_window(prices_df, hero_ticker, start_date, end_date)
    hero_features = build_stock_window_features(hero_window)
    hero_macro = build_macro_features(macro_df, end_date)

    window_size = len(hero_window)

    matches = []

    for ticker in prices_df["ticker"].unique():
        if ticker == hero_ticker.upper(): 
            continue # Skip the hero stock itself

        candidate_window = get_latest_price_window(prices_df, ticker, window_size)
        
        if candidate_window.empty: 
            continue # Skip if we don't have enough data for this candidate
        
        candidate_features = build_stock_window_features(candidate_window)

        candidate_end_date = candidate_window["date"].iloc[-1].strftime("%Y-%m-%d")
        candidate_macro = build_macro_features(macro_df, candidate_end_date)
        
        stock_distance = stock_feature_distance(hero_features, candidate_features)
        macro_distance = macro_feature_distance(hero_macro, candidate_macro)
        
        combined_distance = (0.7 * stock_distance) + (0.3 * macro_distance) # Weighted average of stock and macro distances, giving more weight to stock features

        matches.append({
            "ticker": ticker,
            "stock_distance": float(stock_distance),
            "macro_distance": float(macro_distance),
            "distance": float(combined_distance),
            "features": candidate_features,
            "matched_window": {
                "start_date": candidate_window["date"].iloc[0].strftime("%Y-%m-%d"),
                "end_date": candidate_window["date"].iloc[-1].strftime("%Y-%m-%d"),
            },
            "series": serialize_close_series(candidate_window),
        })

    matches.sort(key=lambda item: item["distance"])
    return matches

def distance_to_score(distance: float) -> float: 
    return 1 / (1 + distance)

def format_match_results(matches: list[dict]) -> list[dict]:
    formatted = []
    for match in matches:
        formatted.append({
            "ticker": match["ticker"],
            "similarity_score": round(distance_to_score(match["distance"]), 4),
            "stock_distance": round(match["stock_distance"], 4),
            "macro_distance": round(match["macro_distance"], 4),
            "features": match["features"],
        })
    return formatted

def classify_macro_regime(macro_features: dict) -> str:
    cpi_yoy = macro_features.get("cpi_yoy")
    fedfunds_6m_change = macro_features.get("fedfunds_6m_change")
    unrate_6m_change = macro_features.get("unrate_6m_change")
    yield_curve_level = macro_features.get("yield_curve_level")

    if (
        cpi_yoy is not None
        and fedfunds_6m_change is not None
        and cpi_yoy < 0.03
        and fedfunds_6m_change <= 0
    ):
        return "SOFT_LANDING"

    if (
        fedfunds_6m_change is not None
        and cpi_yoy is not None
        and fedfunds_6m_change > 0
        and cpi_yoy >= 0.03
    ):
        return "TIGHTENING_PRESSURE"

    if unrate_6m_change is not None and unrate_6m_change > 0.3:
        return "DEFENSIVE_GROWTH"

    if yield_curve_level is not None and yield_curve_level < 0:
        return "SELECTIVE_GROWTH"

    return "BALANCED_EXPANSION"

def build_match_explanation(match: dict) -> str:
    features = match["features"]
    stock_distance = match["stock_distance"] 
    macro_distance = match["macro_distance"]

    stock_text = (
        "very similar stock behavior"
        if stock_distance < 0.5
        else "moderately similar stock behavior"
        if stock_distance < 0.35
        else "looser stock behavior similarity"
    )

    macro_text = (
        "strong macro regime alignment"
        if macro_distance < 0.15
        else "moderate macro regime alignment"
        if macro_distance < 0.3 
        else "weaker macro regime alignment"
    )

    return (
        f"{stock_text} with {macro_text}. "
        f"Total return {features['total_return']:.4f}, "
        f"volatility {features['volatility']:.4f}, "
        f"max drawdown {features['max_drawdown']:.4f}."
    )

def format_api_matches(matches: list[dict]) -> list[dict]:
    formatted = []

    for item in matches:
        score = round(distance_to_score(item["distance"]), 4)
        formatted.append({
            "ticker": item["ticker"],
            "name": item["ticker"],
            "score": score,
            "regime_label": f"Economic DNA match ({item['matched_window']['start_date']} to {item['matched_window']['end_date']})",
            "sector": "Unknown",
            "explanation": build_match_explanation(item),
            "matched_window": item["matched_window"],
            "series": item["series"],
            "stock_distance": round(item["stock_distance"], 4),
            "macro_distance": round(item["macro_distance"], 4),
            "features": item["features"],
        })

    return formatted

def main(): 
    load_dotenv()  # Load environment variables from .env file
    api_key = os.getenv("FRED_API_KEY")  # Get the FRED API key from environment variables

    if not api_key: 
        raise RuntimeError("Missing FRED_API_KEY in environment variables. Please set it in your .env file.")
    
    df = fetch_all_macro_series(api_key=api_key)
    save_macro_data(df, "mirrorquant_demo/data/macro_series.csv")
    prices_df = load_prices("mirrorquant_demo/data/prices.csv")

    hero_dna = build_hero_economic_dna(
        macro_df=df, 
        prices_df=prices_df, 
        ticker="MSFT",
        start_date="2023-01-03",
        end_date="2023-04-03",
    )

    matches = find_stock_feature_matches(
        macro_df=df,
        prices_df=prices_df,
        hero_ticker="MSFT",
        start_date="2023-01-03",
        end_date="2023-04-03",
    )

    api_matches = format_api_matches(matches)
    print(api_matches[:5])

    print(hero_dna)

    print(df.head())
    print("Saved macro data")

    features = build_macro_features(df, "2023-04-03") 
    print(features) 
    
if __name__ == "__main__":
    main()

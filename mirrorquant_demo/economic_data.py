import os
from dotenv import load_dotenv

import requests
import pandas as pd

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



def main(): 
    load_dotenv() # Load environment variables from .env file
    api_key = os.getenv("FRED_API_KEY") # Get the FRED API key from environment variables

    if not api_key: 
        raise RuntimeError("Missing FRED_API_KEY in environment variables. Please set it in your .env file.")
    
    df = fetch_all_macro_series(api_key=api_key)
    save_macro_data(df, "mirrorquant_demo/data/macro_series.csv") # Save the combined DataFrame to a CSV file
    print(df.head()) # Print the first few rows of the DataFrame to verify it was loaded correctly
    print("Saved macro data")


    snapshot = build_macro_snapshot(df, "2023-04-03") 
    print(snapshot) 
    
if __name__ == "__main__":
    main()
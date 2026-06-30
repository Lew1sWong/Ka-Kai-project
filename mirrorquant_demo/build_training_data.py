from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

WINDOW_SIZE = 40
MIN_HISTORY = 60


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build sliding-window training data from a prices CSV.",
    )
    parser.add_argument(
        "--market",
        choices=["us", "cn"],
        default="us",
        help="Market to build training data for. Determines input/output file paths.",
    )
    return parser.parse_args()


def _paths(market: str):
    suffix = "_cn" if market == "cn" else ""
    return (
        DATA_DIR / f"prices{suffix}.csv",
        DATA_DIR / f"training_windows{suffix}.npz",
        DATA_DIR / f"training_windows_meta{suffix}.csv",
    )


def load_prices(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    return df.sort_values(["ticker", "date"]).copy()

# pct_change: Pandas method to compute percentage change between the current and a prior element. It is often used to calculate returns in financial data.
# fillna: Pandas method to fill NA/NaN values using the specified method. In this case, it fills NaN values with 0.0.
def make_sequence_features(window_df: pd.DataFrame) -> np.ndarray:
    window_df = window_df.sort_values("date").copy()

    window_df["daily_return"] = window_df["close"].pct_change().fillna(0.0)
    window_df["volume_change"] = (
        window_df["volume"]
        .pct_change()
        .replace([np.inf, -np.inf], 0.0)
        .fillna(0.0)
    )
    window_df["price_rel"] = (window_df["close"] / window_df["close"].iloc[0]) - 1.0 

    features = window_df[["daily_return", "volume_change", "price_rel"]].to_numpy(dtype=np.float32)
    return features


def build_windows(df: pd.DataFrame, window_size: int = WINDOW_SIZE):
    windows = []
    meta_rows = []

    for ticker in sorted(df["ticker"].unique()):
        stock_df = df[df["ticker"] == ticker].sort_values("date").copy()

        if len(stock_df) < MIN_HISTORY:
            continue

        for start_idx in range(0, len(stock_df) - window_size + 1):
            end_idx = start_idx + window_size
            window_df = stock_df.iloc[start_idx:end_idx].copy()

            X_window = make_sequence_features(window_df)

            if len(X_window) != window_size:
                continue

            windows.append(X_window)
            meta_rows.append(
                {
                    "ticker": ticker,
                    "start_date": window_df["date"].iloc[0],
                    "end_date": window_df["date"].iloc[-1],
                }
            )

    X = np.stack(windows)
    meta_df = pd.DataFrame(meta_rows)
    return X, meta_df


def main():
    args = parse_args()
    prices_path, windows_out, meta_out = _paths(args.market)

    if not prices_path.exists():
        raise SystemExit(
            f"Price file not found: {prices_path}\n"
            f"Run the appropriate fetcher first (e.g. fetch_prices_akshare.py for cn)."
        )

    df = load_prices(prices_path)
    X, meta_df = build_windows(df)

    np.savez_compressed(windows_out, X=X)
    meta_df.to_csv(meta_out, index=False)

    print(f"Built training data for market={args.market}")
    print("X shape:", X.shape)
    print("Saved:", windows_out)
    print("Saved:", meta_out)


if __name__ == "__main__":
    main()
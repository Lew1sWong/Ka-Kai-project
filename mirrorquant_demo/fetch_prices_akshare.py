from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

try:
    import akshare as ak
except ImportError as exc:
    raise SystemExit(
        "Missing akshare. Install it with `pip install akshare` before running this script."
    ) from exc

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_PATH = DATA_DIR / "prices_cn.csv"

DEFAULT_TICKERS = ["600519", "300750", "600036", "002594", "601318"]
ADJUST_MAP = {"qfq": "qfq", "hfq": "hfq", "none": ""}

CN_MARKET_WATCH_TICKERS = ["510300", "159915", "510500", "511010", "511380"]


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Fetch daily OHLCV bars for A-share stocks (and ETFs) using akshare "
            "and save them to a CSV file."
        ),
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help="6-digit A-share ticker codes, e.g. 600519 300750 510300.",
    )
    parser.add_argument(
        "--start",
        default="2023-01-01",
        help="Start date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--end",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="End date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--adjust",
        choices=sorted(ADJUST_MAP.keys()),
        default="qfq",
        help="Price adjustment: qfq=forward (前复权), hfq=backward (后复权), none=unadjusted.",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_PATH),
        help="Output CSV file path.",
    )
    parser.add_argument(
        "--market-watch",
        action="store_true",
        help=(
            "Fetch the standard CN market watch ETFs instead of --tickers. "
            "Output defaults to data/market_watch_prices_cn.csv unless --output is set."
        ),
    )
    return parser.parse_args()


def fetch_daily_bars(symbol: str, start: str, end: str, adjust: str) -> pd.DataFrame:
    start_fmt = start.replace("-", "")
    end_fmt = end.replace("-", "")

    frame = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_fmt,
        end_date=end_fmt,
        adjust=adjust,
    )

    if frame.empty:
        raise RuntimeError(f"No data returned for {symbol} between {start} and {end}.")

    normalized = pd.DataFrame(
        {
            "ticker": symbol,
            "date": pd.to_datetime(frame["日期"]).dt.strftime("%Y-%m-%d"),
            "open": frame["开盘"].astype(float),
            "high": frame["最高"].astype(float),
            "low": frame["最低"].astype(float),
            "close": frame["收盘"].astype(float),
            "volume": frame["成交量"].astype(int),
        }
    )
    return normalized.sort_values("date").reset_index(drop=True)


def main():
    args = parse_args()
    adjust = ADJUST_MAP[args.adjust]

    if args.market_watch:
        tickers = CN_MARKET_WATCH_TICKERS
        output_path = Path(args.output) if args.output != str(OUTPUT_PATH) else DATA_DIR / "market_watch_prices_cn.csv"
    else:
        tickers = args.tickers
        output_path = Path(args.output)

    frames = []
    for index, ticker in enumerate(tickers):
        print(f"[{index + 1}/{len(tickers)}] Fetching {ticker} from akshare...")
        try:
            frames.append(
                fetch_daily_bars(
                    symbol=ticker,
                    start=args.start,
                    end=args.end,
                    adjust=adjust,
                )
            )
        except RuntimeError as exc:
            print(f"  Warning: {exc} — skipping.")

    if not frames:
        raise SystemExit("No data fetched. Check your tickers and date range.")

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values(["ticker", "date"]).reset_index(drop=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output_path, index=False)

    print(f"Saved {len(combined)} rows to {output_path}")
    if not args.market_watch:
        print("Next steps:")
        print("  1. python build_training_data.py --market cn")
        print("  2. python train_vqvae.py --market cn")
        print("  3. python encode_windows.py --market cn")
        print("  4. python fetch_prices_akshare.py --market-watch  (for CN market watch)")
        print("  5. uvicorn mirrorquant_demo.app:app --reload")


if __name__ == "__main__":
    main()

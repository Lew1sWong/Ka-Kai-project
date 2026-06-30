"""Lightweight A-share daily OHLCV fetcher (Tencent / Sina free endpoints).

A dependency-free alternative / fallback to ``fetch_prices_akshare.py``, inspired
by the public data sources that mpquant/Ashare uses. This is a clean-room
implementation that talks directly to the public Tencent and Sina finance
endpoints (no akshare, no extra packages — only ``requests`` + ``pandas``).

  - Tencent (``web.ifzq.gtimg.cn/appstock/app/fqkline/get``) is tried first and
    supports forward/backward adjusted prices (qfq/hfq), matching the training
    pipeline's expectation of adjusted bars.
  - Sina (``CN_MarketData.getKLineData``) is the failover. NOTE: Sina returns
    *unadjusted* bars, so when an adjusted series was requested a warning is
    printed (use the Tencent source for clean adjusted data).

Output schema is identical to ``fetch_prices_akshare.py``:
``ticker,date,open,high,low,close,volume`` -> ``data/prices_cn.csv``.

`fetch_daily_bars(symbol, start, end, adjust)` has the same signature as the
akshare fetcher, so it can be used as an automatic fallback there.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_PATH = DATA_DIR / "prices_cn.csv"

DEFAULT_TICKERS = ["600519", "300750", "600036", "002594", "601318"]
CN_MARKET_WATCH_TICKERS = ["510300", "159915", "510500", "511010", "511380"]
ADJUST_CHOICES = ("qfq", "hfq", "none")

_HEADERS = {"User-Agent": "Mozilla/5.0 (MirrorQuant Ashare fetcher)"}
_TIMEOUT = 15
_TENCENT_URL = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
_SINA_URL = (
    "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "CN_MarketData.getKLineData"
)


def _prefixed(code: str) -> str:
    """6-digit A-share code -> exchange-prefixed symbol (sh/sz/bj)."""
    code = str(code).strip().lower()
    if code[:2] in ("sh", "sz", "bj"):
        return code
    head = code[0]
    if head in ("5", "6", "9") or code[:3] in ("110", "113", "118", "132", "204"):
        return "sh" + code
    if head in ("4", "8"):
        return "bj" + code
    return "sz" + code  # 0/1/2/3 (incl. 深 ETF 159xxx, 创业板 300xxx)


def _normalize_adjust(adjust: str | None) -> str:
    adjust = (adjust or "").strip().lower()
    return "" if adjust in ("", "none") else adjust


def _count_for_range(start: str, end: str) -> int:
    s = datetime.strptime(start, "%Y-%m-%d").date()
    e = datetime.strptime(end, "%Y-%m-%d").date()
    days = max(0, (e - s).days)
    # ~0.69 trading days per calendar day; add a buffer, clamp to a sane ceiling.
    return max(30, min(int(days * 0.75) + 40, 8000))


def _fetch_tencent(code: str, count: int, end: str, adjust: str) -> list[dict]:
    sym = _prefixed(code)
    param = f"{sym},day,,{end},{count},{adjust}"
    resp = requests.get(_TENCENT_URL, params={"param": param}, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    node = (resp.json() or {}).get("data", {}).get(sym, {})
    key = {"qfq": "qfqday", "hfq": "hfqday"}.get(adjust, "day")
    rows = node.get(key) or node.get("day") or []
    out: list[dict] = []
    for row in rows:
        # row = [date, open, close, high, low, volume, ...]
        out.append(
            {
                "date": str(row[0])[:10],
                "open": float(row[1]),
                "close": float(row[2]),
                "high": float(row[3]),
                "low": float(row[4]),
                "volume": int(float(row[5])),
            }
        )
    return out


def _fetch_sina(code: str, count: int) -> list[dict]:
    sym = _prefixed(code)
    resp = requests.get(
        _SINA_URL,
        params={"symbol": sym, "scale": 240, "ma": "no", "datalen": count},
        headers=_HEADERS,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    out: list[dict] = []
    for item in resp.json() or []:
        out.append(
            {
                "date": str(item["day"])[:10],
                "open": float(item["open"]),
                "high": float(item["high"]),
                "low": float(item["low"]),
                "close": float(item["close"]),
                "volume": int(float(item["volume"])),
            }
        )
    return out


def fetch_daily_bars(symbol: str, start: str, end: str, adjust: str = "qfq") -> pd.DataFrame:
    """Daily OHLCV for one A-share code, normalized to the prices_cn.csv schema.

    Tencent (adjusted-capable) first, Sina (unadjusted) as failover. Raises
    ``RuntimeError`` if no usable data is returned for the window.
    """
    adjust = _normalize_adjust(adjust)
    count = _count_for_range(start, end)

    rows: list[dict] = []
    errors: list[str] = []
    try:
        rows = _fetch_tencent(symbol, count, end, adjust)
    except Exception as exc:  # network / parse / source change
        errors.append(f"tencent: {exc}")

    if not rows:
        try:
            rows = _fetch_sina(symbol, count)
            if rows and adjust:
                print(
                    f"  Note: {symbol} fell back to Sina, which is UNADJUSTED "
                    f"(requested {adjust}); prefer Tencent for adjusted data."
                )
        except Exception as exc:
            errors.append(f"sina: {exc}")

    if not rows:
        raise RuntimeError(f"No data for {symbol} ({'; '.join(errors) or 'empty response'}).")

    frame = pd.DataFrame(rows)
    frame = frame[(frame["date"] >= start) & (frame["date"] <= end)]
    if frame.empty:
        raise RuntimeError(f"No data for {symbol} between {start} and {end}.")

    frame.insert(0, "ticker", str(symbol))
    frame = frame[["ticker", "date", "open", "high", "low", "close", "volume"]]
    return frame.sort_values("date").reset_index(drop=True)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Fetch daily OHLCV bars for A-share stocks/ETFs from the free Tencent/Sina "
            "endpoints (dependency-free Ashare-style fallback) and save them to CSV."
        ),
    )
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS,
                        help="6-digit A-share codes, e.g. 600519 300750 510300.")
    parser.add_argument("--start", default="2023-01-01", help="Start date YYYY-MM-DD.")
    parser.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d"),
                        help="End date YYYY-MM-DD.")
    parser.add_argument("--adjust", choices=ADJUST_CHOICES, default="qfq",
                        help="qfq=forward (前复权), hfq=backward (后复权), none=unadjusted.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output CSV path.")
    parser.add_argument("--market-watch", action="store_true",
                        help="Fetch the CN market-watch ETFs (-> data/market_watch_prices_cn.csv).")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.market_watch:
        tickers = CN_MARKET_WATCH_TICKERS
        output_path = (
            Path(args.output)
            if args.output != str(OUTPUT_PATH)
            else DATA_DIR / "market_watch_prices_cn.csv"
        )
    else:
        tickers = args.tickers
        output_path = Path(args.output)

    frames = []
    for index, ticker in enumerate(tickers):
        print(f"[{index + 1}/{len(tickers)}] Fetching {ticker} from Tencent/Sina...")
        try:
            frames.append(fetch_daily_bars(ticker, args.start, args.end, args.adjust))
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
        print("  4. python fetch_prices_ashare.py --market-watch  (for CN market watch)")


if __name__ == "__main__":
    main()

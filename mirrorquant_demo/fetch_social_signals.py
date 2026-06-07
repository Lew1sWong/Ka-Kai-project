from __future__ import annotations

import argparse
import json
import math
import os
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
import torch
from dotenv import load_dotenv
from transformers import AutoModelForSequenceClassification, AutoTokenizer

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_OUTPUT_PATH = DATA_DIR / "social_news.json"
SIGNALS_OUTPUT_PATH = DATA_DIR / "social_signals.csv"

DEFAULT_TICKERS = ["MSFT", "NVDA", "LLY", "AAPL", "AMD", "META", "AVGO", "GOOGL"]
DEFAULT_NAMES = {
    "AAPL": "Apple",
    "AMD": "AMD",
    "AVGO": "Broadcom",
    "GOOGL": "Alphabet",
    "LLY": "Eli Lilly",
    "META": "Meta",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
}

FINNHUB_COMPANY_NEWS_URL = "https://finnhub.io/api/v1/company-news"
NEWSAPI_EVERYTHING_URL = "https://newsapi.org/v2/everything"
FINBERT_MODEL_NAME = "ProsusAI/finbert"

AI_KEYWORDS = (
    "ai",
    "artificial intelligence",
    "gpu",
    "chip",
    "server",
    "cloud",
    "copilot",
    "model",
)
INNOVATION_KEYWORDS = (
    "innovation",
    "drug",
    "trial",
    "product",
    "platform",
    "launch",
    "approval",
    "pipeline",
    "patent",
)
ANALYST_KEYWORDS = (
    "analyst",
    "price target",
    "upgrade",
    "downgrade",
    "outperform",
    "overweight",
    "buy rating",
    "estimate",
)
CONTROVERSY_KEYWORDS = (
    "lawsuit",
    "probe",
    "investigation",
    "fraud",
    "regulator",
    "ban",
    "risk",
    "controversy",
    "antitrust",
)
HIGH_CREDIBILITY_SOURCES = {
    "reuters",
    "bloomberg",
    "cnbc",
    "marketwatch",
    "wsj",
    "wall street journal",
    "financial times",
    "associated press",
    "the associated press",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Fetch company news from Finnhub and NewsAPI, score it with FinBERT, "
            "and write daily Social DNA signals."
        ),
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help="Ticker symbols to fetch.",
    )
    parser.add_argument(
        "--start",
        default="2023-01-01",
        help="Start date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--end",
        default=datetime.utcnow().strftime("%Y-%m-%d"),
        help="End date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--raw-output",
        default=str(RAW_OUTPUT_PATH),
        help="Where to write normalized article JSON.",
    )
    parser.add_argument(
        "--signals-output",
        default=str(SIGNALS_OUTPUT_PATH),
        help="Where to write aggregated daily social signals CSV.",
    )
    parser.add_argument(
        "--model",
        default=FINBERT_MODEL_NAME,
        help="Hugging Face model name for sentiment classification.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="FinBERT inference batch size.",
    )
    parser.add_argument(
        "--newsapi-page-size",
        type=int,
        default=50,
        help="NewsAPI page size. Official max is 100.",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=1.0,
        help="Pause between network calls to avoid hammering rate limits.",
    )
    return parser.parse_args()


def get_credentials() -> tuple[str, str]:
    load_dotenv()
    finnhub_api_key = os.getenv("FINNHUB_API_KEY")
    newsapi_api_key = os.getenv("NEWSAPI_API_KEY")
    if not finnhub_api_key or not newsapi_api_key:
        raise RuntimeError(
            "Missing FINNHUB_API_KEY or NEWSAPI_API_KEY. Add both to your environment "
            "or a .env file."
        )
    return finnhub_api_key, newsapi_api_key


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    path = parsed.path.rstrip("/")
    return f"{parsed.netloc.lower()}{path}"


def _slug_source(source: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", source.lower()).strip()


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _source_quality(source: str, url: str) -> float:
    source_slug = _slug_source(source)
    domain = urlparse(url).netloc.lower()
    if source_slug in HIGH_CREDIBILITY_SOURCES or any(
        trusted in domain for trusted in ("reuters", "bloomberg", "cnbc", "wsj", "ft.com", "apnews")
    ):
        return 0.9
    if source_slug:
        return 0.65
    return 0.45


def _build_newsapi_query(ticker: str, company_name: str) -> str:
    base_terms = [
        f"\"{company_name}\"",
        f"\"{ticker}\"",
    ]
    market_context = "(stock OR shares OR earnings OR analyst OR revenue OR guidance)"
    return f"({' OR '.join(base_terms)}) AND {market_context}"


def fetch_finnhub_company_news(
    symbol: str,
    start: str,
    end: str,
    api_key: str,
) -> list[dict[str, object]]:
    response = requests.get(
        FINNHUB_COMPANY_NEWS_URL,
        params={
            "symbol": symbol,
            "from": start,
            "to": end,
            "token": api_key,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError(f"Unexpected Finnhub payload for {symbol}: {payload}")
    return payload


def fetch_newsapi_articles(
    symbol: str,
    company_name: str,
    start: str,
    end: str,
    api_key: str,
    page_size: int,
) -> list[dict[str, object]]:
    response = requests.get(
        NEWSAPI_EVERYTHING_URL,
        params={
            "q": _build_newsapi_query(symbol, company_name),
            "from": start,
            "to": end,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(page_size, 100),
            "page": 1,
        },
        headers={"X-Api-Key": api_key},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "ok":
        raise RuntimeError(f"NewsAPI rejected {symbol}: {payload}")
    return payload.get("articles", [])


def normalize_articles(
    ticker: str,
    company_name: str,
    finnhub_items: list[dict[str, object]],
    newsapi_items: list[dict[str, object]],
) -> list[dict[str, object]]:
    deduped: dict[str, dict[str, object]] = {}

    for item in finnhub_items:
        url = _safe_text(item.get("url"))
        title = _safe_text(item.get("headline"))
        summary = _safe_text(item.get("summary"))
        if not url or not title:
            continue
        published_at = datetime.utcfromtimestamp(int(item.get("datetime", 0))).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        key = _normalize_url(url) or f"{ticker}-{title.lower()}"
        deduped[key] = {
            "ticker": ticker,
            "company_name": company_name,
            "provider": "finnhub",
            "source": _safe_text(item.get("source")),
            "title": title,
            "summary": summary,
            "content": "",
            "url": url,
            "published_at": published_at,
        }

    for item in newsapi_items:
        url = _safe_text(item.get("url"))
        title = _safe_text(item.get("title"))
        description = _safe_text(item.get("description"))
        content = _safe_text(item.get("content"))
        if not url or not title:
            continue
        key = _normalize_url(url) or f"{ticker}-{title.lower()}"
        if key in deduped:
            continue
        source_obj = item.get("source") or {}
        deduped[key] = {
            "ticker": ticker,
            "company_name": company_name,
            "provider": "newsapi",
            "source": _safe_text(source_obj.get("name")),
            "title": title,
            "summary": description,
            "content": content,
            "url": url,
            "published_at": _safe_text(item.get("publishedAt")),
        }

    articles = list(deduped.values())
    articles.sort(key=lambda row: (row["published_at"], row["source"], row["title"]))
    return articles


class FinBertScorer:
    def __init__(self, model_name: str):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.eval()

    def score_texts(self, texts: list[str], batch_size: int) -> list[dict[str, float | str]]:
        results: list[dict[str, float | str]] = []
        label_map = {
            int(idx): str(label).lower()
            for idx, label in self.model.config.id2label.items()
        }

        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            encoded = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="pt",
            )
            with torch.no_grad():
                logits = self.model(**encoded).logits
                probabilities = torch.nn.functional.softmax(logits, dim=-1)

            for row in probabilities:
                probs = row.tolist()
                indexed = {
                    label_map[idx]: float(value)
                    for idx, value in enumerate(probs)
                }
                positive = indexed.get("positive", 0.0)
                negative = indexed.get("negative", 0.0)
                neutral = indexed.get("neutral", 0.0)
                label = max(indexed, key=indexed.get)
                results.append(
                    {
                        "label": label,
                        "positive": positive,
                        "negative": negative,
                        "neutral": neutral,
                        "sentiment_score": positive - negative,
                    }
                )

        return results


def _article_text(article: dict[str, object]) -> str:
    parts = [
        _safe_text(article.get("title")),
        _safe_text(article.get("summary")),
        _safe_text(article.get("content")),
    ]
    return " ".join(part for part in parts if part).strip()


def score_articles(
    articles: list[dict[str, object]],
    scorer: FinBertScorer,
    batch_size: int,
) -> list[dict[str, object]]:
    if not articles:
        return []

    texts = [_article_text(article) for article in articles]
    scored = scorer.score_texts(texts, batch_size=batch_size)
    output = []

    for article, sentiment in zip(articles, scored):
        text = _article_text(article)
        output.append(
            {
                **article,
                **sentiment,
                "date": _safe_text(article["published_at"])[:10],
                "theme_ai": 1.0 if _contains_any(text, AI_KEYWORDS) else 0.0,
                "theme_innovation": 1.0 if _contains_any(text, INNOVATION_KEYWORDS) else 0.0,
                "analyst_attention": 1.0 if _contains_any(text, ANALYST_KEYWORDS) else 0.0,
                "controversy_flag": 1.0 if _contains_any(text, CONTROVERSY_KEYWORDS) else 0.0,
                "credibility_score": _source_quality(
                    _safe_text(article.get("source")),
                    _safe_text(article.get("url")),
                ),
            }
        )

    return output


def aggregate_daily_signals(scored_articles: list[dict[str, object]]) -> pd.DataFrame:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for article in scored_articles:
        grouped[(str(article["ticker"]), str(article["date"]))].append(article)

    rows = []
    for (ticker, date_str), items in sorted(grouped.items()):
        article_count = len(items)
        source_count = len({str(item["source"]).strip().lower() for item in items if item["source"]})
        positive_share = sum(float(item["positive"]) for item in items) / article_count
        negative_share = sum(float(item["negative"]) for item in items) / article_count
        neutral_share = sum(float(item["neutral"]) for item in items) / article_count
        sentiment_score = sum(float(item["sentiment_score"]) for item in items) / article_count
        theme_ai = sum(float(item["theme_ai"]) for item in items) / article_count
        theme_innovation = sum(float(item["theme_innovation"]) for item in items) / article_count
        analyst_attention = sum(float(item["analyst_attention"]) for item in items) / article_count
        credibility_score = sum(float(item["credibility_score"]) for item in items) / article_count
        controversy_hits = sum(float(item["controversy_flag"]) for item in items) / article_count
        controversy_score = min(
            1.0,
            (0.55 * controversy_hits) + (0.45 * max(negative_share, 0.0)),
        )
        mention_intensity = min(1.0, math.log1p(article_count) / math.log(6))

        rows.append(
            {
                "ticker": ticker,
                "date": date_str,
                "article_count": article_count,
                "source_count": source_count,
                "positive_share": round(positive_share, 6),
                "negative_share": round(negative_share, 6),
                "neutral_share": round(neutral_share, 6),
                "sentiment_score": round(sentiment_score, 6),
                "mention_intensity": round(mention_intensity, 6),
                "controversy_score": round(controversy_score, 6),
                "theme_ai": round(theme_ai, 6),
                "theme_innovation": round(theme_innovation, 6),
                "analyst_attention": round(analyst_attention, 6),
                "credibility_score": round(credibility_score, 6),
            }
        )

    return pd.DataFrame(rows)


def main():
    args = parse_args()
    finnhub_api_key, newsapi_api_key = get_credentials()
    scorer = FinBertScorer(args.model)

    all_articles: list[dict[str, object]] = []
    for index, ticker in enumerate(args.tickers):
        symbol = ticker.upper()
        company_name = DEFAULT_NAMES.get(symbol, symbol)
        print(f"[{index + 1}/{len(args.tickers)}] Fetching social news for {symbol}...")
        finnhub_items = fetch_finnhub_company_news(
            symbol=symbol,
            start=args.start,
            end=args.end,
            api_key=finnhub_api_key,
        )
        time.sleep(args.pause_seconds)
        newsapi_items = fetch_newsapi_articles(
            symbol=symbol,
            company_name=company_name,
            start=args.start,
            end=args.end,
            api_key=newsapi_api_key,
            page_size=args.newsapi_page_size,
        )
        time.sleep(args.pause_seconds)
        all_articles.extend(
            normalize_articles(
                ticker=symbol,
                company_name=company_name,
                finnhub_items=finnhub_items,
                newsapi_items=newsapi_items,
            )
        )

    scored_articles = score_articles(all_articles, scorer, batch_size=args.batch_size)

    raw_output = Path(args.raw_output)
    raw_output.write_text(json.dumps(scored_articles, indent=2), encoding="utf-8")

    signals_df = aggregate_daily_signals(scored_articles)
    if signals_df.empty:
        raise RuntimeError("No social articles were collected, so no signals were written.")

    signals_df = signals_df.sort_values(["ticker", "date"]).reset_index(drop=True)
    signals_output = Path(args.signals_output)
    signals_df.to_csv(signals_output, index=False)

    print(f"Saved {len(scored_articles)} scored articles to {raw_output}")
    print(f"Saved {len(signals_df)} daily social signal rows to {signals_output}")
    print("Next steps:")
    print("  1. py -m uvicorn mirrorquant_demo.app:app --reload")
    print("  2. Open the dashboard and switch to Social DNA")


if __name__ == "__main__":
    main()

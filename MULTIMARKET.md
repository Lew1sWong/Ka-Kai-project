# Multi-market (US + A-share / CN) support

This repo was mirrored from `Ch3ngK/Hand-drawn-agent`, then the local
multi-market / A-share work was ported back on top. This note records what was
ported and what still needs wiring to fully surface CN through the new
DB-backed API + Next.js frontend.

## What was ported in

- **`mirrorquant_demo/fetch_prices_akshare.py`** — A-share price fetcher
  (writes `data/prices_cn.csv`, and `data/market_watch_prices_cn.csv` with
  `--market-watch`).
- **Market-aware ML pipeline** — `build_training_data.py`, `train_vqvae.py`,
  `encode_windows.py`, `vqvae_search.py` now take `--market {us,cn}` and read/write
  market-suffixed artifacts (`*_cn.npz`, `vqvae_model_cn.pt`, etc.). `us` is the
  default, so existing US behavior is unchanged.
- **CN data assets** — `data/heroes_cn.json`, `data/industry_chain_cn.json`,
  `data/market_watch_cn.json`.
- **`market` threaded through the search path** (backward-compatible, defaults to
  `"us"`):
  - `schemas.py`: added `Market` literal + `SearchRunCreate.market`.
  - `search_service.py`: `_market_prices_path()`, and `market` on
    `_build_price_dna_run` / `_build_search_payload` / `run_search_for_hero`,
    passed down to `find_vqvae_mirrors`.
  - `backend/app/main.py`: `POST /api/heroes/{hero_id}/search-runs` forwards
    `payload.market`.

## Build the CN artifacts (one time)

Run from the repo root so the `mirrorquant_demo` package imports resolve:

```bash
python -m mirrorquant_demo.fetch_prices_akshare              # -> data/prices_cn.csv
python -m mirrorquant_demo.build_training_data --market cn
python -m mirrorquant_demo.train_vqvae --market cn
python -m mirrorquant_demo.encode_windows --market cn
python -m mirrorquant_demo.fetch_prices_akshare --market-watch   # CN market watch
```

A CN price-DNA search then works via:
`POST /api/heroes/{hero_id}/search-runs` with body `{"mode": "price_dna", "market": "cn"}`.

## Still to do (not ported in this pass)

- **CN heroes in the DB.** Heroes are now DB-backed (per-user); `heroes_cn.json`
  is curated/seed data. To expose CN heroes in the UI, seed them per market or add
  a `market` column to `Hero` and a CN seeder.
- **economic_dna / social_dna for CN.** `economic_data.py` (FRED) and
  `social_data.py` (Finnhub/NewsAPI/FinBERT) are US-oriented. CN macro/social
  sources are not yet wired; CN searches should stick to `price_dna` until then.
- **Frontend market switch.** The Next.js client has no US/CN toggle yet; add one
  that sends `market` on search-run requests and loads the CN curated lists.

## Backup

The previous local flat-folder version (standalone multi-market `app.py`,
original US/CN artifacts) was backed up before the mirror to a sibling
`mirrorquant_demo_backup_<timestamp>/` folder on the Desktop.

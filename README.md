# MirrorQuant

MirrorQuant is an AI-first fintech platform that helps users discover stocks with the same hidden behavioral "DNA" as a reference stock during its strongest breakout period.

Instead of screening by sector, valuation, or static ratios, MirrorQuant learns discrete latent market regimes from historical market behavior using a Vector Quantized Variational Autoencoder (VQ-VAE). A user selects a hero stock and a historical window, such as `MSFT` in early 2023, and MirrorQuant extracts the latent profile behind that move. The platform then scans the current market for stocks whose learned regime vectors match the hero profile, even across unrelated sectors.

The result is a new class of "Mirror" stocks that conventional screeners are likely to miss.

## Current Demo Status

The repo now contains a working single-page demo in [`mirrorquant_demo/`](/abs/path/c:/Users/cheng/Desktop/Hand-drawn-agent/mirrorquant_demo) with:

- a FastAPI backend
- a dark quant-terminal-style dashboard
- a real `Price DNA` path powered by a trained VQ-VAE
- curated fallback demo data for `Economic DNA` and `Social DNA`
- user-selectable hero windows via start and end date inputs

The app mixes real and mock layers on purpose:

- `Price DNA` uses the trained VQ-VAE pipeline
- `Economic DNA` and `Social DNA` still use curated demo results from JSON
- `Market Watch` and `Industry Chain` remain demo data

## Demo Folder Layout

```text
mirrorquant_demo/
  app.py
  build_training_data.py
  train_vqvae.py
  encode_windows.py
  vqvae_search.py
  fetch_prices_alpha_vantage.py
  data/
    heroes.json
    mirror_matches.json
    market_watch.json
    industry_chain.json
    prices.csv
    training_windows.npz
    training_windows_meta.csv
    vqvae_model.pt
    window_embeddings.npz
    window_embedding_meta.csv
  static/
    index.html
    styles.css
    app.js
```

## Install

1. Create or activate a Python environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Run The App

Start the FastAPI app:

```bash
python -m uvicorn mirrorquant_demo.app:app --reload
```

Then open:

```text
http://127.0.0.1:8000
```

## Main User Flow

1. Select a hero stock.
2. Choose a DNA mode.
3. Optionally edit the `Start date` and `End date`.
4. Click `Find Mirrors`.
5. Review:
   - selected hero window
   - encoded model window
   - top mirror matches
   - market watch context
   - industry-chain explanation

Important note:

- the **Selected window** is the date range the user asked for
- the **Encoded window** is the exact model-sized slice used by the VQ-VAE

Because the current VQ-VAE was trained on fixed 40-day windows, the app encodes a 40-trading-day slice from the chosen hero range.

## API Endpoints

- `GET /api/heroes`
- `GET /api/mirrors?ticker=MSFT&mode=price_dna`
- `GET /api/mirrors?ticker=MSFT&mode=price_dna&start_date=2023-01-03&end_date=2023-04-03`
- `GET /api/market-watch`
- `GET /api/industry-chain/MSFT`
- `GET /health`

## Fetch Real Market Data With Alpha Vantage

The repo includes a fetch script that replaces the demo `prices.csv` with real daily OHLCV data from Alpha Vantage:

[`mirrorquant_demo/fetch_prices_alpha_vantage.py`](/abs/path/c:/Users/cheng/Desktop/Hand-drawn-agent/mirrorquant_demo/fetch_prices_alpha_vantage.py:1)

### Step 1: Get an API key

Create a free Alpha Vantage API key here:

https://www.alphavantage.co/documentation/

### Step 2: Set the API key

Add it to your environment or a local `.env` file:

```env
ALPHAVANTAGE_API_KEY=your_key_here
```

### Step 3: Fetch prices

Fetch the default demo tickers:

```bash
python mirrorquant_demo/fetch_prices_alpha_vantage.py
```

Or fetch specific tickers:

```bash
python mirrorquant_demo/fetch_prices_alpha_vantage.py --tickers MSFT NVDA LLY AAPL
```

### Important Alpha Vantage note

The current script uses `TIME_SERIES_DAILY` with `outputsize=compact`, which returns only the latest 100 daily points on the free tier. If you want deeper history, you will need either:

- a premium Alpha Vantage plan, or
- a different market-data provider

## Retrain The AI

If you change `prices.csv`, you should rebuild the VQ-VAE pipeline in this order.

### 1. Build training windows

This converts daily OHLCV history into fixed-size model windows:

```bash
python mirrorquant_demo/build_training_data.py
```

Outputs:

- `mirrorquant_demo/data/training_windows.npz`
- `mirrorquant_demo/data/training_windows_meta.csv`

### 2. Train the VQ-VAE

This trains the current `Price DNA` model:

```bash
python mirrorquant_demo/train_vqvae.py
```

Output:

- `mirrorquant_demo/data/vqvae_model.pt`

### 3. Encode all windows

This builds the searchable embedding library used by the app:

```bash
python -m mirrorquant_demo.encode_windows
```

Outputs:

- `mirrorquant_demo/data/window_embeddings.npz`
- `mirrorquant_demo/data/window_embedding_meta.csv`

### 4. Restart the app

After retraining and re-encoding, start or restart:

```bash
python -m uvicorn mirrorquant_demo.app:app --reload
```

## When You Need To Retrain

You do **not** retrain the AI every time a user clicks `Find Mirrors`.

You typically retrain only when:

- you replace demo price data with real price data
- you add more stocks
- you change the feature engineering
- you change the VQ-VAE architecture

You should re-encode windows when:

- you retrain the model
- you update `prices.csv`

## What Is Real vs Mock Right Now

### Real

- FastAPI backend
- custom hero window input
- VQ-VAE training pipeline
- VQ-VAE embedding search for `Price DNA`

### Mock / curated

- `Economic DNA`
- `Social DNA`
- market watch values
- industry chain relationships

## Best Demo Flow

Use this sequence during a presentation:

1. Start with `MSFT` in `Price DNA`.
2. Show the selected window and the encoded model window.
3. Explain that the VQ-VAE is matching latent behavior, not sector labels.
4. Switch to `Economic DNA` and `Social DNA` as explainability layers.
5. Use Market Watch to frame the current regime.
6. Use Industry Chain to connect quant signals back to real-world logic.

## What To Say During The Demo

You can describe it like this:

> MirrorQuant is not screening for stocks in the same sector. It is retrieving stocks expressing the same latent breakout behavior under similar market conditions.

If someone asks whether the AI is real:

> Price DNA is powered by a trained VQ-VAE over rolling price-volume windows. Economic DNA and Social DNA are currently curated demo layers while the full multi-modal stack is still being built.

## Technical Summary

### Frontend

- single-page dashboard
- custom hero window inputs
- sci-fi quant-terminal visual system

### Backend

- `FastAPI`
- JSON-backed demo metadata
- VQ-VAE search orchestration for `Price DNA`

### ML Pipeline

- rolling 40-day windows
- sequence features:
  - `daily_return`
  - `volume_change`
  - `price_rel`
- VQ-VAE training with PyTorch
- offline embedding generation

## Future Extensions

- real macroeconomic feeds for `Economic DNA`
- sentiment/news embeddings for `Social DNA`
- longer-history or variable-length sequence models
- richer vector search and ranking logic
- realtime refresh jobs
- portfolio-level analog search

## License

Add your preferred license here.

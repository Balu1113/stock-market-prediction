# Stock Prediction & Trading

A full-stack web app to analyze NSE/BSE stocks, predict next-day returns with
ML, screen and backtest strategies, track alerts and a portfolio, and explore
market breadth — built with Django + React.

## Features

- **Analysis** — CSV upload, Yahoo Finance (NSE/BSE, no API key), or Zerodha
  Kite data; Ridge / Ensemble / Colab-trained LSTM models with leakage-safe
  training, walk-forward backtests, feature importance, and an 80% uncertainty
  band on future forecasts.
- **Technical indicators** — MA20/50, RSI, MACD, Bollinger Bands, Supertrend,
  Stochastic, ADX, VWAP, OBV (all selectable as model features).
- **Composite stock score** — explainable 0–100 score (momentum, trend,
  volatility, volume, model) with per-component breakdown.
- **Candlestick patterns** — doji, engulfing, hammer, stars, marubozu.
- **Top Picks** — batch-ranks the Nifty 50 by predicted return + score.
- **Screener** — Chartink-style rule builder (AND/OR conditions, cross
  operators), saved scans, and per-symbol historical hit-rate backtests.
- **Strategy backtester** — golden/death cross, RSI reversion, Supertrend,
  MACD crossover presets with buy/sell markers, equity curve, and trade log.
- **Alerts** — price/RSI/crossover/volume-spike alerts evaluated against live
  data, with a trigger event feed.
- **Portfolio** — holdings CRUD, live P&L, allocation pie, Nifty 50 benchmark.
- **Market dashboard** — Nifty 50 breadth, gainers/losers, sector performance.
- **News sentiment** — Yahoo Finance headlines scored with VADER.

## Setup

### Backend

```bash
pip install -r requirements.txt
cd backend
python manage.py migrate
python manage.py runserver 8001
```

### Frontend

```bash
cd frontend
npm install
# optionally: set REACT_APP_API_BASE=http://localhost:8001/api
npm run dev
```

Tests: `cd backend && python manage.py test api`

## Zerodha Kite (optional)

Set `KITE_API_KEY` and `KITE_API_SECRET` in `.env` (see `.env.example`),
restart Django, then use the "Zerodha Kite" tab to connect. Read-only — the
app never places orders.

## LSTM (optional)

The LSTM is trained free on Google Colab (`colab/train_lstm_nse.py`). Copy
`nse_lstm.keras` and `nse_lstm_config.json` into `models/`, install
tensorflow, and restart Django.

## CSV format

Minimum columns: `Date`, `Close`. Optional for richer models: `Open`,
`High`, `Low`, `Volume`.

## Configuration

Copy `.env.example` to `.env` for Kite keys and Django production settings
(`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`,
`CORS_ALLOWED_ORIGINS`).

## Disclaimer

Research/educational tool. Predictions are not investment advice.

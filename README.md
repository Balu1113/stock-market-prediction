# Stock Market Prediction & Trading Simulator

This project provides a web-based interface to analyze stock market data, predict future prices using machine learning models (Linear Regression, Random Forest), and simulate trading strategies based on technical indicators.

## Features
- **Data Processing**: Load CSV files and calculate technical indicators (Moving Average, RSI, MACD).
- **Machine Learning**: Predict future stock prices using Scikit-Learn models.
- **Trading Simulation**: Backtest trading strategies using Golden/Death Cross signals.
- **Visualization**: Interactive charts using Plotly.

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the Django backend from the `backend` directory (use another port if 8000 is occupied):
   ```bash
   cd backend
   python manage.py runserver 8001
   ```
3. In a second terminal, start the React frontend:
   ```bash
   cd frontend
   npm install
   # PowerShell: $env:REACT_APP_API_BASE = "http://localhost:8001/api"
   npm run dev
   ```
4. Open the URL printed by the frontend, usually `http://localhost:3000`.

## Zerodha Kite Connect
To use historical Kite candles, create a Kite Connect app and set its registered redirect URL to:
`http://localhost:8000/api/kite/callback`

In the same PowerShell terminal used to start Django, set the credentials and run the server:
```powershell
cd backend
python manage.py runserver 8001
```
Before starting Django, put `KITE_API_KEY` and `KITE_API_SECRET` in the repository-root `.env` file. Keep the file private and out of source control. In the frontend, choose **Zerodha Kite**, connect your account, search for an NSE/BSE equity, select a date range and candle interval, then analyze. This integration fetches historical data only and does not place orders.

## Alpha Vantage
Get an API key from [Alpha Vantage](https://www.alphavantage.co/support/#api-key), add it to the repository-root `.env` as `ALPHA_VANTAGE_API_KEY`, and restart Django. Choose **Alpha Vantage**, search by company or ticker, and select a matching result before analyzing. Alpha Vantage returns search matches rather than a complete global stock catalog. This provider uses daily historical candles; its available history and request limits depend on your plan. The key stays on the backend.

## Data Format
The uploaded CSV must contain at least 'Date' and 'Close' columns.
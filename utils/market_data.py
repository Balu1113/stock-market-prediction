"""Cached Yahoo Finance daily-history helpers shared by all views."""

import pandas as pd
import yfinance as yf

from utils.cache import history_cache, quote_cache


COLUMNS = ['Open', 'High', 'Low', 'Close', 'Volume']


def normalize_symbol(symbol: str, exchange: str = 'NSE') -> str:
    symbol = symbol.strip().upper()
    if symbol.endswith('.NSE'):
        symbol = f'{symbol[:-4]}.NS'
    elif symbol.endswith('.BSE'):
        symbol = f'{symbol[:-4]}.BO'
    if symbol.endswith(('.NS', '.BO')):
        return symbol
    if symbol.startswith('^'):
        return symbol
    suffix = '.BO' if exchange == 'BSE' else '.NS'
    return f'{symbol}{suffix}'


def fetch_daily_history(symbol: str, period: str = '1y') -> pd.DataFrame | None:
    """Fetch OHLCV history; cached per (symbol, period) for 15 minutes."""
    key = f'hist:{symbol}:{period}'
    cached = history_cache.get(key)
    if cached is not None:
        return cached.copy() if isinstance(cached, pd.DataFrame) else cached

    try:
        data = yf.Ticker(symbol).history(period=period, auto_adjust=True)
    except Exception:
        return None
    if data is None or data.empty:
        return None
    if data.index.tz is not None:
        data.index = data.index.tz_localize(None)
    data.index = pd.to_datetime(data.index)
    data.index.name = 'Date'
    data = data[[c for c in COLUMNS if c in data.columns]].apply(
        pd.to_numeric, errors='coerce'
    )
    data.sort_index(inplace=True)
    history_cache.set(key, data)
    return data.copy()


def fetch_last_quote(symbol: str) -> dict | None:
    """Last close and previous close from the cached 5d history."""
    key = f'quote:{symbol}'
    cached = quote_cache.get(key)
    if cached is not None:
        return cached

    data = fetch_daily_history(symbol, period='5d')
    if data is None or len(data) < 1 or 'Close' not in data.columns:
        return None
    price = float(data['Close'].iloc[-1])
    previous = float(data['Close'].iloc[-2]) if len(data) >= 2 else None
    change = price - previous if previous is not None else None
    quote = {
        'symbol': symbol,
        'price': price,
        'previous_close': previous,
        'change': change,
        'change_percent': (change / previous * 100) if change is not None and previous else None,
        'as_of': str(data.index[-1].date()),
    }
    quote_cache.set(key, quote)
    return quote

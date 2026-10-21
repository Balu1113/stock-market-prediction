"""Candlestick pattern detection on OHLCV bars."""

import numpy as np
import pandas as pd


def _body(df):
    return (df['Close'] - df['Open']).abs()


def _range(df):
    return (df['High'] - df['Low']).replace(0, np.nan)


def detect_patterns(data: pd.DataFrame, lookback: int = 20) -> list:
    """Return recent candlestick pattern hits (newest first).

    Each item: {pattern, direction ('bullish'/'bearish'), date, index}.
    Requires Open/High/Low/Close columns.
    """
    required = {'Open', 'High', 'Low', 'Close'}
    if not required.issubset(data.columns) or len(data) < 5:
        return []

    df = data.dropna(subset=list(required)).copy()
    body = _body(df)
    rng = _range(df)
    upper_wick = df['High'] - df[['Open', 'Close']].max(axis=1)
    lower_wick = df[['Open', 'Close']].min(axis=1) - df['Low']
    prev_body = body.shift(1)
    prev_close = df['Close'].shift(1)
    prev_open = df['Open'].shift(1)

    small_body = body < 0.35 * rng
    long_body = body > 0.65 * rng
    bullish_close = df['Close'] > df['Open']
    bearish_close = df['Close'] < df['Open']
    prev_bullish = bullish_close.shift(1).eq(True)
    prev_bearish = bearish_close.shift(1).eq(True)

    conditions = {
        'Doji': (small_body, np.where(bullish_close, 'bearish', 'bullish')),
        'Hammer': ((lower_wick > 2 * body) & (upper_wick < 0.5 * body) & (body > 0), 'bullish'),
        'Shooting Star': ((upper_wick > 2 * body) & (lower_wick < 0.5 * body) & (body > 0), 'bearish'),
        'Bullish Engulfing': (
            prev_bearish
            & bullish_close
            & (df['Open'] <= prev_close)
            & (df['Close'] >= prev_open)
            & (body > prev_body),
            'bullish',
        ),
        'Bearish Engulfing': (
            prev_bullish
            & bearish_close
            & (df['Open'] >= prev_close)
            & (df['Close'] <= prev_open)
            & (body > prev_body),
            'bearish',
        ),
        'Marubozu Bullish': (long_body & bullish_close & (upper_wick < 0.05 * rng) & (lower_wick < 0.05 * rng), 'bullish'),
        'Marubozu Bearish': (long_body & bearish_close & (upper_wick < 0.05 * rng) & (lower_wick < 0.05 * rng), 'bearish'),
        'Morning Star': (
            (prev_body > 0.6 * rng.shift(1))
            & (body.shift(1) > 0.6 * rng.shift(1))
            & bearish_close.shift(2)
            & small_body.shift(1)
            & bullish_close
            & (df['Close'] > (prev_open + prev_close) / 2.0),
            'bullish',
        ),
        'Evening Star': (
            bullish_close.shift(2)
            & (body.shift(2) > 0.6 * rng.shift(2))
            & small_body.shift(1)
            & bearish_close
            & (df['Close'] < (prev_open + prev_close) / 2.0),
            'bearish',
        ),
    }

    hits = []
    for name, (mask, direction) in conditions.items():
        positions = np.flatnonzero(mask.fillna(False).to_numpy(dtype=bool))
        for pos in positions[-3:]:
            ts = df.index[pos]
            hits.append({
                'pattern': name,
                'direction': direction if isinstance(direction, str) else str(direction[pos]),
                'date': str(pd.Timestamp(ts).date()),
            })

    hits.sort(key=lambda item: item['date'], reverse=True)
    return hits[:lookback]

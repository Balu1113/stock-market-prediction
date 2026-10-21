"""Explainable composite stock score (0-100), Trendlyne-DVM / Kavout-Kai style.

Components:
- momentum: trailing returns + RSI
- trend: distance above MAs, ADX/Supertrend direction when available
- volatility: lower normalized ATR is better
- model: predicted next-day return direction/magnitude (optional)
- volume: OBV/volume trend when available
"""

import numpy as np
import pandas as pd


def _clip01(value):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return 50.0
    return float(min(100.0, max(0.0, value)))


def _momentum_score(data: pd.DataFrame) -> tuple:
    close = data['Close'].astype(float)
    last = float(close.iloc[-1])
    scores = []
    for window, weight in ((21, 0.35), (63, 0.35), (126, 0.30)):
        if len(close) > window:
            ret = last / float(close.iloc[-window - 1]) - 1.0
            scores.append((np.tanh(ret * 8.0) * 50.0 + 50.0, weight))
    if 'RSI' in data.columns:
        rsi = float(data['RSI'].iloc[-1])
        scores.append((_clip01((rsi - 50) * 2.0 + 50.0), 0.30))
    if not scores:
        return 50.0, 'Neutral momentum'
    value = sum(s * w for s, w in scores) / sum(w for _, w in scores)
    label = 'Strong momentum' if value >= 65 else 'Weak momentum' if value <= 35 else 'Neutral momentum'
    return _clip01(value), label


def _trend_score(data: pd.DataFrame) -> tuple:
    close = data['Close'].astype(float)
    last = float(close.iloc[-1])
    parts = []
    for ma_name in ('MA20', 'MA50', 'SMA_20', 'SMA_50'):
        if ma_name in data.columns:
            ma = float(data[ma_name].iloc[-1])
            if ma == ma:
                parts.append(np.tanh((last / ma - 1.0) * 20.0) * 50.0 + 50.0)
    if 'Supertrend_dir' in data.columns:
        direction = float(data['Supertrend_dir'].iloc[-1])
        parts.append(70.0 if direction > 0 else 30.0)
    if 'ADX' in data.columns:
        adx = float(data['ADX'].iloc[-1])
        if adx == adx:
            parts.append(min(100.0, 40.0 + adx))
    if not parts:
        return 50.0, 'Neutral trend'
    value = float(np.mean(parts))
    label = 'Uptrend' if value >= 60 else 'Downtrend' if value <= 40 else 'Sideways'
    return _clip01(value), label


def _volatility_score(data: pd.DataFrame) -> tuple:
    close = data['Close'].astype(float)
    if 'ATR_14' in data.columns and len(close) > 20:
        atr_pct = (data['ATR_14'] / close).dropna()
        if len(atr_pct) >= 20:
            current = float(atr_pct.iloc[-1])
            rank = float((atr_pct.iloc[-20:] < current).mean())
            # Low recent ATR percentile -> calmer, higher score.
            return _clip01(100.0 - rank * 100.0), 'Calm' if rank < 0.4 else 'Volatile'
    log_return = np.log(close / close.shift(1)).dropna()
    if len(log_return) >= 20:
        vol = float(log_return.iloc[-20:].std())
        return _clip01(100.0 - min(1.0, vol * 50 * 100)), 'Calm' if vol < 0.015 else 'Volatile'
    return 50.0, 'Neutral volatility'


def _volume_score(data: pd.DataFrame) -> tuple:
    if 'VolumeSMA_ratio' in data.columns:
        ratio = float(data['VolumeSMA_ratio'].iloc[-1])
        return _clip01(np.tanh((ratio - 1.0) * 2.0) * 50.0 + 50.0), \
            'Above-average volume' if ratio > 1.1 else 'Below-average volume'
    if 'OBV_change_5' in data.columns:
        obv = float(data['OBV_change_5'].iloc[-1])
        return _clip01(np.tanh(obv * 3.0) * 50.0 + 50.0), \
            'OBV accumulation' if obv > 0 else 'OBV distribution'
    return 50.0, 'Neutral volume'


def _model_score(predicted_return) -> tuple:
    if predicted_return is None:
        return None, None
    predicted_return = float(predicted_return)
    value = np.tanh(predicted_return * 40.0) * 50.0 + 50.0
    label = (
        'Model sees upside' if predicted_return > 0.002
        else 'Model sees downside' if predicted_return < -0.002
        else 'Model sees flat move'
    )
    return _clip01(value), label


def compute_score(data: pd.DataFrame, predicted_return=None) -> dict:
    """Composite score with per-component breakdown and plain-language notes."""
    momentum, momentum_note = _momentum_score(data)
    trend, trend_note = _trend_score(data)
    volatility, volatility_note = _volatility_score(data)
    volume, volume_note = _volume_score(data)
    model, model_note = _model_score(predicted_return)

    weights = {
        'momentum': 0.28, 'trend': 0.28, 'volatility': 0.14,
        'volume': 0.10, 'model': 0.20,
    }
    components = {
        'momentum': (momentum, momentum_note),
        'trend': (trend, trend_note),
        'volatility': (volatility, volatility_note),
        'volume': (volume, volume_note),
    }
    if model is None:
        weights.pop('model')
    else:
        components['model'] = (model, model_note)

    total_weight = sum(weights.values())
    overall = sum(components[name][0] * w for name, w in weights.items()) / total_weight

    rating = (
        'Strong' if overall >= 70 else
        'Bullish' if overall >= 58 else
        'Neutral' if overall >= 42 else
        'Bearish' if overall >= 30 else 'Weak'
    )
    notes = [components[name][1] for name in weights]
    return {
        'overall': round(_clip01(overall), 1),
        'rating': rating,
        'components': {
            name: {'score': round(components[name][0], 1), 'note': components[name][1]}
            for name in components
        },
        'summary': '; '.join(notes),
    }

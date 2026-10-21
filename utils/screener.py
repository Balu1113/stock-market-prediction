"""Rule-based stock screener (Chartink-style) over OHLCV + indicators.

Rule DSL (JSON):
  condition: {"field": "RSI", "op": "crosses_below", "value": 30}
  group: {"op": "AND"|"OR", "conditions": [ ...nested groups or conditions... ]}
Fields are indicator/computed column names or synthetic keys
(close, volume, change_pct, ret_21d, sma20_cross etc.).
"""

import numpy as np
import pandas as pd

from utils.data_processor import DataProcessor
from utils.market_data import fetch_daily_history
from utils.universe import NIFTY50, symbol_label

MAX_SYMBOLS = 40
OPS = {
    'gt': lambda s, v: s > v,
    'gte': lambda s, v: s >= v,
    'lt': lambda s, v: s < v,
    'lte': lambda series, value: series <= value,
    'eq': lambda series, value: series == value,
    'crosses_above': lambda series, value: (series > value) & (series.shift(1) <= value),
    'crosses_below': lambda series, value: (series < value) & (series.shift(1) >= value),
}
ALL_INDICATORS = [
    'Moving Average', 'RSI', 'MACD', 'Bollinger Bands', 'Supertrend',
    'Stochastic', 'ADX', 'VWAP', 'OBV',
]
BASIC_FIELDS = {'close', 'open', 'high', 'low', 'volume', 'change_pct', 'ret_21d', 'ret_63d'}


def _needed_indicators(group: dict, found: set) -> None:
    condition = group.get('condition')
    if condition:
        found.add(str(condition.get('field', '')).upper())
        return
    for child in group.get('conditions', []) or []:
        _needed_indicators(child, found)


def _indicator_features_for(group: dict) -> list:
    needed = set()
    _needed_indicators(group, needed)
    mapping = {
        'RSI': 'RSI', 'MACD': 'MACD', 'MA20': 'Moving Average', 'MA50': 'Moving Average',
        'SMA20': 'Moving Average', 'SMA50': 'Moving Average',
        'BB_PCTB': 'Bollinger Bands', 'BB_WIDTH': 'Bollinger Bands',
        'SUPERTREND_DIST': 'Supertrend', 'SUPERTREND_DIR': 'Supertrend',
        'STOCH_K': 'Stochastic', 'STOCH_D': 'Stochastic',
        'ADX': 'ADX', 'ADX_DI_DIFF': 'ADX',
        'CLOSE_VWAP_RATIO': 'VWAP', 'OBV_CHANGE_5': 'OBV',
    }
    features = []
    for key in needed:
        if key in mapping and mapping[key] not in features:
            features.append(mapping[key])
    return features


def _series_for_field(data: pd.DataFrame, field: str):
    key = str(field).strip().upper()
    column_map = {
        'CLOSE': 'Close', 'OPEN': 'Open', 'HIGH': 'High', 'LOW': 'Low', 'VOLUME': 'Volume',
        'MA20': 'MA20', 'MA50': 'MA50', 'SMA20': 'MA20', 'SMA50': 'MA50',
        'RSI': 'RSI', 'MACD': 'MACD', 'SIGNAL': 'Signal',
        'BB_PCTB': 'BB_pctb', 'BB_WIDTH': 'BB_width',
        'SUPERTREND_DIST': 'Supertrend_dist', 'SUPERTREND_DIR': 'Supertrend_dir',
        'STOCH_K': 'Stoch_K', 'STOCH_D': 'Stoch_D',
        'ADX': 'ADX', 'ADX_DI_DIFF': 'ADX_DI_diff',
        'CLOSE_VWAP_RATIO': 'Close_VWAP_ratio', 'OBV_CHANGE_5': 'OBV_change_5',
    }
    if key == 'CHANGE_PCT':
        return data['Close'].pct_change() * 100.0
    if key == 'RET_21D':
        return data['Close'].pct_change(21) * 100.0
    if key == 'RET_63D':
        return data['Close'].pct_change(63) * 100.0
    column = column_map.get(key)
    if column and column in data.columns:
        return data[column]
    if field in data.columns:
        return data[field]
    raise ValueError(f'Unknown screener field: {field}')


def _eval_group(data: pd.DataFrame, group: dict) -> pd.Series:
    condition = group.get('condition')
    if condition:
        series = _series_for_field(data, condition.get('field', ''))
        op = str(condition.get('op', 'gt'))
        if op not in OPS:
            raise ValueError(f'Unknown screener operator: {op}')
        value = condition.get('value')
        mask = OPS[op](series.astype(float), float(value))
        return mask.fillna(False)

    children = group.get('conditions', []) or []
    if not children:
        return pd.Series(True, index=data.index)
    combine = str(group.get('op', 'AND')).upper()
    result = _eval_group(data, children[0])
    for child in children[1:]:
        child_mask = _eval_group(data, child)
        result = (result & child_mask) if combine == 'AND' else (result | child_mask)
    return result.fillna(False)


def _prepare(symbol: str, period: str = '1y') -> pd.DataFrame | None:
    raw = fetch_daily_history(symbol, period=period)
    if raw is None or len(raw) < 30:
        return None
    return raw


def scan_universe(rules: dict, symbols=None) -> list:
    """Run the rule group over the universe; return matching symbols."""
    symbols = [str(s).upper() for s in (symbols or NIFTY50)][:MAX_SYMBOLS]
    features = _indicator_features_for(rules)
    matches = []

    for symbol in symbols:
        try:
            raw = _prepare(symbol)
            if raw is None:
                continue
            data = DataProcessor().add_indicators(raw, features)
            mask = _eval_group(data, rules)
            if not bool(mask.iloc[-1]):
                continue
            last = data.iloc[-1]
            matches.append({
                'symbol': symbol,
                'label': symbol_label(symbol),
                'close': float(last['Close']),
                'change_pct': float(data['Close'].pct_change().iloc[-1] * 100),
                'volume': float(last['Volume']) if 'Volume' in data.columns and pd.notna(last['Volume']) else None,
                'rsi': float(last['RSI']) if 'RSI' in data.columns and pd.notna(last['RSI']) else None,
                'sma20': float(last['MA20']) if 'MA20' in data.columns and pd.notna(last['MA20']) else None,
                'sma50': float(last['MA50']) if 'MA50' in data.columns and pd.notna(last['MA50']) else None,
            })
        except Exception:
            continue
    return matches


def backtest_rules(rules: dict, symbol: str, months: int = 12, forward_days: int = 5) -> dict:
    """Historical hit-rate of the rule on one symbol (monthly buckets)."""
    period = f'{max(6, months)}mo'
    raw = _prepare(symbol, period=period)
    if raw is None or len(raw) < 60:
        raise ValueError('Not enough history to backtest this symbol.')
    features = _indicator_features_for(rules)
    data = DataProcessor().add_indicators(raw, features)
    mask = _eval_group(data, rules)

    closes = data['Close'].astype(float)
    forward = closes.shift(-forward_days) / closes - 1.0

    buckets = {}
    for ts, hit in mask.items():
        if not hit:
            continue
        key = f'{ts.year}-{ts.month:02d}'
        fwd = forward.loc[ts]
        buckets.setdefault(key, []).append(float(fwd) if pd.notna(fwd) else np.nan)

    rows = []
    for month, values in sorted(buckets.items()):
        array = np.array([v for v in values if not np.isnan(v)], dtype=float)
        rows.append({
            'month': month,
            'signals': len(values),
            'hit_rate': float((array > 0).mean() * 100) if len(array) else None,
            'avg_forward_return_pct': float(array.mean() * 100) if len(array) else None,
        })
    total = sum(row['signals'] for row in rows)
    hits = sum(
        row['signals'] * (row['hit_rate'] or 0) / 100 for row in rows
    )
    return {
        'symbol': symbol,
        'forward_days': forward_days,
        'months': rows,
        'total_signals': total,
        'overall_hit_rate': (hits / total * 100) if total else None,
    }

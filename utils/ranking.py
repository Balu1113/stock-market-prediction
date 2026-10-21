"""Multi-symbol ranking: lightweight next-day prediction + composite score."""

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from utils.data_processor import DataProcessor
from utils.market_data import fetch_daily_history
from utils.patterns import detect_patterns
from utils.scores import compute_score
from utils.universe import NIFTY50, SECTOR_MAP, symbol_label

RANKING_FEATURES = ['Moving Average', 'RSI', 'MACD']


def _next_day_return(data: pd.DataFrame) -> tuple:
    """Fit a leakage-safe Ridge on the last year and predict the next-day return."""
    processed = DataProcessor().process_data(data.copy(), RANKING_FEATURES)
    feature_columns = [
        column for column in processed.columns
        if column not in ('Close', 'Open', 'High', 'Low', 'Volume', 'Dividends', 'Stock Splits')
    ]
    if len(processed) < 60 or not feature_columns:
        return None, None

    log_return = np.log(processed['Close'] / processed['Close'].shift(1))
    frame = processed[feature_columns].copy()
    frame['target'] = log_return.shift(-1)
    frame.dropna(inplace=True)
    if len(frame) < 40:
        return None, None

    split = int(len(frame) * 0.8)
    train = frame.iloc[:split]
    scaler = StandardScaler()
    X_train = scaler.fit_transform(train[feature_columns])
    y_train = train['target'].to_numpy()
    model = Ridge(alpha=1.0)
    model.fit(X_train, y_train)

    last_row = frame[feature_columns].iloc[[-1]]
    predicted = float(model.predict(scaler.transform(last_row))[0])
    return predicted, processed


def rank_symbols(symbols=None, limit=15) -> list:
    """Rank symbols by predicted next-day return blended with composite score."""
    symbols = list(symbols or NIFTY50)
    limit = min(int(limit), 50)
    results = []

    for symbol in symbols:
        try:
            data = fetch_daily_history(symbol, period='1y')
            if data is None or len(data) < 60:
                continue
            predicted, processed = _next_day_return(data)
            if processed is None:
                continue
            score = compute_score(processed, predicted_return=predicted)
            recent_patterns = [
                item['pattern'] for item in detect_patterns(data, lookback=5)
                if item['date'] >= str(data.index[-1].date())
            ]
            price = float(data['Close'].iloc[-1])
            month_ago = float(data['Close'].iloc[-min(len(data), 22)])
            results.append({
                'symbol': symbol,
                'label': symbol_label(symbol),
                'sector': SECTOR_MAP.get(symbol, ''),
                'price': price,
                'predicted_return_pct': round(predicted * 100, 3) if predicted is not None else None,
                'score': score['overall'],
                'rating': score['rating'],
                'score_summary': score['summary'],
                'return_1m_pct': round((price / month_ago - 1.0) * 100, 2) if month_ago else None,
                'patterns': recent_patterns[:3],
            })
        except Exception:
            continue

    results.sort(
        key=lambda item: (
            item['score'],
            item['predicted_return_pct'] if item['predicted_return_pct'] is not None else -999,
        ),
        reverse=True,
    )
    return results[:limit]

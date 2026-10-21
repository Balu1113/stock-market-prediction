"""
LSTM training for the stock-market-prediction app — runs entirely in Google Colab.

HOW TO USE (no local GPU required):
1. Open https://colab.research.google.com -> New notebook.
2. Copy this whole file into a cell (File > Upload file, or paste) and run it.
   (Runtime > Change runtime type -> T4 GPU is optional; CPU is fine, ~5-10 min.)
3. When it finishes, two files are produced:
      nse_lstm.keras        (trained model weights)
      nse_lstm_config.json  (feature list, lookback, scaler stats)
4. Download them from the Colab file browser (they land in /content/models/).
5. Copy BOTH files into the `models/` folder of your project repository
   (next to requirements.txt), then restart Django.
6. In the app, choose model "LSTM (Colab)".

IMPORTANT: the feature engineering below must stay identical to
utils/data_processor.py in the repository (it is intentionally duplicated so
this script is fully self-contained for Colab).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

# ----------------------------------------------------------------- config ---
SYMBOLS = [
    'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS',
    'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'LT.NS', 'HINDUNILVR.NS',
    'KOTAKBANK.NS', 'AXISBANK.NS', 'MARUTI.NS', 'SUNPHARMA.NS', 'TITAN.NS',
    'ULTRACEMCO.NS', 'ASIANPAINT.NS', 'BAJFINANCE.NS', 'WIPRO.NS', 'NTPC.NS',
]
PERIOD = '5y'
LOOKBACK = 20          # trading days of history the LSTM sees per prediction
TRAIN_FRACTION = 0.8   # chronological split per symbol
EPOCHS = 60
BATCH_SIZE = 64
LEARNING_RATE = 1e-3
RANDOM_SEED = 42

# Curated features — keep in sync with utils/data_processor.py.
ALWAYS_ON_FEATURES = [
    'LogReturn_10',
    'ATR_14',
    'HighLowRange',
    'OvernightReturn',
    'VolumeSMA_ratio',
]


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Stationary features computed only from data up to and including day t."""
    out = df.copy()
    close = out['Close'].astype(float)
    log_return = np.log(close / close.shift(1))

    out['LogReturn_10'] = log_return.rolling(window=10).mean()

    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            out['High'] - out['Low'],
            (out['High'] - previous_close).abs(),
            (out['Low'] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out['ATR_14'] = true_range.rolling(window=14).mean()
    out['HighLowRange'] = (out['High'] - out['Low']) / close
    out['OvernightReturn'] = np.log(out['Open'].astype(float) / close.shift(1))
    out['VolumeSMA_ratio'] = (
        pd.to_numeric(out['Volume'], errors='coerce')
        / pd.to_numeric(out['Volume'], errors='coerce').rolling(window=20).mean()
    )
    return out


def build_dataset():
    """Download symbols and return (sequences, targets, dates, feature_frame)."""
    all_sequences, all_targets, all_dates = [], [], []
    feature_frames = []

    for symbol in SYMBOLS:
        raw = yf.Ticker(symbol).history(period=PERIOD, auto_adjust=True)
        if raw is None or raw.empty or len(raw) < LOOKBACK + 40:
            print(f'Skipping {symbol}: not enough data')
            continue
        if raw.index.tz is not None:
            raw.index = raw.index.tz_localize(None)
        raw = raw[['Open', 'High', 'Low', 'Close', 'Volume']].apply(
            pd.to_numeric, errors='coerce'
        )
        frame = add_features(raw).dropna()
        if len(frame) < LOOKBACK + 40:
            print(f'Skipping {symbol}: too few rows after features')
            continue

        values = frame[ALWAYS_ON_FEATURES].to_numpy(dtype=float)
        close = frame['Close'].to_numpy(dtype=float)
        log_return = np.log(close[1:] / close[:-1])  # return t -> t+1
        feature_frames.append(frame)

        for i in range(LOOKBACK - 1, len(frame) - 1):
            # Sequence ending at day t predicts the return from t to t+1.
            all_sequences.append(values[i - LOOKBACK + 1:i + 1])
            all_targets.append(log_return[i])
            all_dates.append((symbol, frame.index[i]))

        print(f'{symbol}: {len(frame)} rows')

    return (
        np.stack(all_sequences),
        np.asarray(all_targets, dtype=float),
        all_dates,
        feature_frames,
    )


def main():
    import tensorflow as tf
    from tensorflow import keras

    tf.random.set_seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    sequences, targets, dates, _ = build_dataset()
    print(f'Total sequences: {len(sequences)}  features: {sequences.shape[2]}')

    # Chronological split across the concatenated dataset (no shuffle).
    split = int(len(sequences) * TRAIN_FRACTION)
    x_train, x_test = sequences[:split], sequences[split:]
    y_train, y_test = targets[:split], targets[split:]

    # Standardize each feature using TRAINING statistics only.
    flat_train = x_train.reshape(-1, x_train.shape[2])
    scaler_mean = flat_train.mean(axis=0)
    scaler_scale = flat_train.std(axis=0)
    scaler_scale = np.where(scaler_scale < 1e-8, 1.0, scaler_scale)
    x_train = (x_train - scaler_mean) / scaler_scale
    x_test = (x_test - scaler_mean) / scaler_scale

    model = keras.Sequential([
        keras.layers.Input(shape=(LOOKBACK, len(ALWAYS_ON_FEATURES))),
        keras.layers.LSTM(64, return_sequences=False),
        keras.layers.Dropout(0.2),
        keras.layers.Dense(32, activation='relu'),
        keras.layers.Dense(1),  # next-day log return
    ])
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=LEARNING_RATE),
        loss='huber',
    )
    model.summary()

    history = model.fit(
        x_train, y_train,
        validation_split=0.15,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        callbacks=[keras.callbacks.EarlyStopping(
            monitor='val_loss', patience=8, restore_best_weights=True,
        )],
        verbose=1,
    )

    pred_test = model.predict(x_test, verbose=0).ravel()
    rmse = float(np.sqrt(np.mean((pred_test - y_test) ** 2)))
    baseline_rmse = float(np.sqrt(np.mean(y_test ** 2)))
    directional = float(np.mean(np.sign(pred_test) == np.sign(y_test)))
    baseline_directional = float(np.mean(y_test > 0))
    print('\n=== Holdout evaluation (last 20% chronologically) ===')
    print(f'RMSE (returns):            {rmse:.6f}   (no-change baseline {baseline_rmse:.6f})')
    print(f'Directional accuracy:      {directional * 100:.1f}%   (always-up baseline {baseline_directional * 100:.1f}%)')

    out_dir = Path('/content/models')
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / 'nse_lstm.keras'
    config_path = out_dir / 'nse_lstm_config.json'

    model.save(model_path)
    config = {
        'features': ALWAYS_ON_FEATURES,
        'lookback': LOOKBACK,
        'scaler_mean': [float(v) for v in scaler_mean],
        'scaler_scale': [float(v) for v in scaler_scale],
        'symbols': SYMBOLS,
        'period': PERIOD,
        'train_fraction': TRAIN_FRACTION,
        'holdout_rmse': rmse,
        'holdout_directional_accuracy': directional,
    }
    config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')

    print(f'\nSaved: {model_path}')
    print(f'Saved: {config_path}')
    print('Download BOTH files and place them in the repo models/ folder.')


if __name__ == '__main__':
    main()

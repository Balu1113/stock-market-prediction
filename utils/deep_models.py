import json
from pathlib import Path

import numpy as np


MODELS_DIR = Path(__file__).resolve().parent.parent / 'models'
DEEP_MODEL_PATH = MODELS_DIR / 'nse_lstm.keras'
DEEP_CONFIG_PATH = MODELS_DIR / 'nse_lstm_config.json'

MISSING_FILES_MESSAGE = (
    'LSTM model files not found. Train the model on Google Colab using '
    'colab/train_lstm_nse.py, then copy nse_lstm.keras and '
    'nse_lstm_config.json into the models/ folder of this repository.'
)


def deep_model_available() -> bool:
    return DEEP_MODEL_PATH.exists() and DEEP_CONFIG_PATH.exists()


def load_deep_bundle():
    """Load the Colab-trained Keras model and its preprocessing config."""
    if not deep_model_available():
        raise ValueError(MISSING_FILES_MESSAGE)
    try:
        from tensorflow.keras.models import load_model
    except ImportError as error:
        raise ValueError(
            'TensorFlow is not installed on the server. '
            'Run: pip install tensorflow'
        ) from error

    config = json.loads(DEEP_CONFIG_PATH.read_text(encoding='utf-8'))
    model = load_model(DEEP_MODEL_PATH)
    return model, config


class DeepReturnModel:
    """Inference-only wrapper around a Colab-trained Keras sequence model."""

    def __init__(self, model, config):
        self.model = model
        self.config = config
        self.features = list(config['features'])
        self.lookback = int(config.get('lookback', 20))
        self.mean = np.asarray(config['scaler_mean'], dtype=float)
        self.scale = np.asarray(config['scaler_scale'], dtype=float)

    def scale_features(self, values: np.ndarray) -> np.ndarray:
        return (np.asarray(values, dtype=float) - self.mean) / self.scale

    def build_sequences(self, feature_matrix: np.ndarray):
        """Turn an (n_rows, n_features) matrix into (batch, lookback, n_features)."""
        scaled = self.scale_features(feature_matrix)
        lookback = self.lookback
        if len(scaled) < lookback:
            raise ValueError(
                f'The LSTM needs at least {lookback} rows of history after '
                'feature engineering.'
            )
        sequences = np.stack([
            scaled[i - lookback + 1:i + 1]
            for i in range(lookback - 1, len(scaled))
        ])
        positions = np.arange(lookback - 1, len(scaled))
        return sequences, positions

    def predict(self, sequences: np.ndarray) -> np.ndarray:
        return np.asarray(self.model.predict(sequences, verbose=0)).ravel()

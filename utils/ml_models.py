import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from utils.data_processor import DataProcessor
from utils.deep_models import DeepReturnModel, load_deep_bundle


# Curated model list: a 10-symbol NSE walk-forward benchmark showed no
# meaningful separation among single tabular models (~49-51% direction), so
# only a stable regularized linear model and a diversified ensemble are kept,
# plus an optional Colab-trained LSTM for users who want a deep model.
SUPPORTED_MODELS = (
    'Ridge Regression',
    'Ensemble (Auto)',
    'LSTM (Colab)',
)

# Raw OHLCV levels are non-stationary (they mostly encode "how recent is
# this row"); the engineered ratio/return features carry the same information
# in a stationary form, so levels are excluded from the feature set.
NON_FEATURE_COLUMNS = frozenset({
    'Close', 'Open', 'High', 'Low', 'Volume', 'Dividends', 'Stock Splits',
})


def feature_columns_for(data: pd.DataFrame) -> list:
    return [column for column in data.columns if column not in NON_FEATURE_COLUMNS]


class EnsembleModel:
    """Averages predictions from several regressors for a stabler forecast."""

    def __init__(self, models):
        self.models = models

    def fit(self, X, y):
        for model in self.models:
            model.fit(X, y)
        return self

    def predict(self, X):
        predictions = np.column_stack([model.predict(X) for model in self.models])
        return predictions.mean(axis=1)


class StockPredictor:
    """Predicts the next day's log return from features known at time t.

    The target for row t is log(Close[t+1] / Close[t]), so features computed
    at time t (indicators, lagged returns, volume, ...) never contain the
    answer. Price-level predictions are derived for plotting only.
    """

    def __init__(self, model_type: str = "Ridge Regression"):
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.test_index = None
        self.test_return_predictions = None
        self.test_actual_returns = None
        self.test_close = None

    def _build_tree_model(self):
        """Trees regularized for small, noisy financial datasets."""
        return RandomForestRegressor(
            n_estimators=200,
            max_depth=5,
            min_samples_leaf=10,
            random_state=42,
            n_jobs=-1,
        )

    def _build_boosting_model(self):
        try:
            import xgboost as xgb
        except ImportError as error:
            raise ValueError(
                "XGBoost is not installed on the server. Choose another model."
            ) from error
        return xgb.XGBRegressor(
            objective='reg:squarederror',
            n_estimators=300,
            learning_rate=0.03,
            max_depth=3,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=42,
            n_jobs=-1,
        )

    def create_model(self):
        """Create the specified model."""
        if self.model_type == "Ridge Regression":
            self.model = Ridge(alpha=1.0)
        elif self.model_type == "Ensemble (Auto)":
            parts = [Ridge(alpha=1.0), self._build_tree_model()]
            try:
                parts.append(self._build_boosting_model())
            except ValueError:
                parts.append(
                    GradientBoostingRegressor(
                        n_estimators=200,
                        learning_rate=0.05,
                        max_depth=3,
                        subsample=0.8,
                        random_state=42,
                    )
                )
            self.model = EnsembleModel(parts)
        elif self.model_type == "LSTM (Colab)":
            model, config = load_deep_bundle()
            self.model = DeepReturnModel(model, config)
        else:
            raise ValueError(
                f"Unsupported model type: {self.model_type}. "
                f"Choose one of: {', '.join(SUPPORTED_MODELS)}."
            )

    def feature_importances(self, feature_columns):
        """Normalized per-feature importance (absolute weight), best effort."""
        if self.model is None or isinstance(self.model, DeepReturnModel):
            return []

        importances = None
        if isinstance(self.model, EnsembleModel):
            collected = []
            for part in self.model.models:
                part_importance = self._single_model_importance(part, feature_columns)
                if part_importance is not None:
                    collected.append(part_importance)
            if collected:
                importances = np.mean(np.vstack(collected), axis=0)
        else:
            importances = self._single_model_importance(self.model, feature_columns)

        if importances is None:
            return []
        total = float(np.sum(np.abs(importances)))
        if total <= 0:
            return []
        normalized = np.abs(importances) / total
        ranked = sorted(
            (
                {'feature': str(name), 'importance': float(value)}
                for name, value in zip(feature_columns, normalized)
            ),
            key=lambda item: item['importance'],
            reverse=True,
        )
        return ranked

    @staticmethod
    def _single_model_importance(model, feature_columns):
        if hasattr(model, 'feature_importances_'):
            values = np.asarray(model.feature_importances_, dtype=float)
            if values.shape[0] == len(feature_columns):
                return values
        if hasattr(model, 'coef_'):
            values = np.abs(np.asarray(model.coef_, dtype=float)).ravel()
            if values.shape[0] == len(feature_columns):
                return values
        return None

    def _indicator_features(self, columns) -> list:
        features = []
        if 'MA20' in columns:
            features.append('Moving Average')
        if 'RSI' in columns:
            features.append('RSI')
        if 'MACD' in columns:
            features.append('MACD')
        return features

    def _build_supervised(self, data: pd.DataFrame, feature_columns: list) -> pd.DataFrame:
        """Pair features at t with the log return from t to t+1."""
        log_return = np.log(data['Close'] / data['Close'].shift(1))
        frame = data[feature_columns].copy()
        frame['target'] = log_return.shift(-1)
        frame.dropna(inplace=True)
        return frame

    def _forecast_future(self, data, feature_columns, prediction_days):
        """Recursively forecast future closes from predicted log returns."""
        processor = DataProcessor()
        indicator_features = self._indicator_features(data.columns)
        history = data.copy()
        future_predictions = []
        last_date = history.index[-1]

        for _ in range(prediction_days):
            rebuilt = processor.add_indicators(history, indicator_features)
            row = rebuilt[feature_columns].iloc[[-1]]
            previous_close = float(history['Close'].iloc[-1])

            if row.isna().any(axis=None):
                predicted_close = previous_close
            else:
                scaled = self.scaler.transform(row)
                predicted_return = float(self.model.predict(scaled)[0])
                predicted_close = previous_close * float(np.exp(predicted_return))
            future_predictions.append(predicted_close)

            next_date = last_date + pd.Timedelta(days=1)
            while next_date in history.index:
                next_date += pd.Timedelta(days=1)
            synthetic = history.iloc[[-1]].copy()
            synthetic.index = [next_date]
            for column in ('Close', 'Open', 'High', 'Low'):
                if column in synthetic.columns:
                    synthetic[column] = predicted_close
            history = pd.concat([history, synthetic])
            last_date = next_date

        return future_predictions

    def _forecast_future_deep(self, data, deep: DeepReturnModel, prediction_days):
        """Recursively forecast future closes with the sequence model."""
        processor = DataProcessor()
        history = data.copy()
        future_predictions = []
        last_date = history.index[-1]

        for _ in range(prediction_days):
            rebuilt = processor.add_indicators(history, [])
            window = rebuilt[deep.features].iloc[-deep.lookback:]
            previous_close = float(history['Close'].iloc[-1])

            if len(window) < deep.lookback or window.isna().any(axis=None):
                predicted_close = previous_close
            else:
                sequence = deep.scale_features(window.to_numpy(dtype=float))[None, ...]
                predicted_return = float(deep.predict(sequence)[0])
                predicted_close = previous_close * float(np.exp(predicted_return))
            future_predictions.append(predicted_close)

            next_date = last_date + pd.Timedelta(days=1)
            while next_date in history.index:
                next_date += pd.Timedelta(days=1)
            synthetic = history.iloc[[-1]].copy()
            synthetic.index = [next_date]
            for column in ('Close', 'Open', 'High', 'Low'):
                if column in synthetic.columns:
                    synthetic[column] = predicted_close
            history = pd.concat([history, synthetic])
            last_date = next_date

        return future_predictions

    def _train_and_predict_deep(self, data, train_size, prediction_days):
        """Inference-only path for the Colab-trained LSTM (no local training)."""
        model, config = load_deep_bundle()
        deep = DeepReturnModel(model, config)
        self.model = deep

        missing = [name for name in deep.features if name not in data.columns]
        if missing:
            raise ValueError(
                'The trained LSTM expects features that are missing from this '
                f'dataset: {", ".join(missing)}. Use Yahoo Finance or Kite '
                'data (which include Open/High/Low/Volume) with this model.'
            )

        feature_matrix = data[deep.features].to_numpy(dtype=float)
        sequences, positions = deep.build_sequences(feature_matrix)
        predicted_returns = deep.predict(sequences)

        log_return = np.log(data['Close'] / data['Close'].shift(1))
        all_targets = log_return.shift(-1).to_numpy(dtype=float)
        targets = all_targets[positions]
        dates = data.index[positions]
        closes = data['Close'].to_numpy(dtype=float)[positions]

        valid = ~np.isnan(targets)
        sequences, targets, dates, closes, predicted_returns = (
            sequences[valid],
            targets[valid],
            dates[valid],
            closes[valid],
            predicted_returns[valid],
        )
        if len(targets) < 4:
            raise ValueError('Not enough usable history for the LSTM model.')

        split_index = int(round(len(targets) * train_size))
        split_index = max(1, min(len(targets) - 1, split_index))

        self.test_index = dates[split_index:]
        self.test_return_predictions = predicted_returns[split_index:]
        self.test_actual_returns = targets[split_index:]
        self.test_close = closes[split_index:]

        y_train = targets[:split_index]
        y_test = targets[split_index:]
        predictions = self.test_close * np.exp(self.test_return_predictions)
        future_predictions = self._forecast_future_deep(
            data, deep, prediction_days
        )

        empty = np.empty((0, len(deep.features)))
        return (
            empty,
            empty,
            y_train,
            y_test,
            predictions,
            np.array(future_predictions),
        )

    def train_and_predict(
        self, data: pd.DataFrame, train_size: float = 0.8, prediction_days: int = 7
    ) -> tuple:
        """Train model and predict next-day returns without lookahead leakage."""
        if self.model_type == 'LSTM (Colab)':
            return self._train_and_predict_deep(data, train_size, prediction_days)

        feature_columns = feature_columns_for(data)
        if not feature_columns:
            raise ValueError(
                'No usable features after engineering. Select at least one '
                'indicator (Moving Average, RSI, or MACD).'
            )

        supervised = self._build_supervised(data, feature_columns)
        if len(supervised) < 4:
            raise ValueError('Not enough usable history after building features.')

        split_index = int(round(len(supervised) * train_size))
        split_index = max(1, min(len(supervised) - 1, split_index))
        train_df = supervised.iloc[:split_index]
        test_df = supervised.iloc[split_index:]

        # Fit the scaler on the training window only to avoid lookahead bias.
        self.scaler = StandardScaler()
        X_train = self.scaler.fit_transform(train_df[feature_columns])
        y_train = train_df['target'].to_numpy()
        X_test = self.scaler.transform(test_df[feature_columns])
        y_test = test_df['target'].to_numpy()

        self.create_model()
        self.model.fit(X_train, y_train)
        predicted_returns = self.model.predict(X_test)

        self.test_index = test_df.index
        self.test_return_predictions = predicted_returns
        self.test_actual_returns = y_test
        self.test_close = data.loc[test_df.index, 'Close'].to_numpy()

        # One-step predicted prices (actual close grown by the predicted
        # return) for plotting against history.
        predictions = self.test_close * np.exp(predicted_returns)

        future_predictions = self._forecast_future(
            data, feature_columns, prediction_days
        )

        return (
            X_train,
            X_test,
            y_train,
            y_test,
            predictions,
            np.array(future_predictions),
        )

    def calculate_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> dict:
        """Metrics on next-day log returns, with a naive no-change baseline."""
        if len(y_true) < 2:
            return {
                'rmse': 0.0,
                'mae': 0.0,
                'r2': 0.0,
                'directional_accuracy': 0.0,
                'baseline_rmse': 0.0,
                'baseline_directional_accuracy': 0.0,
            }
        y_true = np.asarray(y_true, dtype=float)
        y_pred = np.asarray(y_pred, dtype=float)
        baseline = np.zeros_like(y_true)
        return {
            'rmse': float(np.sqrt(mean_squared_error(y_true, y_pred))),
            'mae': float(mean_absolute_error(y_true, y_pred)),
            'r2': float(r2_score(y_true, y_pred)),
            'directional_accuracy': float(
                np.mean(np.sign(y_true) == np.sign(y_pred))
            ),
            # Naive baseline: predict "price will not move" (zero return).
            'baseline_rmse': float(
                np.sqrt(mean_squared_error(y_true, baseline))
            ),
            # Naive directional baseline: always predict "up".
            'baseline_directional_accuracy': float(np.mean(y_true > 0)),
        }

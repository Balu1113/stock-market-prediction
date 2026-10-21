import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from utils.data_processor import DataProcessor


class StockPredictor:
    def __init__(self, model_type: str = "Linear Regression"):
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()

    def create_model(self):
        """Create the specified model."""
        if self.model_type == "Linear Regression":
            self.model = LinearRegression()
        elif self.model_type == "Random Forest":
            self.model = RandomForestRegressor(
                n_estimators=100, random_state=42, n_jobs=-1
            )
        elif self.model_type == "XGBoost":
            try:
                import xgboost as xgb
            except ImportError as error:
                raise ValueError(
                    "XGBoost is not installed on the server. Choose another model."
                ) from error
            self.model = xgb.XGBRegressor(
                objective='reg:squarederror',
                n_estimators=100,
                random_state=42,
                n_jobs=-1,
            )
        else:
            raise ValueError(f"Unsupported model type: {self.model_type}")

    def _indicator_features(self, columns) -> list:
        features = []
        if 'MA20' in columns:
            features.append('Moving Average')
        if 'RSI' in columns:
            features.append('RSI')
        if 'MACD' in columns:
            features.append('MACD')
        return features

    def _forecast_future(self, data, feature_columns, prediction_days):
        """Recursively forecast future closes, rebuilding indicators each step."""
        processor = DataProcessor()
        indicator_features = self._indicator_features(data.columns)
        close = data['Close'].astype(float).copy()
        future_predictions = []
        last_date = close.index[-1]

        for step in range(prediction_days):
            rebuilt = processor.add_indicators(
                pd.DataFrame({'Close': close}), indicator_features
            )
            row = rebuilt[feature_columns].iloc[[-1]]

            if row.isna().any(axis=None):
                future_predictions.append(float(close.iloc[-1]))
            else:
                scaled = self.scaler.transform(row)
                future_predictions.append(float(self.model.predict(scaled)[0]))

            next_date = last_date + pd.Timedelta(days=step + 1)
            close = pd.concat([
                close,
                pd.Series([future_predictions[-1]], index=[next_date]),
            ])

        return future_predictions

    def train_and_predict(
        self, data: pd.DataFrame, train_size: float = 0.8, prediction_days: int = 7
    ) -> tuple:
        """Train model and make predictions without lookahead leakage."""
        feature_columns = [col for col in data.columns if col != 'Close']
        if not feature_columns:
            raise ValueError('Select at least one indicator before training.')

        split_index = int(round(len(data) * train_size))
        split_index = max(1, min(len(data) - 1, split_index))
        train_df = data.iloc[:split_index]
        test_df = data.iloc[split_index:]

        # Fit the scaler on the training window only to avoid lookahead bias.
        self.scaler = StandardScaler()
        X_train = self.scaler.fit_transform(train_df[feature_columns])
        y_train = train_df['Close'].to_numpy()
        X_test = self.scaler.transform(test_df[feature_columns])
        y_test = test_df['Close'].to_numpy()

        self.create_model()
        self.model.fit(X_train, y_train)
        predictions = self.model.predict(X_test)

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
        """Calculate model performance metrics."""
        if len(y_true) < 2:
            return {'rmse': 0.0, 'mae': 0.0, 'r2': 0.0}
        return {
            'rmse': float(np.sqrt(mean_squared_error(y_true, y_pred))),
            'mae': float(mean_absolute_error(y_true, y_pred)),
            'r2': float(r2_score(y_true, y_pred)),
        }

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

class StockPredictor:
    def __init__(self, model_type: str = "Linear Regression"):
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        
    def prepare_data(self, data: pd.DataFrame) -> tuple:
        """Prepare features and target variables."""
        # Use all columns except 'Close' as features
        feature_columns = [col for col in data.columns if col != 'Close']
        X = data[feature_columns]
        y = data['Close']
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        return X_scaled, y
        
    def create_model(self):
        """Create the specified model."""
        if self.model_type == "Linear Regression":
            self.model = LinearRegression()
        elif self.model_type == "Random Forest":
            self.model = RandomForestRegressor(n_estimators=100, 
                                             random_state=42,
                                             n_jobs=-1)
        else:
            raise ValueError(f"Unsupported model type: {self.model_type}")
            
    def train_and_predict(self, data: pd.DataFrame, 
                         train_size: float = 0.8,
                         prediction_days: int = 7) -> tuple:
        """Train model and make predictions."""
        X_scaled, y = self.prepare_data(data)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, train_size=train_size, shuffle=False
        )
        
        # Create and train model
        self.create_model()
        self.model.fit(X_train, y_train)
        
        # Make predictions
        predictions = self.model.predict(X_test)
        
        # Generate future predictions
        last_features = X_scaled[-1:].copy()
        future_predictions = []
        
        for _ in range(prediction_days):
            next_pred = self.model.predict(last_features)[0]
            future_predictions.append(next_pred)
            
            # Update features for next prediction
            # This is a simplified approach; in practice, you'd need to update all features
            last_features = last_features.copy()
        
        return X_train, X_test, y_train, y_test, predictions, np.array(future_predictions)
    
    def calculate_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> dict:
        """Calculate model performance metrics."""
        return {
            'rmse': np.sqrt(mean_squared_error(y_true, y_pred)),
            'mae': mean_absolute_error(y_true, y_pred),
            'r2': r2_score(y_true, y_pred)
        }
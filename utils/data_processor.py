import pandas as pd
import numpy as np
from typing import List

class DataProcessor:
    def load_data(self, file) -> pd.DataFrame:
        """Load and validate the input data."""
        df = pd.read_csv(file)
        
        # Validate required columns
        required_columns = ['Date', 'Close']
        if not all(col in df.columns for col in required_columns):
            raise ValueError("CSV must contain 'Date' and 'Close' columns")
        
        # Convert Date to datetime and set as index
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        
        return df

    def calculate_moving_average(self, data: pd.DataFrame, window: int = 20) -> pd.Series:
        """Calculate moving average."""
        return data['Close'].rolling(window=window).mean()

    def calculate_rsi(self, data: pd.DataFrame, periods: int = 14) -> pd.Series:
        """Calculate Relative Strength Index."""
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_macd(self, data: pd.DataFrame) -> tuple:
        """Calculate MACD (Moving Average Convergence Divergence)."""
        exp1 = data['Close'].ewm(span=12, adjust=False).mean()
        exp2 = data['Close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        return macd, signal

    def add_indicators(self, data: pd.DataFrame, features: List[str]) -> pd.DataFrame:
        """Engineer indicator and statistical feature columns."""
        df = data.copy()

        if "Moving Average" in features:
            df['MA20'] = self.calculate_moving_average(df)
            df['MA50'] = self.calculate_moving_average(df, window=50)

        if "RSI" in features:
            df['RSI'] = self.calculate_rsi(df)

        if "MACD" in features:
            df['MACD'], df['Signal'] = self.calculate_macd(df)

        close = df['Close'].astype(float)
        log_return = np.log(close / close.shift(1))

        # Curated always-on features: kept only if they showed stable
        # predictive rank-IC across a 10-symbol NSE benchmark (|IC| >= 0.025,
        # sign stability >= 70%). Every feature at t uses data up to t;
        # the model target is the return from t to t+1.
        df['LogReturn_10'] = log_return.rolling(window=10).mean()

        if {'High', 'Low'}.issubset(df.columns):
            previous_close = close.shift(1)
            true_range = pd.concat(
                [
                    df['High'] - df['Low'],
                    (df['High'] - previous_close).abs(),
                    (df['Low'] - previous_close).abs(),
                ],
                axis=1,
            ).max(axis=1)
            df['ATR_14'] = true_range.rolling(window=14).mean()
            df['HighLowRange'] = (df['High'] - df['Low']) / close

        if 'Open' in df.columns:
            df['OvernightReturn'] = np.log(df['Open'].astype(float) / close.shift(1))

        if 'Volume' in df.columns:
            volume = pd.to_numeric(df['Volume'], errors='coerce')
            df['VolumeSMA_ratio'] = volume / volume.rolling(window=20).mean()

        return df

    def process_data(self, data: pd.DataFrame, features: List[str]) -> pd.DataFrame:
        """Process data and engineer features."""
        df = self.add_indicators(data, features)

        # Drop NaN values
        df.dropna(inplace=True)

        return df
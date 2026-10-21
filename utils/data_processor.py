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

    def calculate_bollinger(self, data: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
        """Bollinger %B and bandwidth (stationary forms)."""
        close = data['Close'].astype(float)
        mid = close.rolling(window=window).mean()
        std = close.rolling(window=window).std()
        upper = mid + num_std * std
        lower = mid - num_std * std
        width = (upper - lower) / mid.replace(0, np.nan)
        pct_b = (close - lower) / (upper - lower).replace(0, np.nan)
        return pd.DataFrame({'BB_pctb': pct_b, 'BB_width': width}, index=data.index)

    def calculate_supertrend(self, data: pd.DataFrame, window: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
        """Supertrend direction and normalized distance (stationary forms)."""
        high = data['High'].astype(float)
        low = data['Low'].astype(float)
        close = data['Close'].astype(float)
        previous_close = close.shift(1)

        tr = pd.concat(
            [
                high - low,
                (high - previous_close).abs(),
                (low - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(window=window).mean()

        hl2 = (high + low) / 2.0
        upper = hl2 + multiplier * atr
        lower = hl2 - multiplier * atr

        direction = pd.Series(1.0, index=data.index)
        supertrend = pd.Series(np.nan, index=data.index)
        for i in range(len(close)):
            if i == 0 or np.isnan(atr.iloc[i]):
                supertrend.iloc[i] = lower.iloc[i]
                direction.iloc[i] = 1.0
                continue
            if close.iloc[i] > upper.iloc[i - 1]:
                direction.iloc[i] = 1.0
            elif close.iloc[i] < lower.iloc[i - 1]:
                direction.iloc[i] = -1.0
            else:
                direction.iloc[i] = direction.iloc[i - 1]

            if direction.iloc[i] == 1.0:
                candidate = lower.iloc[i]
                if direction.iloc[i - 1] == 1.0 and not np.isnan(supertrend.iloc[i - 1]):
                    candidate = max(candidate, supertrend.iloc[i - 1])
            else:
                candidate = upper.iloc[i]
                if direction.iloc[i - 1] == -1.0 and not np.isnan(supertrend.iloc[i - 1]):
                    candidate = min(candidate, supertrend.iloc[i - 1])
            supertrend.iloc[i] = candidate

        dist = (close - supertrend) / close.replace(0, np.nan)
        return pd.DataFrame(
            {'Supertrend_dist': dist, 'Supertrend_dir': direction.astype(float)},
            index=data.index,
        )

    def calculate_stochastic(self, data: pd.DataFrame, k_window: int = 14, d_window: int = 3) -> pd.DataFrame:
        """Stochastic oscillator %K and %D."""
        low_min = data['Low'].rolling(window=k_window).min()
        high_max = data['High'].rolling(window=k_window).max()
        denom = (high_max - low_min).replace(0, np.nan)
        percent_k = 100.0 * (data['Close'] - low_min) / denom
        percent_d = percent_k.rolling(window=d_window).mean()
        return pd.DataFrame({'Stoch_K': percent_k, 'Stoch_D': percent_d}, index=data.index)

    def calculate_adx(self, data: pd.DataFrame, window: int = 14) -> pd.DataFrame:
        """ADX and DI+/DI- spread."""
        high = data['High'].astype(float)
        low = data['Low'].astype(float)
        close = data['Close'].astype(float)
        previous_close = close.shift(1)
        previous_high = high.shift(1)
        previous_low = low.shift(1)

        tr = pd.concat(
            [
                high - low,
                (high - previous_close).abs(),
                (low - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        plus_dm = (high - previous_high).clip(lower=0)
        minus_dm = (previous_low - low).clip(lower=0)
        plus_dm[(plus_dm < minus_dm)] = 0.0
        minus_dm[(minus_dm < plus_dm)] = 0.0

        atr = tr.rolling(window=window).mean()
        plus_di = 100.0 * plus_dm.rolling(window=window).mean() / atr.replace(0, np.nan)
        minus_di = 100.0 * minus_dm.rolling(window=window).mean() / atr.replace(0, np.nan)
        dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        adx = dx.rolling(window=window).mean()
        return pd.DataFrame(
            {'ADX': adx, 'ADX_DI_diff': plus_di - minus_di},
            index=data.index,
        )

    def calculate_vwap_ratio(self, data: pd.DataFrame) -> pd.Series:
        """Close-to-cumulative-VWAP ratio (daily-bar approximation)."""
        typical = (
            data['High'].astype(float)
            + data['Low'].astype(float)
            + data['Close'].astype(float)
        ) / 3.0
        volume = pd.to_numeric(data['Volume'], errors='coerce').fillna(0.0)
        cumulative_pv = (typical * volume).cumsum()
        cumulative_v = volume.cumsum().replace(0, np.nan)
        vwap = cumulative_pv / cumulative_v
        return data['Close'].astype(float) / vwap.replace(0, np.nan)

    def calculate_obv_change(self, data: pd.DataFrame, window: int = 5) -> pd.Series:
        """On-balance-volume momentum (stationary stand-in for raw OBV)."""
        close = data['Close'].astype(float)
        volume = pd.to_numeric(data['Volume'], errors='coerce').fillna(0.0)
        direction = np.sign(close.diff()).fillna(0.0)
        obv = (direction * volume).cumsum()
        obv_sma = obv.rolling(window=20).mean().replace(0, np.nan)
        return (obv - obv_sma) / obv_sma.abs()

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

        has_ohlcv = {'High', 'Low'}.issubset(df.columns)

        if "Bollinger Bands" in features:
            bollinger = self.calculate_bollinger(df)
            df = df.join(bollinger)

        if "Supertrend" in features and has_ohlcv:
            supertrend = self.calculate_supertrend(df)
            df = df.join(supertrend)

        if "Stochastic" in features and has_ohlcv:
            stochastic = self.calculate_stochastic(df)
            df = df.join(stochastic)

        if "ADX" in features and has_ohlcv:
            adx = self.calculate_adx(df)
            df = df.join(adx)

        if "VWAP" in features and 'Volume' in df.columns:
            df['Close_VWAP_ratio'] = self.calculate_vwap_ratio(df)

        if "OBV" in features and 'Volume' in df.columns:
            df['OBV_change_5'] = self.calculate_obv_change(df)

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
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from dataclasses import dataclass

from utils.data_processor import DataProcessor


@dataclass
class TradePosition:
    entry_price: float
    entry_date: pd.Timestamp
    position_type: str  # 'long' or 'short'
    quantity: int
    exit_price: float = None
    exit_date: pd.Timestamp = None


STRATEGY_PRESETS = ('cross', 'rsi_reversion', 'supertrend', 'macd_cross', 'model')


def _prepare_indicators(data: pd.DataFrame, strategy: str) -> pd.DataFrame:
    features = ['Moving Average']
    if strategy == 'rsi_reversion':
        features.append('RSI')
    elif strategy == 'supertrend':
        features.append('Supertrend')
    elif strategy == 'macd_cross':
        features.append('MACD')
    return DataProcessor().add_indicators(data.copy(), features)


def strategy_signals(data: pd.DataFrame, strategy: str, params: dict | None = None) -> pd.DataFrame:
    """DataFrame with a Signal column: 1 = enter long at close, -1 = exit, 0 = hold."""
    params = params or {}
    df = _prepare_indicators(data, strategy)
    signal = pd.Series(0, index=df.index)

    if strategy == 'cross':
        fast = params.get('fast', 20)
        slow = params.get('slow', 50)
        sma_fast = df['Close'].rolling(fast).mean()
        sma_slow = df['Close'].rolling(slow).mean()
        above = sma_fast > sma_slow
        signal[above & ~above.shift(1, fill_value=False)] = 1
        signal[(~above) & above.shift(1, fill_value=False)] = -1

    elif strategy == 'rsi_reversion':
        period = params.get('period', 14)
        oversold = params.get('oversold', 30)
        overbought = params.get('overbought', 70)
        rsi = df['RSI'] if 'RSI' in df.columns else DataProcessor().calculate_rsi(df, period)
        prev = rsi.shift(1)
        signal[(rsi > oversold) & (prev <= oversold)] = 1
        signal[(rsi < overbought) & (prev >= overbought)] = -1

    elif strategy == 'supertrend':
        if 'Supertrend_dir' in df.columns:
            direction = df['Supertrend_dir']
            signal[(direction > 0) & (direction.shift(1) <= 0)] = 1
            signal[(direction < 0) & (direction.shift(1) >= 0)] = -1

    elif strategy == 'macd_cross':
        if {'MACD', 'Signal'}.issubset(df.columns):
            macd = df['MACD']
            sig = df['Signal']
            signal[(macd > sig) & (macd.shift(1) <= sig.shift(1))] = 1
            signal[(macd < sig) & (macd.shift(1) >= sig.shift(1))] = -1

    elif strategy == 'model':
        raise ValueError('Use simulate_with_model for the model strategy.')

    else:
        raise ValueError(f'Unknown strategy: {strategy}. Choose from {STRATEGY_PRESETS}.')

    df['Signal'] = signal
    return df


def _simulate_long_only(df: pd.DataFrame, initial_capital: float) -> Tuple[List[Dict], Dict]:
    capital = initial_capital
    trades: List[Dict] = []
    open_trade = None

    for ts, row in df.iterrows():
        sig = int(row['Signal'])
        price = float(row['Close'])
        if sig == 1 and open_trade is None:
            quantity = int(capital * 0.95 / price) if price > 0 else 0
            if quantity <= 0:
                continue
            capital -= quantity * price
            open_trade = {
                'entry_date': str(pd.Timestamp(ts).date()),
                'entry_price': price,
                'quantity': quantity,
            }
        elif sig == -1 and open_trade is not None:
            pnl = (price - open_trade['entry_price']) * open_trade['quantity']
            capital += open_trade['quantity'] * price
            trades.append({
                **open_trade,
                'exit_date': str(pd.Timestamp(ts).date()),
                'exit_price': price,
                'pnl': round(pnl, 2),
                'return_pct': round(
                    (price / open_trade['entry_price'] - 1.0) * 100, 3
                ),
            })
            open_trade = None

    equity_curve = []
    holding = 0
    cash = initial_capital
    open_trade = None
    for ts, row in df.iterrows():
        sig = int(row['Signal'])
        price = float(row['Close'])
        if sig == 1 and open_trade is None:
            holding = int(cash * 0.95 / price) if price > 0 else 0
            cash -= holding * price
            open_trade = True
        elif sig == -1 and open_trade:
            cash += holding * price
            holding = 0
            open_trade = None
        equity_curve.append({
            'date': str(pd.Timestamp(ts).date()),
            'equity': round(cash + holding * price, 2),
        })

    final_equity = equity_curve[-1]['equity'] if equity_curve else initial_capital
    wins = sum(1 for trade in trades if trade['pnl'] > 0)
    metrics = {
        'strategy': 'rules',
        'total_trades': len(trades),
        'profitable_trades': wins,
        'total_pnl': round(final_equity - initial_capital, 2),
        'win_rate': round(wins / len(trades) * 100, 2) if trades else 0.0,
        'avg_return': round(float(np.mean([t['return_pct'] for t in trades])), 3) if trades else 0.0,
        'final_capital': round(final_equity, 2),
        'buy_hold_return_pct': round(
            (float(df['Close'].iloc[-1]) / float(df['Close'].iloc[0]) - 1.0) * 100, 2
        ) if len(df) else None,
    }
    return trades, {'metrics': metrics, 'equity_curve': equity_curve}


class TradingStrategy:
    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: List[TradePosition] = []
        self.trade_history: List[Dict] = []

    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Backward-compatible golden/death-cross signals."""
        return strategy_signals(data, 'cross')

    def simulate_trades(self, data: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """Backward-compatible cross backtest."""
        df = self.calculate_signals(data)
        trades, detail = _simulate_long_only(df, self.initial_capital)
        self.trade_history = trades
        self.capital = detail['metrics']['final_capital']
        return df, detail['metrics']

    def run_backtest(self, data: pd.DataFrame, strategy: str, params: dict | None = None) -> dict:
        """Named-strategy backtest with signal frame, trade log, equity curve."""
        if strategy == 'model':
            raise ValueError('Model backtest requires predictions; use simulate_with_model.')
        df = strategy_signals(data, strategy, params)
        trades, detail = _simulate_long_only(df, self.initial_capital)
        return {
            'strategy': strategy,
            'params': params or {},
            'trades': trades,
            'metrics': detail['metrics'],
            'equity_curve': detail['equity_curve'],
            'signal_dates': {
                'buys': [
                    str(pd.Timestamp(ts).date())
                    for ts, row in df.iterrows() if int(row['Signal']) == 1
                ],
                'sells': [
                    str(pd.Timestamp(ts).date())
                    for ts, row in df.iterrows() if int(row['Signal']) == -1
                ],
            },
        }

    def simulate_with_model(
        self,
        data: pd.DataFrame,
        test_index,
        predicted_returns,
    ) -> Tuple[pd.DataFrame, Dict]:
        """Long-only backtest driven by model predictions.

        A predicted positive return for day t means holding from the close of
        t to the close of t+1; otherwise the model stays in cash.
        """
        index = pd.Index(test_index)
        predicted_returns = np.asarray(predicted_returns, dtype=float)
        positions = data.index.get_indexer(index)
        valid = positions >= 0
        positions = positions[valid]
        predicted_returns = predicted_returns[valid]

        if len(positions) < 2:
            return data, self.calculate_performance_metrics()

        closes = data['Close'].to_numpy(dtype=float)
        equity = self.initial_capital
        trade_returns = []
        entry_equity = None
        equity_curve = []

        for i in range(len(positions) - 1):
            signal_on = predicted_returns[i] > 0
            daily_return = closes[positions[i + 1]] / closes[positions[i]] - 1.0

            if signal_on:
                if entry_equity is None:
                    entry_equity = equity
                equity *= 1.0 + daily_return
            elif entry_equity is not None:
                trade_returns.append(equity / entry_equity - 1.0)
                entry_equity = None
            equity_curve.append({
                'date': str(pd.Timestamp(index[i]).date()),
                'equity': round(equity, 2),
            })

        if entry_equity is not None:
            trade_returns.append(equity / entry_equity - 1.0)

        self.capital = equity
        total_trades = len(trade_returns)
        profitable = sum(1 for trade_return in trade_returns if trade_return > 0)
        return data, {
            'strategy': 'model',
            'total_trades': total_trades,
            'profitable_trades': profitable,
            'total_pnl': float(equity - self.initial_capital),
            'win_rate': float(profitable / total_trades * 100) if total_trades else 0.0,
            'avg_return': float(np.mean(trade_returns) * 100) if trade_returns else 0.0,
            'final_capital': float(equity),
            'equity_curve': equity_curve,
        }

    def calculate_performance_metrics(self) -> Dict:
        """Calculate trading performance metrics."""
        if not self.trade_history:
            return {
                'total_trades': 0,
                'profitable_trades': 0,
                'total_pnl': 0,
                'win_rate': 0,
                'avg_return': 0,
                'final_capital': self.initial_capital
            }

        profitable_trades = sum(1 for trade in self.trade_history if trade['pnl'] > 0)
        total_pnl = sum(trade['pnl'] for trade in self.trade_history)
        avg_return = np.mean([trade['return_pct'] for trade in self.trade_history])

        return {
            'total_trades': len(self.trade_history),
            'profitable_trades': profitable_trades,
            'total_pnl': total_pnl,
            'win_rate': (profitable_trades / len(self.trade_history)) * 100,
            'avg_return': avg_return,
            'final_capital': self.capital
        }

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from dataclasses import dataclass

@dataclass
class TradePosition:
    entry_price: float
    entry_date: pd.Timestamp
    position_type: str  # 'long' or 'short'
    quantity: int
    exit_price: float = None
    exit_date: pd.Timestamp = None
    
class TradingStrategy:
    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: List[TradePosition] = []
        self.trade_history: List[Dict] = []
        
    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate trading signals based on technical indicators."""
        df = data.copy()
        
        # Calculate technical indicators
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        
        # Generate signals
        df['Signal'] = 0  # 0: Hold, 1: Buy, -1: Sell
        df.loc[df['SMA_20'] > df['SMA_50'], 'Signal'] = 1  # Golden Cross
        df.loc[df['SMA_20'] < df['SMA_50'], 'Signal'] = -1  # Death Cross
        
        return df
    
    def simulate_trades(self, data: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """Simulate trading based on signals."""
        df = self.calculate_signals(data)
        position = 0  # 0: No position, 1: Long, -1: Short
        
        for index, row in df.iterrows():
            if position == 0 and row['Signal'] == 1:  # Enter long
                position = 1
                quantity = int(self.capital * 0.95 / row['Close'])  # Use 95% of capital
                self.positions.append(TradePosition(
                    entry_price=row['Close'],
                    entry_date=index,
                    position_type='long',
                    quantity=quantity
                ))
                self.capital -= quantity * row['Close']
                
            elif position == 1 and row['Signal'] == -1:  # Exit long
                position = 0
                current_position = self.positions[-1]
                current_position.exit_price = row['Close']
                current_position.exit_date = index
                
                # Calculate profit/loss
                pnl = (row['Close'] - current_position.entry_price) * current_position.quantity
                self.capital += (current_position.quantity * row['Close'])
                
                self.trade_history.append({
                    'entry_date': current_position.entry_date,
                    'exit_date': current_position.exit_date,
                    'entry_price': current_position.entry_price,
                    'exit_price': current_position.exit_price,
                    'quantity': current_position.quantity,
                    'pnl': pnl,
                    'return_pct': (pnl / (current_position.entry_price * current_position.quantity)) * 100
                })
        
        return df, self.calculate_performance_metrics()
    
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
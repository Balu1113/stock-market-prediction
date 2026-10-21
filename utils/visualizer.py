import plotly.graph_objects as go
import pandas as pd
import numpy as np
from plotly.subplots import make_subplots


class Visualizer:
    def plot_predictions(self,
                        historical_data: pd.DataFrame,
                        predictions: np.ndarray,
                        future_predictions: np.ndarray,
                        future_lower=None,
                        future_upper=None) -> go.Figure:
        """Create an interactive plot of historical data and predictions."""
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=historical_data.index,
            y=historical_data['Close'],
            name='Historical',
            line=dict(color='#17B897')
        ))

        pred_index = historical_data.index[-len(predictions):]
        fig.add_trace(go.Scatter(
            x=pred_index,
            y=predictions,
            name='Predicted',
            line=dict(color='#FF6B6B', dash='dash')
        ))

        future_dates = pd.bdate_range(
            start=historical_data.index[-1] + pd.Timedelta(days=1),
            periods=len(future_predictions)
        )

        if future_lower is not None and future_upper is not None:
            lower = np.asarray(future_lower, dtype=float)
            upper = np.asarray(future_upper, dtype=float)
            fig.add_trace(go.Scatter(
                x=np.concatenate([future_dates, future_dates[::-1]]),
                y=np.concatenate([upper, lower[::-1]]),
                fill='toself',
                fillcolor='rgba(74,144,226,0.15)',
                line=dict(color='rgba(0,0,0,0)'),
                name='80% band',
                hoverinfo='skip',
            ))

        fig.add_trace(go.Scatter(
            x=future_dates,
            y=future_predictions,
            name='Future Predictions',
            line=dict(color='#4A90E2', dash='dot')
        ))

        fig.update_layout(
            title='Stock Price Prediction',
            xaxis_title='Date',
            yaxis_title='Price',
            hovermode='x unified',
            template='plotly_white',
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01
            )
        )

        return fig

    def plot_backtest(self, historical_data: pd.DataFrame, backtest: dict) -> go.Figure:
        """Price chart with buy/sell markers plus an equity-curve subplot."""
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            vertical_spacing=0.08,
            row_heights=[0.68, 0.32],
            subplot_titles=('Price & signals', 'Equity curve'),
        )

        fig.add_trace(
            go.Scatter(
                x=historical_data.index,
                y=historical_data['Close'],
                name='Close',
                line=dict(color='#17B897'),
            ),
            row=1, col=1,
        )

        buys = backtest.get('signal_dates', {}).get('buys', [])
        sells = backtest.get('signal_dates', {}).get('sells', [])
        if buys:
            buy_prices = [
                float(historical_data['Close'].loc[pd.Timestamp(day)])
                for day in buys if pd.Timestamp(day) in historical_data.index
            ]
            buy_dates = [
                pd.Timestamp(day) for day in buys if pd.Timestamp(day) in historical_data.index
            ]
            fig.add_trace(
                go.Scatter(
                    x=buy_dates, y=buy_prices, mode='markers',
                    name='Buy', marker=dict(symbol='triangle-up', size=11, color='#17B897'),
                ),
                row=1, col=1,
            )
        if sells:
            sell_prices = [
                float(historical_data['Close'].loc[pd.Timestamp(day)])
                for day in sells if pd.Timestamp(day) in historical_data.index
            ]
            sell_dates = [
                pd.Timestamp(day) for day in sells if pd.Timestamp(day) in historical_data.index
            ]
            fig.add_trace(
                go.Scatter(
                    x=sell_dates, y=sell_prices, mode='markers',
                    name='Sell', marker=dict(symbol='triangle-down', size=11, color='#FF6B6B'),
                ),
                row=1, col=1,
            )

        equity = backtest.get('equity_curve') or []
        if equity:
            fig.add_trace(
                go.Scatter(
                    x=[pd.Timestamp(row['date']) for row in equity],
                    y=[row['equity'] for row in equity],
                    name='Equity',
                    line=dict(color='#4A90E2'),
                ),
                row=2, col=1,
            )

        fig.update_layout(
            height=620, template='plotly_white', hovermode='x unified', showlegend=True
        )
        fig.update_yaxes(title_text='Price', row=1, col=1)
        fig.update_yaxes(title_text='Capital', row=2, col=1)
        return fig

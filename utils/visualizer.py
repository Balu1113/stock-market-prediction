import plotly.graph_objects as go
import pandas as pd
import numpy as np

class Visualizer:
    def plot_predictions(self, 
                        historical_data: pd.DataFrame,
                        predictions: np.ndarray,
                        future_predictions: np.ndarray) -> go.Figure:
        """Create an interactive plot of historical data and predictions."""
        fig = go.Figure()

        # Historical data
        fig.add_trace(go.Scatter(
            x=historical_data.index,
            y=historical_data['Close'],
            name='Historical',
            line=dict(color='#17B897')
        ))

        # Predictions
        pred_index = historical_data.index[-len(predictions):]
        fig.add_trace(go.Scatter(
            x=pred_index,
            y=predictions,
            name='Predicted',
            line=dict(color='#FF6B6B', dash='dash')
        ))

        # Future predictions
        future_dates = pd.date_range(
            start=historical_data.index[-1] + pd.Timedelta(days=1),
            periods=len(future_predictions)
        )
        fig.add_trace(go.Scatter(
            x=future_dates,
            y=future_predictions,
            name='Future Predictions',
            line=dict(color='#4A90E2', dash='dot')
        ))

        # Update layout
        fig.update_layout(
            title='Stock Price Prediction',
            xaxis_title='Date',
            yaxis_title='Price ($)',
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
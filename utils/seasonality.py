"""Seasonality stats: monthly and weekday average returns."""

import numpy as np
import pandas as pd


def seasonality_stats(data: pd.DataFrame) -> dict:
    """Monthly (year x month) and weekday average log returns in percent."""
    if len(data) < 30 or 'Close' not in data.columns:
        return {'monthly': None, 'weekday': None}

    log_return = np.log(data['Close'] / data['Close'].shift(1)).dropna()
    frame = pd.DataFrame({'ret': log_return})
    frame['year'] = frame.index.year
    frame['month'] = frame.index.month
    frame['weekday'] = frame.index.weekday
    # Keep weekdays only (0=Mon .. 4=Fri).
    frame = frame[frame['weekday'] <= 4]

    monthly = frame.pivot_table(index='year', columns='month', values='ret', aggfunc='mean') * 100
    monthly = monthly.round(3).where(pd.notna(monthly), None)

    weekday_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
    weekday = frame.groupby('weekday')['ret'].mean() * 100

    return {
        'monthly': {
            'years': [int(year) for year in monthly.index],
            'months': [int(month) for month in monthly.columns],
            'values': [
                [None if pd.isna(monthly.loc[year, month]) else float(monthly.loc[year, month])
                 for month in monthly.columns]
                for year in monthly.index
            ],
        },
        'weekday': {
            'labels': [weekday_labels[int(day)] for day in weekday.index],
            'values': [float(value) for value in weekday.values],
        },
    }


def seasonality_plot(data: pd.DataFrame, symbol: str = '') -> str:
    """Plotly JSON with monthly heatmap and weekday bar chart."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    stats = seasonality_stats(data)
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=(
            f'{symbol} average monthly return (%)'.strip(),
            f'{symbol} average weekday return (%)'.strip(),
        ),
        vertical_spacing=0.18,
        row_heights=[0.6, 0.4],
    )

    if stats['monthly']:
        z = stats['monthly']['values']
        fig.add_trace(
            go.Heatmap(
                z=z,
                x=[f'M{m}' for m in stats['monthly']['months']],
                y=[str(y) for y in stats['monthly']['years']],
                colorscale='RdYlGn',
                zmid=0,
                colorbar={'title': '%'},
            ),
            row=1, col=1,
        )

    if stats['weekday']:
        fig.add_trace(
            go.Bar(
                x=stats['weekday']['labels'],
                y=stats['weekday']['values'],
                marker_color='#4A90E2',
            ),
            row=2, col=1,
        )

    fig.update_layout(
        height=640,
        template='plotly_white',
        showlegend=False,
        hovermode='closest',
    )
    fig.update_yaxes(title_text='%', row=2, col=1)
    return fig.to_json()

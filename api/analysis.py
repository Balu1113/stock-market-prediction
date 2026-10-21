import pandas as pd
from rest_framework.exceptions import ValidationError
from utils.ml_models import StockPredictor
from utils.trading_strategy import TradingStrategy
from utils.visualizer import Visualizer


def analyze_dataframe(
    data,
    *,
    model_type,
    train_size,
    prediction_days,
    simulate_trading,
    initial_capital,
):
    if len(data) < 3:
        raise ValidationError('Not enough usable price history for analysis.')

    predictor = StockPredictor(model_type=model_type)
    _, _, y_train, y_test, predictions, future_predictions = predictor.train_and_predict(
        data, train_size=train_size, prediction_days=prediction_days
    )
    metrics = predictor.calculate_metrics(y_test, predictions)

    trading_metrics = {}
    if simulate_trading:
        strategy = TradingStrategy(initial_capital=initial_capital)
        _, trading_metrics = strategy.simulate_trades(data)

    figure = Visualizer().plot_predictions(data, predictions, future_predictions)
    last_date = data.index[-1]
    future_index = pd.bdate_range(
        start=last_date + pd.Timedelta(days=1), periods=prediction_days
    )
    future_dates = [str(date.date()) for date in future_index]

    return {
        'metrics': metrics,
        'trading_metrics': trading_metrics,
        'plot': figure.to_json(),
        'future_predictions': {
            'dates': future_dates,
            'values': future_predictions.tolist(),
        },
    }

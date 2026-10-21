import numpy as np
import pandas as pd
from rest_framework.exceptions import ValidationError
from utils.ml_models import StockPredictor, feature_columns_for
from utils.trading_strategy import TradingStrategy
from utils.visualizer import Visualizer


def walk_forward_backtest(data, *, model_type, folds=3, min_train_fraction=0.5):
    """Expanding-window backtest: train on the past, test on the next chunk."""
    n_rows = len(data)
    if n_rows < 60:
        return None

    initial_train = int(n_rows * min_train_fraction)
    remaining = n_rows - initial_train
    fold_size = remaining // folds
    if initial_train < 30 or fold_size < 5:
        return None

    fold_results = []
    for fold in range(folds):
        train_end = initial_train + fold * fold_size
        test_end = min(n_rows, train_end + fold_size)
        if test_end - train_end < 5:
            break
        window = data.iloc[:test_end]
        predictor = StockPredictor(model_type=model_type)
        try:
            _, _, _, y_test, _, _ = predictor.train_and_predict(
                window, train_size=train_end / test_end, prediction_days=1
            )
        except ValueError:
            break
        metrics = predictor.calculate_metrics(
            y_test, predictor.test_return_predictions
        )
        fold_results.append(metrics)

    if not fold_results:
        return None

    directional = np.array([m['directional_accuracy'] for m in fold_results])
    rmses = np.array([m['rmse'] for m in fold_results])
    baseline_directional = np.array(
        [m['baseline_directional_accuracy'] for m in fold_results]
    )
    return {
        'folds': len(fold_results),
        'rmse_mean': float(np.mean(rmses)),
        'rmse_std': float(np.std(rmses)),
        'directional_accuracy_mean': float(np.mean(directional)),
        'directional_accuracy_std': float(np.std(directional)),
        'baseline_directional_accuracy_mean': float(np.mean(baseline_directional)),
    }


def analyze_dataframe(
    data,
    *,
    model_type,
    train_size,
    prediction_days,
    simulate_trading,
    initial_capital,
):
    if len(data) < 10:
        raise ValidationError('Not enough usable price history for analysis.')

    predictor = StockPredictor(model_type=model_type)
    _, _, y_train, y_test, predictions, future_predictions = predictor.train_and_predict(
        data, train_size=train_size, prediction_days=prediction_days
    )
    metrics = predictor.calculate_metrics(
        y_test, predictor.test_return_predictions
    )
    feature_columns = feature_columns_for(data)
    importances = predictor.feature_importances(feature_columns)

    trading_metrics = {}
    if simulate_trading:
        strategy = TradingStrategy(initial_capital=initial_capital)
        _, trading_metrics = strategy.simulate_with_model(
            data, predictor.test_index, predictor.test_return_predictions
        )

    walk_forward = walk_forward_backtest(data, model_type=model_type)

    figure = Visualizer().plot_predictions(data, predictions, future_predictions)
    last_date = data.index[-1]
    future_index = pd.bdate_range(
        start=last_date + pd.Timedelta(days=1), periods=prediction_days
    )
    future_dates = [str(date.date()) for date in future_index]

    return {
        'model': model_type,
        'metrics': metrics,
        'feature_importance': importances[:10],
        'walk_forward': walk_forward,
        'trading_metrics': trading_metrics,
        'plot': figure.to_json(),
        'future_predictions': {
            'dates': future_dates,
            'values': future_predictions.tolist(),
        },
    }

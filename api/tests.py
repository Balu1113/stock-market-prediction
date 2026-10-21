from datetime import datetime, timedelta
from unittest.mock import patch

import numpy as np
import pandas as pd
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from utils.data_processor import DataProcessor
from utils.ml_models import StockPredictor


class StockPredictorTests(TestCase):
    def setUp(self):
        dates = pd.bdate_range('2024-01-01', periods=160)
        base = (
            np.linspace(100, 160, len(dates))
            + np.sin(np.arange(len(dates)) / 5) * 3
        )
        frame = pd.DataFrame({'Close': base}, index=dates)
        frame.index.name = 'Date'
        self.data = DataProcessor().process_data(
            frame, ['Moving Average', 'RSI', 'MACD']
        )
        self.feature_columns = [c for c in self.data.columns if c != 'Close']

    def test_future_predictions_vary_and_are_finite(self):
        predictor = StockPredictor('Ridge Regression')
        _, _, _, y_test, predictions, future = predictor.train_and_predict(
            self.data, train_size=0.8, prediction_days=7
        )

        self.assertEqual(len(predictions), len(y_test))
        self.assertEqual(len(future), 7)
        self.assertTrue(np.all(np.isfinite(future)))
        self.assertGreater(float(np.ptp(future)), 0.0)

    def test_scaler_is_fit_on_the_training_window_only(self):
        predictor = StockPredictor('Ridge Regression')
        _, _, y_train, _, _, _ = predictor.train_and_predict(
            self.data, train_size=0.5, prediction_days=1
        )

        expected_mean = self.data[self.feature_columns].iloc[:len(y_train)].mean().to_numpy()
        self.assertTrue(np.allclose(predictor.scaler.mean_, expected_mean))

    def test_target_is_the_next_day_log_return(self):
        predictor = StockPredictor('Ridge Regression')
        supervised = predictor._build_supervised(self.data, self.feature_columns)

        closes = self.data['Close'].astype(float)
        expected_last = float(
            np.log(closes.iloc[-1] / closes.iloc[-2])
        )
        self.assertAlmostEqual(
            float(supervised['target'].iloc[-1]), expected_last, places=10
        )
        # The final raw row has no next-day target and must be excluded.
        self.assertEqual(len(supervised), len(self.data) - 1)

    def test_metrics_include_directional_accuracy_and_baseline(self):
        predictor = StockPredictor('Ridge Regression')
        _, _, _, y_test, _, _ = predictor.train_and_predict(
            self.data, train_size=0.7, prediction_days=1
        )
        metrics = predictor.calculate_metrics(
            y_test, predictor.test_return_predictions
        )

        self.assertIn('directional_accuracy', metrics)
        self.assertIn('baseline_rmse', metrics)
        self.assertIn('baseline_directional_accuracy', metrics)
        self.assertGreaterEqual(metrics['directional_accuracy'], 0.0)
        self.assertLessEqual(metrics['directional_accuracy'], 1.0)
        self.assertGreater(metrics['baseline_rmse'], 0.0)


class AdvancedModelTests(TestCase):
    def setUp(self):
        dates = pd.bdate_range('2024-01-01', periods=160)
        rng = np.random.default_rng(3)
        closes = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, len(dates))))
        frame = pd.DataFrame({'Close': closes}, index=dates)
        frame.index.name = 'Date'
        self.data = DataProcessor().process_data(
            frame, ['Moving Average', 'RSI', 'MACD']
        )

    def test_ridge_and_ensemble_train(self):
        for model_type in (
            'Ridge Regression',
            'Ensemble (Auto)',
        ):
            predictor = StockPredictor(model_type)
            _, _, _, y_test, predictions, future = predictor.train_and_predict(
                self.data, train_size=0.75, prediction_days=3
            )

            self.assertEqual(len(predictions), len(y_test), model_type)
            self.assertEqual(len(future), 3, model_type)
            self.assertTrue(np.all(np.isfinite(future)), model_type)

    def test_unsupported_model_lists_valid_options(self):
        predictor = StockPredictor('Prophet')

        with self.assertRaises(ValueError) as context:
            predictor.create_model()

        self.assertIn('LSTM (Colab)', str(context.exception))

    def test_feature_importances_are_ranked_and_normalized(self):
        predictor = StockPredictor('Ensemble (Auto)')
        predictor.train_and_predict(self.data, train_size=0.75, prediction_days=1)
        feature_columns = [c for c in self.data.columns if c != 'Close']
        importances = predictor.feature_importances(feature_columns)

        self.assertTrue(importances)
        values = [item['importance'] for item in importances]
        self.assertEqual(values, sorted(values, reverse=True))
        self.assertAlmostEqual(sum(values), 1.0, places=6)

    def test_new_features_are_engineered_without_lookahead_columns(self):
        feature_columns = [c for c in self.data.columns if c != 'Close']

        for expected in ('MA20', 'MA50', 'RSI', 'MACD', 'Signal', 'LogReturn_10'):
            self.assertIn(expected, feature_columns)

        for dropped in ('ROC_5', 'ZScore_20', 'DayOfWeekSin', 'Returns', 'Volatility'):
            self.assertNotIn(dropped, feature_columns)

    def test_raw_ohlcv_levels_are_excluded_from_features(self):
        from utils.ml_models import feature_columns_for

        dates = pd.bdate_range('2024-01-01', periods=80)
        frame = pd.DataFrame({
            'Open': np.linspace(100, 110, 80),
            'High': np.linspace(101, 111, 80),
            'Low': np.linspace(99, 109, 80),
            'Close': np.linspace(100, 110, 80),
            'Volume': np.linspace(1e6, 2e6, 80),
        }, index=dates)
        frame.index.name = 'Date'
        processed = DataProcessor().process_data(frame, [])
        columns = feature_columns_for(processed)

        for level in ('Open', 'High', 'Low', 'Close', 'Volume'):
            self.assertNotIn(level, columns)
        for expected in (
            'LogReturn_10', 'ATR_14', 'HighLowRange',
            'OvernightReturn', 'VolumeSMA_ratio',
        ):
            self.assertIn(expected, columns)


class WalkForwardBacktestTests(TestCase):
    def test_walk_forward_returns_stable_metric_summary(self):
        from api.analysis import walk_forward_backtest

        dates = pd.bdate_range('2022-01-03', periods=120)
        rng = np.random.default_rng(7)
        closes = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, len(dates))))
        frame = pd.DataFrame({'Close': closes}, index=dates)
        frame.index.name = 'Date'
        data = DataProcessor().process_data(frame, [])

        result = walk_forward_backtest(data, model_type='Ridge Regression', folds=3)

        self.assertIsNotNone(result)
        self.assertEqual(result['folds'], 3)
        self.assertGreaterEqual(result['directional_accuracy_mean'], 0.0)
        self.assertLessEqual(result['directional_accuracy_mean'], 1.0)
        self.assertGreaterEqual(result['directional_accuracy_std'], 0.0)

    def test_walk_forward_skips_too_small_history(self):
        from api.analysis import walk_forward_backtest

        dates = pd.bdate_range('2024-01-01', periods=20)
        frame = pd.DataFrame({'Close': np.linspace(100, 110, 20)}, index=dates)
        frame.index.name = 'Date'
        data = DataProcessor().process_data(frame, [])

        self.assertIsNone(walk_forward_backtest(data, model_type='Ridge Regression'))


class ModelTradingSimulationTests(TestCase):
    def test_simulation_longs_only_on_positive_predictions(self):
        from utils.trading_strategy import TradingStrategy

        dates = pd.bdate_range('2024-01-01', periods=5)
        closes = np.array([100.0, 102.0, 101.0, 105.0, 104.0])
        data = pd.DataFrame({'Close': closes}, index=dates)

        test_index = dates[:4]
        predicted_returns = np.array([0.01, -0.01, 0.02, -0.01])

        _, metrics = TradingStrategy(initial_capital=10000).simulate_with_model(
            data, test_index, predicted_returns
        )

        # Long day 0->1 (+2%), flat 1->2, long 2->3 (+~3.96%), flat 3->4.
        expected_capital = 10000 * 1.02 * (105.0 / 101.0)
        self.assertEqual(metrics['strategy'], 'model')
        self.assertEqual(metrics['total_trades'], 2)
        self.assertEqual(metrics['profitable_trades'], 2)
        self.assertAlmostEqual(metrics['final_capital'], expected_capital, places=6)
        self.assertAlmostEqual(
            metrics['total_pnl'], expected_capital - 10000, places=6
        )
        self.assertEqual(metrics['win_rate'], 100.0)


class DeepModelTests(TestCase):
    def setUp(self):
        dates = pd.bdate_range('2024-01-01', periods=90)
        rng = np.random.default_rng(11)
        closes = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, len(dates))))
        frame = pd.DataFrame({'Close': closes}, index=dates)
        frame.index.name = 'Date'
        self.data = DataProcessor().process_data(frame, [])

    def test_missing_model_files_point_to_colab_instructions(self):
        predictor = StockPredictor('LSTM (Colab)')
        with patch('utils.deep_models.deep_model_available', return_value=False):
            with self.assertRaises(ValueError) as context:
                predictor.train_and_predict(self.data, train_size=0.8, prediction_days=3)

        self.assertIn('colab/train_lstm_nse.py', str(context.exception))

    def test_deep_inference_path_with_mocked_model(self):
        class FakeKeras:
            def predict(self, sequences, verbose=0):
                return np.zeros((len(sequences), 1), dtype=float)

        config = {
            'features': ['LogReturn_10'],
            'lookback': 5,
            'scaler_mean': [0.0],
            'scaler_scale': [1.0],
        }

        with patch('utils.ml_models.load_deep_bundle', return_value=(FakeKeras(), config)):
            predictor = StockPredictor('LSTM (Colab)')
            _, _, y_train, y_test, predictions, future = predictor.train_and_predict(
                self.data, train_size=0.8, prediction_days=3
            )

        self.assertGreater(len(y_train), 0)
        self.assertEqual(len(predictions), len(y_test))
        self.assertEqual(len(future), 3)
        self.assertTrue(np.all(np.isfinite(future)))
        # A zero-return model predicts flat prices at the last close.
        self.assertTrue(np.allclose(predictions, predictor.test_close))

    def test_deep_path_rejects_data_without_required_features(self):
        class FakeKeras:
            def predict(self, sequences, verbose=0):
                return np.zeros((len(sequences), 1), dtype=float)

        config = {
            'features': ['ATR_14'],
            'lookback': 5,
            'scaler_mean': [0.0],
            'scaler_scale': [1.0],
        }

        with patch('utils.ml_models.load_deep_bundle', return_value=(FakeKeras(), config)):
            predictor = StockPredictor('LSTM (Colab)')
            with self.assertRaises(ValueError) as context:
                predictor.train_and_predict(self.data, train_size=0.8, prediction_days=1)

        self.assertIn('ATR_14', str(context.exception))


@override_settings(KITE_API_KEY='test-key', KITE_API_SECRET='test-secret')
class KiteQuoteViewTests(APITestCase):
    def setUp(self):
        session = self.client.session
        session['kite_access_token'] = 'test-access-token'
        session.save()

    def test_quote_returns_a_normalized_live_price(self):
        quote_payload = {
            'NSE:INFY': {
                'last_price': 1500.5,
                'net_change': 10.5,
                'ohlc': {'open': 1490, 'high': 1510, 'low': 1485, 'close': 1490},
                'volume': 1000,
            }
        }

        with patch('api.kite_views._authenticated_client') as get_client:
            get_client.return_value.quote.return_value = quote_payload
            response = self.client.get(
                '/api/kite/quote', {'exchange': 'NSE', 'tradingsymbol': 'INFY'}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['price'], 1500.5)
        self.assertAlmostEqual(response.data['change_percent'], 10.5 / 1490 * 100)


@override_settings(KITE_API_KEY='test-key', KITE_API_SECRET='test-secret')
class KiteAnalyzeViewTests(APITestCase):
    def setUp(self):
        session = self.client.session
        session['kite_access_token'] = 'test-access-token'
        session.save()

    def test_kite_candles_are_normalized_for_existing_analysis(self):
        candles = [
            {
                'date': datetime(2025, 1, 1) + timedelta(days=offset),
                'open': 100 + offset,
                'high': 102 + offset,
                'low': 99 + offset,
                'close': 101 + offset,
                'volume': 1000 + offset,
            }
            for offset in range(30)
        ]
        request_data = {
            'exchange': 'NSE',
            'instrument_token': 12345,
            'tradingsymbol': 'INFY',
            'from_date': '2025-01-01',
            'to_date': '2025-02-01',
            'interval': 'day',
            'model_type': 'Linear Regression',
            'features': [],
            'train_size': 80,
            'prediction_days': 7,
            'simulate_trading': False,
            'initial_capital': 10000,
        }
        analysis_result = {
            'metrics': {'rmse': 0, 'mae': 0, 'r2': 1},
            'trading_metrics': {},
            'plot': '{}',
            'future_predictions': {'dates': [], 'values': []},
        }

        with patch('api.kite_views._authenticated_client') as get_client:
            with patch('api.kite_views.analyze_dataframe', return_value=analysis_result) as analyze:
                get_client.return_value.historical_data.return_value = candles
                response = self.client.post(
                    '/api/predict/kite', request_data, format='json'
                )

        self.assertEqual(response.status_code, 200)
        frame = analyze.call_args.args[0]
        self.assertIn('Close', frame.columns)
        self.assertNotIn('close', frame.columns)
        self.assertEqual(response.data['instrument']['tradingsymbol'], 'INFY')

    def test_status_reports_configuration_without_kite_session(self):
        self.client.session.flush()

        response = self.client.get('/api/kite/status')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['configured'])
        self.assertFalse(response.data['connected'])

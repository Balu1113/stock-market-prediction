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
        predictor = StockPredictor('Linear Regression')
        _, _, _, _, predictions, future = predictor.train_and_predict(
            self.data, train_size=0.8, prediction_days=7
        )

        split = int(round(len(self.data) * 0.8))
        self.assertEqual(len(predictions), len(self.data) - split)
        self.assertEqual(len(future), 7)
        self.assertTrue(np.all(np.isfinite(future)))
        self.assertGreater(float(np.ptp(future)), 0.0)

    def test_scaler_is_fit_on_the_training_window_only(self):
        predictor = StockPredictor('Linear Regression')
        predictor.train_and_predict(self.data, train_size=0.5, prediction_days=1)

        split = int(round(len(self.data) * 0.5))
        expected_mean = self.data[self.feature_columns].iloc[:split].mean().to_numpy()
        self.assertTrue(np.allclose(predictor.scaler.mean_, expected_mean))


@override_settings(ALPHA_VANTAGE_API_KEY='test-key')
class AlphaVantageQuoteViewTests(APITestCase):
    def test_quote_returns_a_normalized_live_price(self):
        payload = {
            'Global Quote': {
                '01. symbol': 'IBM',
                '05. price': '180.50',
                '09. change': '1.25',
                '10. change percent': '0.7000%',
                '08. previous close': '179.25',
            }
        }

        with patch('api.alpha_views.requests.get') as get_data:
            get_data.return_value.json.return_value = payload
            response = self.client.get('/api/alpha-vantage/quote', {'symbol': 'ibm'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['price'], 180.5)
        self.assertAlmostEqual(response.data['change'], 1.25)
        self.assertAlmostEqual(response.data['change_percent'], 0.7)


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

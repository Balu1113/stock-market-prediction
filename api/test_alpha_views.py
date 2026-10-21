from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import override_settings
from rest_framework.test import APITestCase


@override_settings(ALPHA_VANTAGE_API_KEY='test-key')
class AlphaVantageAnalyzeViewTests(APITestCase):
    def test_symbol_search_returns_selectable_provider_matches(self):
        provider_matches = {
            'bestMatches': [
                {
                    '1. symbol': 'RELIANCE.BSE',
                    '2. name': 'Reliance Industries Limited',
                    '4. region': 'India/Bombay',
                    '8. currency': 'INR',
                    '9. matchScore': '0.9000',
                }
            ]
        }

        with patch('api.alpha_views.requests.get') as get_data:
            get_data.return_value.json.return_value = provider_matches
            response = self.client.get(
                '/api/alpha-vantage/symbols',
                {'keywords': 'reliance'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['symbols'], [{
            'symbol': 'RELIANCE.BSE',
            'name': 'Reliance Industries Limited',
            'region': 'India/Bombay',
            'currency': 'INR',
        }])
        self.assertEqual(
            get_data.call_args.kwargs['params']['apikey'],
            'test-key',
        )

    def test_daily_prices_are_normalized_and_sorted_before_analysis(self):
        time_series = {
            (datetime(2025, 1, 1) + timedelta(days=offset)).strftime('%Y-%m-%d'): {
                '1. open': str(100 + offset),
                '2. high': str(102 + offset),
                '3. low': str(99 + offset),
                '4. close': str(101 + offset),
                '5. volume': str(1000 + offset),
            }
            for offset in reversed(range(60))
        }
        result = {
            'metrics': {'rmse': 0, 'mae': 0, 'r2': 1},
            'trading_metrics': {},
            'plot': '{}',
            'future_predictions': {'dates': [], 'values': []},
        }
        response_payload = {'Time Series (Daily)': time_series}

        with patch('api.alpha_views.requests.get') as get_data:
            with patch('api.alpha_views.analyze_dataframe', return_value=result) as analyze:
                get_data.return_value.json.return_value = response_payload
                response = self.client.post(
                    '/api/predict/alpha-vantage',
                    {
                        'symbol': 'ibm',
                        'model_type': 'Linear Regression',
                        'features': [],
                        'train_size': 80,
                        'prediction_days': 7,
                        'simulate_trading': False,
                    },
                    format='json',
                )

        self.assertEqual(response.status_code, 200)
        frame = analyze.call_args.args[0]
        self.assertIn('Close', frame.columns)
        self.assertTrue(frame.index.is_monotonic_increasing)
        self.assertEqual(response.data['instrument']['symbol'], 'IBM')
        self.assertEqual(response.data['instrument']['provider'], 'Alpha Vantage')
        self.assertEqual(
            get_data.call_args.kwargs['params']['function'],
            'TIME_SERIES_DAILY',
        )

    def test_status_reports_missing_key_without_exposing_a_value(self):
        with override_settings(ALPHA_VANTAGE_API_KEY=''):
            response = self.client.get('/api/alpha-vantage/status')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['configured'])
        self.assertNotIn('api_key', response.data)

from unittest.mock import patch

import pandas as pd
from rest_framework.test import APITestCase


def _history(rows=60):
    index = pd.date_range('2025-01-01', periods=rows, freq='B', tz='Asia/Kolkata')
    return pd.DataFrame({
        'Open': [100.0 + offset for offset in range(rows)],
        'High': [102.0 + offset for offset in range(rows)],
        'Low': [99.0 + offset for offset in range(rows)],
        'Close': [101.0 + offset for offset in range(rows)],
        'Volume': [1000 + offset for offset in range(rows)],
        'Dividends': [0.0] * rows,
        'Stock Splits': [0.0] * rows,
    }, index=index)


class YahooStatusViewTests(APITestCase):
    def test_status_reports_available_without_api_key(self):
        response = self.client.get('/api/yahoo/status')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['configured'])
        self.assertFalse(response.data['requires_api_key'])
        self.assertNotIn('api_key', response.data)


class YahooSymbolSearchViewTests(APITestCase):
    def test_search_filters_to_indian_exchange_symbols(self):
        provider_matches = {
            'quotes': [
                {'symbol': 'RELIANCE.NS', 'shortname': 'Reliance Industries Limited', 'exchDisp': 'NSI'},
                {'symbol': 'RELIANCE.BO', 'shortname': 'Reliance Industries Limited', 'exchDisp': 'BSE'},
                {'symbol': 'IBM', 'shortname': 'International Business Machines', 'exchDisp': 'NYQ'},
            ]
        }

        with patch('api.yahoo_views.requests.get') as get_data:
            get_data.return_value.json.return_value = provider_matches
            response = self.client.get('/api/yahoo/symbols', {'keywords': 'reliance'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['symbols'], [
            {
                'symbol': 'RELIANCE.NS',
                'name': 'Reliance Industries Limited',
                'exchange': 'NSE',
                'region': 'India',
                'currency': 'INR',
            },
            {
                'symbol': 'RELIANCE.BO',
                'name': 'Reliance Industries Limited',
                'exchange': 'BSE',
                'region': 'India',
                'currency': 'INR',
            },
        ])
        self.assertEqual(get_data.call_args.kwargs['params']['q'], 'reliance')


class YahooQuoteViewTests(APITestCase):
    def test_quote_normalizes_symbol_and_returns_latest_close(self):
        with patch('api.yahoo_views.yf.Ticker') as ticker_cls:
            ticker_cls.return_value.history.return_value = _history(rows=5)
            response = self.client.get('/api/yahoo/quote', {'symbol': 'reliance'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ticker_cls.call_args.args[0], 'RELIANCE.NS')
        self.assertEqual(response.data['provider'], 'Yahoo Finance')
        self.assertEqual(response.data['symbol'], 'RELIANCE.NS')
        self.assertEqual(response.data['exchange'], 'NSE')
        self.assertEqual(response.data['price'], 105.0)
        self.assertEqual(response.data['previous_close'], 104.0)
        self.assertEqual(response.data['change'], 1.0)
        self.assertAlmostEqual(
            response.data['change_percent'], 1.0 / 104.0 * 100
        )
        self.assertEqual(response.data['currency'], 'INR')
        self.assertTrue(response.data['latest_trading_day'])

    def test_quote_uses_bse_suffix_when_exchange_is_bse(self):
        with patch('api.yahoo_views.yf.Ticker') as ticker_cls:
            ticker_cls.return_value.history.return_value = _history(rows=5)
            response = self.client.get(
                '/api/yahoo/quote', {'symbol': 'TCS', 'exchange': 'BSE'}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ticker_cls.call_args.args[0], 'TCS.BO')
        self.assertEqual(response.data['exchange'], 'BSE')

    def test_quote_rejects_unknown_exchange(self):
        response = self.client.get(
            '/api/yahoo/quote', {'symbol': 'RELIANCE', 'exchange': 'NYSE'}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('NSE or BSE', response.data['error'])


class YahooAnalyzeViewTests(APITestCase):
    def test_daily_prices_are_normalized_and_sorted_before_analysis(self):
        result = {
            'metrics': {'rmse': 0, 'mae': 0, 'r2': 1},
            'trading_metrics': {},
            'plot': '{}',
            'future_predictions': {'dates': [], 'values': []},
        }

        with patch('api.yahoo_views.yf.Ticker') as ticker_cls:
            ticker_cls.return_value.history.return_value = _history().iloc[::-1]
            with patch('api.yahoo_views.analyze_dataframe', return_value=result) as analyze:
                response = self.client.post(
                    '/api/predict/yahoo',
                    {
                        'symbol': 'reliance',
                        'model_type': 'Linear Regression',
                        'features': [],
                        'train_size': 80,
                        'prediction_days': 7,
                        'simulate_trading': False,
                    },
                    format='json',
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ticker_cls.call_args.args[0], 'RELIANCE.NS')
        self.assertEqual(ticker_cls.return_value.history.call_args.kwargs['period'], '5y')
        frame = analyze.call_args.args[0]
        self.assertIn('Close', frame.columns)
        self.assertTrue(frame.index.is_monotonic_increasing)
        self.assertIsNone(frame.index.tz)
        self.assertEqual(response.data['instrument']['symbol'], 'RELIANCE.NS')
        self.assertEqual(response.data['instrument']['provider'], 'Yahoo Finance')
        self.assertEqual(response.data['instrument']['currency'], 'INR')

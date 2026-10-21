"""Tests for competitor-feature modules: patterns, screener, scores, seasonality,
strategies, alerts, portfolio, ranking, auth."""

from unittest.mock import patch

import numpy as np
import pandas as pd
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from utils.data_processor import DataProcessor
from utils.patterns import detect_patterns
from utils.screener import _eval_group, _indicator_features_for
from utils.scores import compute_score
from utils.seasonality import seasonality_stats
from utils.trading_strategy import TradingStrategy, strategy_signals


def make_ohlcv(n=260, seed=42, start='2024-01-01'):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, n)))
    high = close * (1 + rng.uniform(0, 0.01, n))
    low = close * (1 - rng.uniform(0, 0.01, n))
    opn = close * (1 + rng.normal(0, 0.005, n))
    volume = rng.integers(1_000_000, 5_000_000, n).astype(float)
    index = pd.bdate_range(start, periods=n)
    frame = pd.DataFrame(
        {'Open': opn, 'High': high, 'Low': low, 'Close': close, 'Volume': volume},
        index=index,
    )
    frame.index.name = 'Date'
    return frame


class IndicatorTests(TestCase):
    def test_extended_indicators_are_stationary_and_clean(self):
        data = make_ohlcv()
        features = [
            'Moving Average', 'RSI', 'MACD', 'Bollinger Bands', 'Supertrend',
            'Stochastic', 'ADX', 'VWAP', 'OBV',
        ]
        processed = DataProcessor().process_data(data, features)
        self.assertFalse(processed.isna().any(axis=None))
        for column in ('BB_pctb', 'Supertrend_dist', 'Stoch_K', 'ADX', 'Close_VWAP_ratio', 'OBV_change_5'):
            self.assertIn(column, processed.columns)
        self.assertTrue(processed['Stoch_K'].between(0, 100).all())


class PatternTests(TestCase):
    def test_detect_patterns_returns_recent_hits(self):
        patterns = detect_patterns(make_ohlcv())
        self.assertIsInstance(patterns, list)
        for hit in patterns:
            self.assertIn(hit['direction'], ('bullish', 'bearish'))
            self.assertIn('date', hit)

    def test_bullish_engulfing_detected(self):
        frame = pd.DataFrame(
            {
                'Open': [100.0, 101.0, 102.0, 99.0, 100.0],
                'High': [101.0, 102.0, 103.0, 103.0, 101.0],
                'Low': [99.0, 100.0, 101.0, 98.0, 99.0],
                'Close': [100.5, 101.5, 99.5, 102.5, 100.5],
            },
            index=pd.bdate_range('2024-01-01', periods=5),
        )
        patterns = detect_patterns(frame)
        self.assertTrue(any(p['pattern'] == 'Bullish Engulfing' for p in patterns))


class ScoreTests(TestCase):
    def test_score_range_and_components(self):
        processed = DataProcessor().process_data(make_ohlcv(), ['Moving Average', 'RSI'])
        score = compute_score(processed, predicted_return=0.01)
        self.assertTrue(0 <= score['overall'] <= 100)
        self.assertIn(score['rating'], ('Strong', 'Bullish', 'Neutral', 'Bearish', 'Weak'))
        self.assertIn('momentum', score['components'])
        self.assertIn('model', score['components'])

    def test_score_without_prediction(self):
        processed = DataProcessor().process_data(make_ohlcv(), ['RSI'])
        score = compute_score(processed)
        self.assertNotIn('model', score['components'])


class SeasonalityTests(TestCase):
    def test_seasonality_shapes(self):
        stats = seasonality_stats(make_ohlcv(n=400))
        self.assertTrue(stats['monthly']['years'])
        self.assertEqual(len(stats['weekday']['labels']), 5)


class ScreenerTests(TestCase):
    def test_indicator_feature_mapping(self):
        rules = {
            'op': 'AND',
            'conditions': [
                {'condition': {'field': 'RSI', 'op': 'lt', 'value': 30}},
                {'condition': {'field': 'sma20', 'op': 'gt', 'value': 1}},
            ],
        }
        features = _indicator_features_for(rules)
        self.assertIn('RSI', features)
        self.assertIn('Moving Average', features)

    def test_eval_group_and_or(self):
        data = DataProcessor().add_indicators(make_ohlcv(), ['RSI', 'Moving Average'])
        rules = {
            'op': 'AND',
            'conditions': [
                {'condition': {'field': 'close', 'op': 'gt', 'value': 1}},
                {
                    'op': 'OR',
                    'conditions': [
                        {'condition': {'field': 'RSI', 'op': 'gt', 'value': -1}},
                        {'condition': {'field': 'RSI', 'op': 'lt', 'value': 0}},
                    ],
                },
            ],
        }
        mask = _eval_group(data, rules)
        self.assertTrue(bool(mask.iloc[-1]))

    def test_crosses_operator(self):
        data = DataProcessor().add_indicators(make_ohlcv(), ['RSI'])
        rules = {'condition': {'field': 'RSI', 'op': 'crosses_above', 'value': 30}}
        mask = _eval_group(data, rules)
        self.assertEqual(mask.dtype, bool)


class StrategyTests(TestCase):
    def test_all_presets_run(self):
        data = make_ohlcv()
        for strategy in ('cross', 'rsi_reversion', 'supertrend', 'macd_cross'):
            result = TradingStrategy(10000).run_backtest(data, strategy)
            self.assertIn('metrics', result)
            self.assertIn('equity_curve', result)
            self.assertIn('signal_dates', result)

    def test_cross_signals_backward_compatible(self):
        data = make_ohlcv()
        framed = TradingStrategy(10000).calculate_signals(data)
        self.assertIn('Signal', framed.columns)

    def test_strategy_signals_invalid(self):
        with self.assertRaises(ValueError):
            strategy_signals(make_ohlcv(), 'nope')


class ModelDefaultTests(TestCase):
    def test_csv_predict_defaults_to_ridge(self):
        frame = make_ohlcv(n=80)
        csv = frame.reset_index()[['Date', 'Close']].to_csv(index=False)
        from django.core.files.uploadedfile import SimpleUploadedFile
        upload = SimpleUploadedFile('data.csv', csv.encode())
        response = self.client.post(
            reverse('predict'),
            {'file': upload, 'train_size': 70, 'prediction_days': 2},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['model'], 'Ridge Regression')


class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_login_me_logout(self):
        response = self.client.post(
            reverse('auth-register'), {'username': 'trader', 'password': 'secret123'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['authenticated'])

        self.client.logout()
        response = self.client.post(
            reverse('auth-login'), {'username': 'trader', 'password': 'secret123'}
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('auth-me'))
        self.assertTrue(response.json()['authenticated'])

        self.client.post(reverse('auth-logout'))
        response = self.client.get(reverse('auth-me'))
        self.assertFalse(response.json()['authenticated'])

    def test_login_rejects_bad_password(self):
        User.objects.create_user(username='x', password='correct-horse')
        response = self.client.post(
            reverse('auth-login'), {'username': 'x', 'password': 'wrong'}
        )
        self.assertEqual(response.status_code, 401)


class AlertApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_crud_and_check(self):
        response = self.client.post(
            reverse('alerts'),
            {'symbol': 'RELIANCE', 'condition_type': 'price_above', 'threshold': 100},
        )
        self.assertEqual(response.status_code, 200)
        alert_id = response.json()['id']

        response = self.client.get(reverse('alerts'))
        self.assertEqual(len(response.json()['alerts']), 1)

        fake = make_ohlcv(n=40)
        with patch('api.alerts_views.fetch_daily_history', return_value=fake):
            response = self.client.post(reverse('alerts-check'))
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIn('triggered', payload)
            # Synthetic prices are ~100+, threshold 100 -> should trigger.
            self.assertTrue(
                any(item['symbol'] == 'RELIANCE.NS' for item in payload['triggered'])
            )

        response = self.client.delete(reverse('alerts'), {'id': alert_id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(reverse('alerts')).json()['alerts'], [])

    def test_alert_requires_threshold(self):
        response = self.client.post(
            reverse('alerts'), {'symbol': 'TCS', 'condition_type': 'price_above'}
        )
        self.assertEqual(response.status_code, 400)


class PortfolioApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_holdings_crud_and_summary(self):
        response = self.client.post(
            reverse('portfolio-holdings'),
            {'symbol': 'INFY', 'quantity': 10, 'average_price': 1500},
        )
        self.assertEqual(response.status_code, 200)
        holding_id = response.json()['id']

        fake = make_ohlcv(n=30)
        with patch('api.portfolio_views.fetch_daily_history', return_value=fake):
            response = self.client.get(reverse('portfolio-summary'))
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload['summary']['positions'], 1)
            self.assertIsNotNone(payload['holdings'][0]['current_price'])

        response = self.client.delete(reverse('portfolio-holdings'), {'id': holding_id})
        self.assertEqual(response.status_code, 200)


class ScreenerApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_scan_with_mocked_history(self):
        fake = make_ohlcv(n=120)
        with patch('utils.screener.fetch_daily_history', return_value=fake):
            response = self.client.post(
                reverse('screener-scan'),
                {
                    'rules': {
                        'op': 'AND',
                        'conditions': [
                            {'condition': {'field': 'close', 'op': 'gt', 'value': 1}},
                        ],
                    },
                    'symbols': ['RELIANCE.NS'],
                },
                format='json',
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)

    def test_saved_scans_crud(self):
        response = self.client.post(
            reverse('screener-scans'),
            {'name': 'Oversold', 'rules': {'condition': {'field': 'RSI', 'op': 'lt', 'value': 30}}},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        scan_id = response.json()['id']
        self.assertEqual(len(self.client.get(reverse('screener-scans')).json()['scans']), 1)
        self.client.delete(reverse('screener-scans'), {'id': scan_id})
        self.assertEqual(self.client.get(reverse('screener-scans')).json()['scans'], [])

    def test_backtest_with_mocked_history(self):
        fake = make_ohlcv(n=160)
        with patch('utils.screener.fetch_daily_history', return_value=fake):
            response = self.client.post(
                reverse('screener-backtest'),
                {
                    'rules': {'condition': {'field': 'close', 'op': 'gt', 'value': 1}},
                    'symbol': 'RELIANCE',
                    'months': 6,
                },
                format='json',
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn('overall_hit_rate', response.json())


class RankingApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_rank_uses_rank_symbols(self):
        fake_rows = [
            {
                'symbol': 'RELIANCE.NS', 'label': 'RELIANCE', 'sector': 'Diversified',
                'price': 100.0, 'predicted_return_pct': 0.5, 'score': 66.0,
                'rating': 'Bullish', 'score_summary': 'ok', 'return_1m_pct': 3.0,
                'patterns': [],
            }
        ]
        with patch('api.ranking_views.rank_symbols', return_value=fake_rows):
            response = self.client.post(
                reverse('rank'), {'symbols': ['RELIANCE'], 'limit': 5}, format='json'
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)


class MarketBreadthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_breadth_with_mocked_history(self):
        fake = make_ohlcv(n=30)
        with patch('api.market_views.fetch_daily_history', return_value=fake):
            response = self.client.get(reverse('market-breadth'))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('advancers', payload)
        self.assertIn('sectors', payload)


class SeasonalityApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_seasonality_endpoint(self):
        fake = make_ohlcv(n=300)
        with patch('api.seasonality_views.fetch_daily_history', return_value=fake):
            response = self.client.get(reverse('yahoo-seasonality'), {'symbol': 'INFY'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('plot', response.json())


class BacktestApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_backtest_endpoint(self):
        fake = make_ohlcv(n=200)
        with patch('api.strategy_views.fetch_daily_history', return_value=fake):
            response = self.client.post(
                reverse('backtest'),
                {'symbol': 'INFY', 'strategy': 'cross', 'initial_capital': 5000},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('plot', payload)
        self.assertIn('trades', payload)
        self.assertEqual(payload['strategy'], 'cross')

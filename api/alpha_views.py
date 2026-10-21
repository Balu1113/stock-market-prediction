import re

import pandas as pd
import requests
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .analysis import analyze_dataframe
from utils.data_processor import DataProcessor


ALPHA_VANTAGE_URL = 'https://www.alphavantage.co/query'
SYMBOL_PATTERN = re.compile(r'^[A-Z0-9.^_-]{1,30}$')


class AlphaVantageStatusView(APIView):
    def get(self, request):
        return Response({'configured': bool(settings.ALPHA_VANTAGE_API_KEY)})


class AlphaVantageQuoteView(APIView):
    def get(self, request):
        if not settings.ALPHA_VANTAGE_API_KEY:
            return Response(
                {'error': 'Add ALPHA_VANTAGE_API_KEY to the backend .env file and restart Django.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        symbol = str(request.query_params.get('symbol', '')).strip().upper()
        if not SYMBOL_PATTERN.fullmatch(symbol):
            return Response(
                {'error': 'Enter a valid Alpha Vantage symbol, such as IBM or RELIANCE.BSE.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            response = requests.get(
                ALPHA_VANTAGE_URL,
                params={
                    'function': 'GLOBAL_QUOTE',
                    'symbol': symbol,
                    'apikey': settings.ALPHA_VANTAGE_API_KEY,
                },
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            message = payload.get('Error Message') or payload.get('Note') or payload.get('Information')
            if message:
                raise ValueError(str(message))

            quote = payload.get('Global Quote') or {}
            price = quote.get('05. price')
            if price in (None, ''):
                raise ValueError('Alpha Vantage returned no live quote for that symbol.')

            def number(value):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None

            return Response({
                'provider': 'Alpha Vantage',
                'symbol': symbol,
                'price': number(price),
                'change': number(quote.get('09. change')),
                'change_percent': number(str(quote.get('10. change percent', '')).rstrip('%')),
                'previous_close': number(quote.get('08. previous close')),
                'open': number(quote.get('02. open')),
                'high': number(quote.get('03. high')),
                'low': number(quote.get('04. low')),
                'volume': number(quote.get('06. volume')),
                'latest_trading_day': quote.get('07. latest trading day', ''),
            })
        except requests.RequestException:
            return Response(
                {'error': 'Could not reach Alpha Vantage. Check your connection and try again.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as error:
            return Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)


class AlphaVantageSymbolSearchView(APIView):
    def get(self, request):
        if not settings.ALPHA_VANTAGE_API_KEY:
            return Response(
                {'error': 'Add ALPHA_VANTAGE_API_KEY to the backend .env file and restart Django.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        keywords = str(request.query_params.get('keywords', '')).strip()
        if len(keywords) < 2 or len(keywords) > 80:
            return Response(
                {'error': 'Enter between 2 and 80 characters to search symbols.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            response = requests.get(
                ALPHA_VANTAGE_URL,
                params={
                    'function': 'SYMBOL_SEARCH',
                    'keywords': keywords,
                    'apikey': settings.ALPHA_VANTAGE_API_KEY,
                },
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            message = payload.get('Error Message') or payload.get('Note') or payload.get('Information')
            if message:
                raise ValueError(str(message))

            matches = [
                {
                    'symbol': item.get('1. symbol', ''),
                    'name': item.get('2. name', ''),
                    'region': item.get('4. region', ''),
                    'currency': item.get('8. currency', ''),
                }
                for item in payload.get('bestMatches', [])
                if item.get('1. symbol')
            ]
            return Response({'symbols': matches})
        except requests.RequestException:
            return Response(
                {'error': 'Could not reach Alpha Vantage. Check your connection and try again.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as error:
            return Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)


class AlphaVantageAnalyzeView(APIView):
    def post(self, request):
        if not settings.ALPHA_VANTAGE_API_KEY:
            return Response(
                {'error': 'Add ALPHA_VANTAGE_API_KEY to the backend .env file and restart Django.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        symbol = str(request.data.get('symbol', '')).strip().upper()
        if not SYMBOL_PATTERN.fullmatch(symbol):
            return Response(
                {'error': 'Enter a valid Alpha Vantage symbol, such as IBM or RELIANCE.BSE.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            train_percent = int(request.data.get('train_size', 80))
            prediction_days = int(request.data.get('prediction_days', 7))
            features = request.data.get('features', [])
            simulate_trading = request.data.get('simulate_trading') is True
            initial_capital = float(request.data.get('initial_capital', 10000))

            if not 1 <= train_percent <= 99:
                raise ValueError('Training size must be between 1 and 99 percent.')
            if not 1 <= prediction_days <= 30:
                raise ValueError('Prediction days must be between 1 and 30.')
            if not isinstance(features, list) or not set(features).issubset(
                {'Moving Average', 'RSI', 'MACD'}
            ):
                raise ValueError('One or more selected indicators are invalid.')
            if initial_capital <= 0:
                raise ValueError('Initial capital must be greater than zero.')

            response = requests.get(
                ALPHA_VANTAGE_URL,
                params={
                    'function': 'TIME_SERIES_DAILY',
                    'symbol': symbol,
                    'outputsize': 'compact',
                    'apikey': settings.ALPHA_VANTAGE_API_KEY,
                },
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()

            message = payload.get('Error Message') or payload.get('Note') or payload.get('Information')
            if message:
                raise ValueError(str(message))

            time_series = payload.get('Time Series (Daily)')
            if not time_series:
                raise ValueError('Alpha Vantage returned no daily prices for that symbol.')

            data = pd.DataFrame.from_dict(time_series, orient='index')
            data.index = pd.to_datetime(data.index)
            data.index.name = 'Date'
            data.rename(columns={
                '1. open': 'Open',
                '2. high': 'High',
                '3. low': 'Low',
                '4. close': 'Close',
                '5. volume': 'Volume',
            }, inplace=True)
            data = data.apply(pd.to_numeric, errors='coerce')
            data.sort_index(inplace=True)
            data = DataProcessor().process_data(data, features)

            results = analyze_dataframe(
                data,
                model_type=request.data.get('model_type', 'Linear Regression'),
                train_size=train_percent / 100,
                prediction_days=prediction_days,
                simulate_trading=simulate_trading,
                initial_capital=initial_capital,
            )
            results['instrument'] = {
                'provider': 'Alpha Vantage',
                'symbol': symbol,
                'currency': str(request.data.get('currency', '')).upper(),
            }
            return Response(results)
        except requests.RequestException:
            return Response(
                {'error': 'Could not reach Alpha Vantage. Check your connection and try again.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as error:
            return Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)

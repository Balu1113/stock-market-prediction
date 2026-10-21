import re

import pandas as pd
import requests
import yfinance as yf
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .analysis import analyze_dataframe
from utils.data_processor import DataProcessor


YAHOO_SEARCH_URL = 'https://query2.finance.yahoo.com/v1/finance/search'
SYMBOL_PATTERN = re.compile(r'^[A-Z0-9]{1,15}(\.[A-Z]{2,4})?$')
ALLOWED_EXCHANGES = {'NSE', 'BSE'}
ALLOWED_FEATURES = {
    'Moving Average', 'RSI', 'MACD', 'Bollinger Bands', 'Supertrend',
    'Stochastic', 'ADX', 'VWAP', 'OBV',
}
YAHOO_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}


def _normalize_symbol(symbol, exchange):
    symbol = symbol.strip().upper()
    if symbol.endswith('.NSE'):
        symbol = f'{symbol[:-4]}.NS'
    elif symbol.endswith('.BSE'):
        symbol = f'{symbol[:-4]}.BO'
    if symbol.endswith(('.NS', '.BO')):
        return symbol
    suffix = '.BO' if exchange == 'BSE' else '.NS'
    return f'{symbol}{suffix}'


def _daily_history(ticker, period='1y'):
    data = ticker.history(period=period, auto_adjust=True)
    if data is None or data.empty:
        return None
    if data.index.tz is not None:
        data.index = data.index.tz_localize(None)
    data.index = pd.to_datetime(data.index)
    data.index.name = 'Date'
    columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    data = data[[c for c in columns if c in data.columns]].apply(
        pd.to_numeric, errors='coerce'
    )
    data.sort_index(inplace=True)
    return data


class YahooStatusView(APIView):
    def get(self, request):
        return Response({'configured': True, 'requires_api_key': False})


class YahooQuoteView(APIView):
    def get(self, request):
        raw_symbol = str(request.query_params.get('symbol', '')).strip()
        if not raw_symbol or len(raw_symbol) > 30:
            return Response(
                {'error': 'Enter a stock symbol, such as RELIANCE or INFY.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        exchange = str(request.query_params.get('exchange', 'NSE')).strip().upper()
        if exchange not in ALLOWED_EXCHANGES:
            return Response(
                {'error': 'Exchange must be NSE or BSE.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        symbol = _normalize_symbol(raw_symbol, exchange)
        if not SYMBOL_PATTERN.fullmatch(symbol):
            return Response(
                {'error': 'Enter a valid symbol, such as RELIANCE or TCS.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            data = _daily_history(yf.Ticker(symbol), period='5d')
            if data is None or data.empty:
                raise ValueError(
                    'Yahoo Finance returned no quotes for that symbol. '
                    'Check the symbol and try again.'
                )

            last = data.iloc[-1]
            price = float(last['Close'])
            previous_close = float(data['Close'].iloc[-2]) if len(data) >= 2 else None
            change = (
                price - previous_close if previous_close is not None else None
            )
            change_percent = (
                change / previous_close * 100
                if change is not None and previous_close
                else None
            )

            return Response({
                'provider': 'Yahoo Finance',
                'symbol': symbol,
                'exchange': 'BSE' if symbol.endswith('.BO') else 'NSE',
                'price': price,
                'change': change,
                'change_percent': change_percent,
                'previous_close': previous_close,
                'open': float(last['Open']) if pd.notna(last.get('Open')) else None,
                'high': float(last['High']) if pd.notna(last.get('High')) else None,
                'low': float(last['Low']) if pd.notna(last.get('Low')) else None,
                'volume': int(last['Volume']) if pd.notna(last.get('Volume')) else None,
                'latest_trading_day': data.index[-1].strftime('%Y-%m-%d'),
                'currency': 'INR',
            })
        except ValueError as error:
            return Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {'error': 'Could not fetch quotes from Yahoo Finance. Try again shortly.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class YahooSymbolSearchView(APIView):
    def get(self, request):
        keywords = str(request.query_params.get('keywords', '')).strip()
        if len(keywords) < 2 or len(keywords) > 80:
            return Response(
                {'error': 'Enter between 2 and 80 characters to search symbols.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            response = requests.get(
                YAHOO_SEARCH_URL,
                params={
                    'q': keywords,
                    'quotesCount': 20,
                    'newsCount': 0,
                    'listsCount': 0,
                },
                headers=YAHOO_HEADERS,
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()

            matches = []
            for item in payload.get('quotes', []):
                yahoo_symbol = str(item.get('symbol', '')).upper()
                if not yahoo_symbol.endswith(('.NS', '.BO')):
                    continue
                matches.append({
                    'symbol': yahoo_symbol,
                    'name': item.get('shortname') or item.get('longname') or yahoo_symbol,
                    'exchange': 'BSE' if yahoo_symbol.endswith('.BO') else 'NSE',
                    'region': 'India',
                    'currency': 'INR',
                })
            return Response({'symbols': matches})
        except requests.RequestException:
            return Response(
                {'error': 'Could not reach Yahoo Finance. Check your connection and try again.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as error:
            return Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)


class YahooAnalyzeView(APIView):
    def post(self, request):
        raw_symbol = str(request.data.get('symbol', '')).strip()
        if not raw_symbol or len(raw_symbol) > 30:
            return Response(
                {'error': 'Enter a stock symbol, such as RELIANCE or INFY.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        exchange = str(request.data.get('exchange', 'NSE')).strip().upper()
        if exchange not in ALLOWED_EXCHANGES:
            return Response(
                {'error': 'Exchange must be NSE or BSE.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        symbol = _normalize_symbol(raw_symbol, exchange)
        if not SYMBOL_PATTERN.fullmatch(symbol):
            return Response(
                {'error': 'Enter a valid symbol, such as RELIANCE or TCS.'},
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
            if not isinstance(features, list) or not set(features).issubset(ALLOWED_FEATURES):
                raise ValueError('One or more selected indicators are invalid.')
            if initial_capital <= 0:
                raise ValueError('Initial capital must be greater than zero.')

            data = _daily_history(yf.Ticker(symbol), period='5y')
            if data is None or data.empty:
                raise ValueError(
                    'Yahoo Finance returned no daily prices for that symbol.'
                )

            data = DataProcessor().process_data(data, features)
            results = analyze_dataframe(
                data,
                model_type=request.data.get('model_type', 'Ridge Regression'),
                train_size=train_percent / 100,
                prediction_days=prediction_days,
                simulate_trading=simulate_trading,
                initial_capital=initial_capital,
            )
            results['instrument'] = {
                'provider': 'Yahoo Finance',
                'symbol': symbol,
                'exchange': 'BSE' if symbol.endswith('.BO') else 'NSE',
                'currency': 'INR',
            }
            return Response(results)
        except ValueError as error:
            return Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {'error': 'Could not fetch data from Yahoo Finance. Try again shortly.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

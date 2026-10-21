from datetime import date
from urllib.parse import urlencode

import pandas as pd
from django.conf import settings
from django.http import HttpResponseRedirect
from kiteconnect import KiteConnect
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from utils.data_processor import DataProcessor
from .analysis import analyze_dataframe


ALLOWED_EXCHANGES = {'NSE', 'BSE'}
ALLOWED_INTERVALS = {
    'minute', '3minute', '5minute', '10minute', '15minute',
    '30minute', '60minute', 'day',
}
ALLOWED_FEATURES = {
    'Moving Average', 'RSI', 'MACD', 'Bollinger Bands', 'Supertrend',
    'Stochastic', 'ADX', 'VWAP', 'OBV',
}


def _kite_client(access_token=None):
    if not settings.KITE_API_KEY or not settings.KITE_API_SECRET:
        raise ValueError('Set KITE_API_KEY and KITE_API_SECRET before connecting Kite.')

    client = KiteConnect(api_key=settings.KITE_API_KEY)
    if access_token:
        client.set_access_token(access_token)
    return client


def _authenticated_client(request):
    access_token = request.session.get('kite_access_token')
    if not access_token:
        raise PermissionError('Connect your Kite account first.')
    return _kite_client(access_token)


def _frontend_redirect(request, result):
    origin = request.session.pop(
        'kite_return_to', settings.CORS_ALLOWED_ORIGINS[0]
    )
    query = urlencode({'kite': result})
    return HttpResponseRedirect(f'{origin}/?{query}')


class KiteLoginView(APIView):
    def get(self, request):
        origin = request.query_params.get('return_to', '')
        if origin not in settings.CORS_ALLOWED_ORIGINS:
            return Response(
                {'error': 'Frontend origin is not allowed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            login_url = _kite_client().login_url()
        except ValueError as error:
            return Response({'error': str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        request.session['kite_return_to'] = origin
        request.session.save()
        return HttpResponseRedirect(login_url)


class KiteCallbackView(APIView):
    def get(self, request):
        if request.query_params.get('status') != 'success':
            return _frontend_redirect(request, 'error')

        request_token = request.query_params.get('request_token')
        if not request_token:
            return _frontend_redirect(request, 'error')

        try:
            session_data = _kite_client().generate_session(
                request_token,
                api_secret=settings.KITE_API_SECRET,
            )
        except Exception:
            return _frontend_redirect(request, 'error')

        request.session.cycle_key()
        request.session['kite_access_token'] = session_data['access_token']
        request.session['kite_user_name'] = session_data.get('user_name', '')
        return _frontend_redirect(request, 'connected')


class KiteStatusView(APIView):
    def get(self, request):
        return Response({
            'configured': bool(settings.KITE_API_KEY and settings.KITE_API_SECRET),
            'connected': bool(request.session.get('kite_access_token')),
            'user_name': request.session.get('kite_user_name', ''),
        })


class KiteDisconnectView(APIView):
    def post(self, request):
        request.session.pop('kite_access_token', None)
        request.session.pop('kite_user_name', None)
        return Response({'connected': False})


class KiteInstrumentSearchView(APIView):
    def get(self, request):
        exchange = request.query_params.get('exchange', 'NSE').upper()
        query = request.query_params.get('q', '').strip().upper()
        if exchange not in ALLOWED_EXCHANGES:
            return Response({'error': 'Choose NSE or BSE.'}, status=status.HTTP_400_BAD_REQUEST)
        if not query:
            return Response({'instruments': []})

        try:
            instruments = _authenticated_client(request).instruments(exchange)
        except PermissionError as error:
            return Response({'error': str(error)}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as error:
            return Response({'error': str(error)}, status=status.HTTP_502_BAD_GATEWAY)

        matches = [
            {
                'instrument_token': instrument['instrument_token'],
                'exchange': instrument['exchange'],
                'tradingsymbol': instrument['tradingsymbol'],
                'name': instrument.get('name', ''),
            }
            for instrument in instruments
            if instrument.get('instrument_type') == 'EQ'
            and (
                query in instrument.get('tradingsymbol', '').upper()
                or query in instrument.get('name', '').upper()
            )
        ]
        matches.sort(key=lambda item: (
            item['tradingsymbol'] != query,
            not item['tradingsymbol'].startswith(query),
            item['tradingsymbol'],
        ))
        return Response({'instruments': matches[:25]})


class KiteAnalyzeView(APIView):
    def post(self, request):
        try:
            client = _authenticated_client(request)
            exchange = str(request.data.get('exchange', '')).upper()
            interval = str(request.data.get('interval', 'day'))
            instrument_token = int(request.data.get('instrument_token'))
            from_date = date.fromisoformat(request.data.get('from_date', ''))
            to_date = date.fromisoformat(request.data.get('to_date', ''))
            train_percent = int(request.data.get('train_size', 80))
            prediction_days = int(request.data.get('prediction_days', 7))
            features = request.data.get('features', [])
            simulate_trading = request.data.get('simulate_trading') is True
            initial_capital = float(request.data.get('initial_capital', 10000))

            if exchange not in ALLOWED_EXCHANGES:
                raise ValueError('Choose NSE or BSE.')
            if interval not in ALLOWED_INTERVALS:
                raise ValueError('Choose a supported candle interval.')
            if from_date >= to_date:
                raise ValueError('Start date must be before end date.')
            if not 1 <= train_percent <= 99:
                raise ValueError('Training size must be between 1 and 99 percent.')
            if not 1 <= prediction_days <= 30:
                raise ValueError('Prediction days must be between 1 and 30.')
            if not isinstance(features, list) or not set(features).issubset(ALLOWED_FEATURES):
                raise ValueError('One or more selected indicators are invalid.')
            if initial_capital <= 0:
                raise ValueError('Initial capital must be greater than zero.')

            candles = client.historical_data(
                instrument_token,
                from_date,
                to_date,
                interval,
            )
            if not candles:
                raise ValueError('Kite returned no candles for that symbol and date range.')

            data = pd.DataFrame(candles).rename(
                columns={'date': 'Date', 'close': 'Close'}
            )
            data['Date'] = pd.to_datetime(data['Date'])
            data.set_index('Date', inplace=True)
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
                'exchange': exchange,
                'instrument_token': instrument_token,
                'tradingsymbol': str(request.data.get('tradingsymbol', '')),
                'currency': 'INR',
            }
            return Response(results)
        except PermissionError as error:
            return Response({'error': str(error)}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as error:
            return Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)


class KiteQuoteView(APIView):
    def get(self, request):
        try:
            client = _authenticated_client(request)
            exchange = str(request.query_params.get('exchange', '')).upper()
            tradingsymbol = str(request.query_params.get('tradingsymbol', '')).strip().upper()
            instrument_token = request.query_params.get('instrument_token')

            if exchange not in ALLOWED_EXCHANGES:
                raise ValueError('Choose NSE or BSE.')
            if not tradingsymbol and not instrument_token:
                raise ValueError('Provide a trading symbol or instrument token.')

            identifier = (
                f'{exchange}:{tradingsymbol}'
                if tradingsymbol
                else int(instrument_token)
            )
            quotes = client.quote([identifier])
            quote = next(iter(quotes.values()), None)
            if not quote:
                raise ValueError('Kite returned no quote for that instrument.')

            last_price = quote.get('last_price')
            ohlc = quote.get('ohlc') or {}
            previous_close = ohlc.get('close')
            change = quote.get('net_change')
            if change is None and last_price is not None and previous_close:
                change = last_price - previous_close
            change_percent = None
            if change is not None and previous_close:
                change_percent = (change / previous_close) * 100

            return Response({
                'provider': 'Zerodha Kite',
                'exchange': exchange,
                'tradingsymbol': tradingsymbol,
                'price': last_price,
                'change': change,
                'change_percent': change_percent,
                'previous_close': previous_close,
                'open': ohlc.get('open'),
                'high': ohlc.get('high'),
                'low': ohlc.get('low'),
                'volume': quote.get('volume'),
                'currency': 'INR',
            })
        except PermissionError as error:
            return Response({'error': str(error)}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as error:
            return Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)

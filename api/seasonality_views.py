from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.market_data import fetch_daily_history, normalize_symbol
from utils.seasonality import seasonality_plot, seasonality_stats


class SeasonalityView(APIView):
    def get(self, request):
        raw_symbol = str(request.query_params.get('symbol', '')).strip()
        if not raw_symbol:
            return Response(
                {'error': 'Enter a stock symbol, such as RELIANCE or INFY.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            symbol = normalize_symbol(raw_symbol)
            data = fetch_daily_history(symbol, period='5y')
            if data is None or len(data) < 60:
                raise ValueError('Not enough price history to compute seasonality.')
            return Response({
                'symbol': symbol,
                'stats': seasonality_stats(data),
                'plot': seasonality_plot(data, symbol=symbol),
            })
        except ValueError as error:
            return Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {'error': 'Could not compute seasonality. Try again shortly.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

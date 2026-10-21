from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.market_data import fetch_daily_history, normalize_symbol
from utils.trading_strategy import STRATEGY_PRESETS, TradingStrategy
from utils.visualizer import Visualizer


class BacktestView(APIView):
    """Rule-strategy backtest with buy/sell markers, trade log, equity curve."""

    def post(self, request):
        try:
            strategy = str(request.data.get('strategy', 'cross'))
            if strategy not in STRATEGY_PRESETS or strategy == 'model':
                raise ValueError(
                    f'Strategy must be one of: {", ".join(s for s in STRATEGY_PRESETS if s != "model")}.'
                )
            symbol = normalize_symbol(str(request.data.get('symbol', '')))
            initial_capital = float(request.data.get('initial_capital', 10000))
            if initial_capital <= 0:
                raise ValueError('Initial capital must be greater than zero.')
            params = request.data.get('params') or {}
            if not isinstance(params, dict):
                raise ValueError('Params must be an object.')

            period = str(request.data.get('period', '2y'))
            if period not in ('1y', '2y', '5y'):
                raise ValueError('Period must be one of: 1y, 2y, 5y.')

            data = fetch_daily_history(symbol, period=period)
            if data is None or len(data) < 60:
                raise ValueError('Not enough price history for that symbol.')

            runner = TradingStrategy(initial_capital=initial_capital)
            result = runner.run_backtest(data, strategy, params)
            result['instrument'] = {'symbol': symbol, 'currency': 'INR'}
            result['plot'] = Visualizer().plot_backtest(data, result).to_json()
            return Response(result)
        except ValueError as error:
            return Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {'error': 'Could not run the backtest. Try again shortly.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

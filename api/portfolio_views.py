from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.market_data import fetch_daily_history, normalize_symbol
from utils.universe import NIFTY_ETF, symbol_label
from .models import Holding


def _serialize(holding):
    return {
        'id': holding.id,
        'symbol': holding.symbol,
        'label': symbol_label(holding.symbol),
        'quantity': holding.quantity,
        'average_price': holding.average_price,
        'created_at': holding.created_at.isoformat(),
    }


class HoldingView(APIView):
    def get(self, request):
        return Response({'holdings': [_serialize(h) for h in Holding.objects.all()]})

    def post(self, request):
        try:
            symbol = normalize_symbol(str(request.data.get('symbol', '')))
            quantity = float(request.data.get('quantity', 0))
            average_price = float(request.data.get('average_price', 0))
            if quantity <= 0:
                raise ValueError('Quantity must be greater than zero.')
            if average_price <= 0:
                raise ValueError('Average price must be greater than zero.')
            holding, _ = Holding.objects.update_or_create(
                symbol=symbol,
                defaults={'quantity': quantity, 'average_price': average_price},
            )
            return Response(_serialize(holding))
        except (TypeError, ValueError) as error:
            return Response(
                {'error': str(error) or 'Provide quantity and average price.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def delete(self, request):
        holding_id = request.data.get('id') or request.query_params.get('id')
        try:
            Holding.objects.filter(id=int(holding_id)).delete()
        except (TypeError, ValueError):
            return Response(
                {'error': 'Provide a valid holding id.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({'deleted': True})


class PortfolioSummaryView(APIView):
    def get(self, request):
        holdings = list(Holding.objects.all())
        rows = []
        total_value = 0.0
        total_cost = 0.0

        for holding in holdings:
            data = fetch_daily_history(holding.symbol, period='1y')
            price = float(data['Close'].iloc[-1]) if data is not None and len(data) else None
            value = price * holding.quantity if price is not None else None
            cost = holding.average_price * holding.quantity
            pnl = (value - cost) if value is not None else None
            if value is not None:
                total_value += value
            total_cost += cost
            rows.append({
                **_serialize(holding),
                'current_price': price,
                'value': round(value, 2) if value is not None else None,
                'cost': round(cost, 2),
                'pnl': round(pnl, 2) if pnl is not None else None,
                'pnl_pct': round(pnl / cost * 100, 2) if pnl is not None and cost else None,
            })

        allocation = []
        for row in rows:
            allocation.append({
                'symbol': row['symbol'],
                'label': row['label'],
                'weight': round(row['value'] / total_value * 100, 2)
                if row['value'] is not None and total_value else None,
            })

        benchmark = None
        if holdings:
            try:
                index = fetch_daily_history(NIFTY_ETF, period='1y')
                if index is not None and len(index) >= 2:
                    closes = index['Close'].astype(float)
                    benchmark = {
                        'symbol': NIFTY_ETF,
                        'return_1m_pct': round((closes.iloc[-1] / closes.iloc[-min(len(closes), 22)] - 1) * 100, 2),
                        'return_3m_pct': round((closes.iloc[-1] / closes.iloc[-min(len(closes), 63)] - 1) * 100, 2),
                        'return_1y_pct': round((closes.iloc[-1] / closes.iloc[0] - 1) * 100, 2),
                    }
            except Exception:
                benchmark = None

        portfolio_return = (
            round((total_value / total_cost - 1) * 100, 2) if total_cost and total_value else None
        )
        return Response({
            'holdings': rows,
            'summary': {
                'total_value': round(total_value, 2),
                'total_cost': round(total_cost, 2),
                'total_pnl': round(total_value - total_cost, 2),
                'total_pnl_pct': portfolio_return,
                'positions': len(rows),
            },
            'allocation': allocation,
            'benchmark': benchmark,
        })

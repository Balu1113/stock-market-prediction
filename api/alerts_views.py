import pandas as pd
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.data_processor import DataProcessor
from utils.market_data import fetch_daily_history, normalize_symbol
from .models import Alert, AlertEvent


def _serialize_alert(alert):
    return {
        'id': alert.id,
        'symbol': alert.symbol,
        'condition_type': alert.condition_type,
        'threshold': alert.threshold,
        'is_active': alert.is_active,
        'created_at': alert.created_at.isoformat(),
        'last_triggered_at': (
            alert.last_triggered_at.isoformat() if alert.last_triggered_at else None
        ),
    }


class AlertView(APIView):
    def get(self, request):
        return Response({'alerts': [_serialize_alert(a) for a in Alert.objects.all()]})

    def post(self, request):
        symbol = normalize_symbol(str(request.data.get('symbol', '')))
        condition_type = str(request.data.get('condition_type', ''))
        valid = {choice[0] for choice in Alert.CONDITION_TYPES}
        if condition_type not in valid:
            return Response(
                {'error': f'Condition must be one of: {", ".join(sorted(valid))}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        threshold = request.data.get('threshold')
        needs_threshold = condition_type not in ('ma_cross_up', 'ma_cross_down')
        if needs_threshold and threshold is None:
            return Response(
                {'error': 'This alert needs a threshold value.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            threshold = float(threshold) if threshold is not None else None
        except (TypeError, ValueError):
            return Response(
                {'error': 'Threshold must be a number.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        alert = Alert.objects.create(
            symbol=symbol, condition_type=condition_type, threshold=threshold
        )
        return Response(_serialize_alert(alert))

    def delete(self, request):
        alert_id = request.data.get('id') or request.query_params.get('id')
        try:
            Alert.objects.filter(id=int(alert_id)).delete()
        except (TypeError, ValueError):
            return Response(
                {'error': 'Provide a valid alert id.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({'deleted': True})


class AlertCheckView(APIView):
    """Evaluate active alerts against fresh market data."""

    def post(self, request):
        triggered = []
        errors = []
        alerts = Alert.objects.filter(is_active=True)
        by_symbol = {}
        for alert in alerts:
            by_symbol.setdefault(alert.symbol, []).append(alert)

        for symbol, symbol_alerts in by_symbol.items():
            try:
                data = fetch_daily_history(symbol, period='3mo')
                if data is None or len(data) < 20:
                    errors.append(symbol)
                    continue
                prepared = DataProcessor().add_indicators(data, ['Moving Average', 'RSI'])
                last = prepared.iloc[-1]
                price = float(last['Close'])
                rsi = float(last['RSI']) if pd.notna(last.get('RSI')) else None

                for alert in symbol_alerts:
                    hit = False
                    message = ''
                    threshold = alert.threshold
                    if alert.condition_type == 'price_above' and threshold is not None:
                        hit = price > threshold
                        message = f'{symbol} price {price:.2f} crossed above {threshold:.2f}'
                    elif alert.condition_type == 'price_below' and threshold is not None:
                        hit = price < threshold
                        message = f'{symbol} price {price:.2f} crossed below {threshold:.2f}'
                    elif alert.condition_type == 'rsi_above' and threshold is not None and rsi is not None:
                        hit = rsi > threshold
                        message = f'{symbol} RSI {rsi:.1f} is above {threshold:.1f}'
                    elif alert.condition_type == 'rsi_below' and threshold is not None and rsi is not None:
                        hit = rsi < threshold
                        message = f'{symbol} RSI {rsi:.1f} is below {threshold:.1f}'
                    elif alert.condition_type in ('ma_cross_up', 'ma_cross_down'):
                        ma20 = prepared['MA20']
                        ma50 = prepared['MA50']
                        above = ma20 > ma50
                        if alert.condition_type == 'ma_cross_up':
                            hit = bool(above.iloc[-1] and not bool(above.iloc[-2]))
                            message = f'{symbol} MA20 crossed above MA50'
                        else:
                            hit = bool((~above).iloc[-1] and bool(above.iloc[-2]))
                            message = f'{symbol} MA20 crossed below MA50'
                    elif alert.condition_type == 'volume_spike' and threshold is not None:
                        ratio = float(last['VolumeSMA_ratio']) if 'VolumeSMA_ratio' in prepared.columns else None
                        if ratio is None:
                            volume = pd.to_numeric(prepared['Volume'], errors='coerce')
                            ratio = float(volume.iloc[-1] / volume.rolling(20).mean().iloc[-1])
                        hit = ratio >= threshold
                        message = f'{symbol} volume is {ratio:.2f}x its 20-day average'

                    if hit:
                        alert.last_triggered_at = timezone.now()
                        alert.save(update_fields=['last_triggered_at'])
                        event = AlertEvent.objects.create(
                            alert=alert, price=price, message=message
                        )
                        triggered.append({
                            'id': event.id,
                            'symbol': alert.symbol,
                            'condition_type': alert.condition_type,
                            'message': message,
                            'price': price,
                            'triggered_at': event.triggered_at.isoformat(),
                        })
            except Exception:
                errors.append(symbol)

        return Response({'triggered': triggered, 'failed_symbols': errors})


class AlertEventView(APIView):
    def get(self, request):
        limit = min(int(request.query_params.get('limit', 50)), 200)
        events = AlertEvent.objects.all()[:limit]
        return Response({'events': [
            {
                'id': event.id,
                'symbol': event.alert.symbol,
                'condition_type': event.alert.condition_type,
                'message': event.message,
                'price': event.price,
                'triggered_at': event.triggered_at.isoformat(),
            }
            for event in events
        ]})

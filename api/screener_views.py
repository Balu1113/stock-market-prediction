from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.screener import backtest_rules, scan_universe
from .models import SavedScan


class ScreenerScanView(APIView):
    def post(self, request):
        try:
            rules = request.data.get('rules')
            if not isinstance(rules, dict) or not rules:
                raise ValueError('Provide a rules object.')
            symbols = request.data.get('symbols')
            if symbols is not None and (
                not isinstance(symbols, list) or len(symbols) > 40
            ):
                raise ValueError('Provide at most 40 symbols.')
            matches = scan_universe(rules, symbols=symbols)
            return Response({'count': len(matches), 'matches': matches})
        except ValueError as error:
            return Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {'error': 'Could not run the scan. Try again shortly.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class ScreenerBacktestView(APIView):
    def post(self, request):
        try:
            rules = request.data.get('rules')
            if not isinstance(rules, dict) or not rules:
                raise ValueError('Provide a rules object.')
            symbol = str(request.data.get('symbol', '')).strip().upper()
            if not symbol:
                raise ValueError('Provide a symbol to backtest.')
            months = int(request.data.get('months', 12))
            if not 3 <= months <= 24:
                raise ValueError('Months must be between 3 and 24.')
            forward_days = int(request.data.get('forward_days', 5))
            if not 1 <= forward_days <= 20:
                raise ValueError('Forward days must be between 1 and 20.')
            result = backtest_rules(rules, symbol, months=months, forward_days=forward_days)
            return Response(result)
        except ValueError as error:
            return Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {'error': 'Could not backtest the scan. Try again shortly.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class SavedScanView(APIView):
    def get(self, request):
        scans = [
            {'id': scan.id, 'name': scan.name, 'rules': scan.rules,
             'created_at': scan.created_at.isoformat()}
            for scan in SavedScan.objects.all()
        ]
        return Response({'scans': scans})

    def post(self, request):
        name = str(request.data.get('name', '')).strip()
        rules = request.data.get('rules')
        if not name or len(name) > 120:
            return Response(
                {'error': 'Provide a scan name (max 120 characters).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(rules, dict) or not rules:
            return Response(
                {'error': 'Provide a rules object.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        scan = SavedScan.objects.create(name=name, rules=rules)
        return Response({'id': scan.id, 'name': scan.name, 'rules': scan.rules})

    def delete(self, request):
        scan_id = request.data.get('id') or request.query_params.get('id')
        try:
            SavedScan.objects.filter(id=int(scan_id)).delete()
        except (TypeError, ValueError):
            return Response(
                {'error': 'Provide a valid scan id.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({'deleted': True})

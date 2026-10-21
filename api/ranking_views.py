from datetime import datetime, timezone

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.cache import scan_cache
from utils.market_data import normalize_symbol
from utils.ranking import rank_symbols
from utils.universe import NIFTY50


class RankView(APIView):
    """Batch ranking of NSE symbols by predicted return + composite score."""

    def post(self, request):
        try:
            raw_symbols = request.data.get('symbols')
            if raw_symbols is not None:
                if not isinstance(raw_symbols, list) or not raw_symbols:
                    raise ValueError('Symbols must be a non-empty list.')
                if len(raw_symbols) > 40:
                    raise ValueError('Rank at most 40 symbols per request.')
                symbols = [normalize_symbol(str(s)) for s in raw_symbols]
            else:
                symbols = list(NIFTY50)

            limit = int(request.data.get('limit', 15))
            if not 1 <= limit <= 50:
                raise ValueError('Limit must be between 1 and 50.')

            cache_key = f'rank:{",".join(symbols)}:{limit}'
            results = scan_cache.get(cache_key)
            if results is None:
                results = rank_symbols(symbols, limit=limit)
                scan_cache.set(cache_key, results)

            return Response({
                'count': len(results),
                'ranked_at': datetime.now(timezone.utc).isoformat(),
                'results': results,
            })
        except ValueError as error:
            return Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {'error': 'Could not rank symbols. Try again shortly.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

import numpy as np
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.cache import scan_cache
from utils.market_data import fetch_daily_history
from utils.universe import NIFTY50, NIFTY_ETF, SECTOR_MAP, symbol_label


class MarketBreadthView(APIView):
    """Advance/decline, new highs/lows, sector split across the Nifty 50."""

    def get(self, request):
        cached = scan_cache.get('breadth')
        if cached is not None:
            return Response(cached)

        advancers, decliners, unchanged = [], [], []
        highs, lows = [], []
        sector_moves = {}
        failed = 0

        for symbol in NIFTY50:
            try:
                data = fetch_daily_history(symbol, period='1y')
                if data is None or len(data) < 2:
                    failed += 1
                    continue
                close = data['Close'].astype(float)
                last = float(close.iloc[-1])
                prev = float(close.iloc[-2])
                change_pct = (last / prev - 1.0) * 100
                row = {
                    'symbol': symbol,
                    'label': symbol_label(symbol),
                    'price': last,
                    'change_pct': round(change_pct, 2),
                    'sector': SECTOR_MAP.get(symbol, ''),
                }
                if change_pct > 0.05:
                    advancers.append(row)
                elif change_pct < -0.05:
                    decliners.append(row)
                else:
                    unchanged.append(row)

                year = close.iloc[-min(len(close), 252):]
                if last >= float(year.max()) * 0.999:
                    highs.append(row)
                if last <= float(year.min()) * 1.001:
                    lows.append(row)

                sector = SECTOR_MAP.get(symbol)
                if sector:
                    sector_moves.setdefault(sector, []).append(change_pct)
            except Exception:
                failed += 1

        sectors = [
            {
                'sector': sector,
                'avg_change_pct': round(float(np.mean(values)), 2),
                'constituents': len(values),
            }
            for sector, values in sorted(sector_moves.items())
        ]
        sectors.sort(key=lambda item: item['avg_change_pct'], reverse=True)

        index_data = fetch_daily_history(NIFTY_ETF, period='5d')
        index_quote = None
        if index_data is not None and len(index_data) >= 2:
            last = float(index_data['Close'].iloc[-1])
            prev = float(index_data['Close'].iloc[-2])
            index_quote = {
                'symbol': NIFTY_ETF,
                'value': last,
                'change_pct': round((last / prev - 1.0) * 100, 2),
            }

        key = lambda row: row['change_pct']  # noqa: E731
        payload = {
            'index': index_quote,
            'advancers': len(advancers),
            'decliners': len(decliners),
            'unchanged': len(unchanged),
            'top_gainers': sorted(advancers, key=key, reverse=True)[:5],
            'top_losers': sorted(decliners, key=key)[:5],
            'new_highs': highs,
            'new_lows': lows,
            'sectors': sectors,
            'failed_symbols': failed,
        }
        scan_cache.set('breadth', payload)
        return Response(payload)

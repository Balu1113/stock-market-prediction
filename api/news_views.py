import yfinance as yf
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.market_data import normalize_symbol
from utils.sentiment import label_for, score_text


def _headline_text(item) -> str:
    if isinstance(item, dict):
        content = item.get('content') if isinstance(item.get('content'), dict) else item
    else:
        return str(item)
    title = content.get('title') or ''
    summary = content.get('summary') or content.get('description') or ''
    return f'{title}. {summary}'.strip('. ')


class YahooNewsView(APIView):
    def get(self, request):
        raw_symbol = str(request.query_params.get('symbol', '')).strip()
        if not raw_symbol:
            return Response(
                {'error': 'Enter a stock symbol, such as RELIANCE or INFY.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            symbol = normalize_symbol(raw_symbol)
            raw_news = yf.Ticker(symbol).get_news(count=15) or []
            items = []
            for entry in raw_news:
                content = entry.get('content') if isinstance(entry, dict) else None
                if not isinstance(content, dict):
                    content = entry if isinstance(entry, dict) else {}
                title = content.get('title') or ''
                if not title:
                    continue
                summary = content.get('summary') or content.get('description') or ''
                link = ''
                if isinstance(content.get('canonicalUrl'), dict):
                    link = content['canonicalUrl'].get('url', '')
                elif isinstance(content.get('clickThroughUrl'), dict):
                    link = content['clickThroughUrl'].get('url', '')
                published = ''
                if isinstance(content.get('providerPublishTime'), dict):
                    published = content['providerPublishTime'].get('fmt', '')
                elif isinstance(content.get('pubDate'), dict):
                    published = content['pubDate'].get('fmt', '')
                score = score_text(f'{title}. {summary}')
                items.append({
                    'title': title,
                    'summary': summary[:400],
                    'link': link,
                    'published': published,
                    'sentiment': round(score, 3),
                    'sentiment_label': label_for(score),
                })

            scores = [item['sentiment'] for item in items]
            aggregate = round(sum(scores) / len(scores), 3) if scores else 0.0
            return Response({
                'symbol': symbol,
                'news': items,
                'sentiment': {
                    'aggregate': aggregate,
                    'label': label_for(aggregate),
                    'articles': len(items),
                },
            })
        except Exception:
            return Response(
                {'error': 'Could not fetch news for that symbol. Try again shortly.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

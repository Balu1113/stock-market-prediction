from django.urls import path
from .yahoo_views import (
    YahooAnalyzeView,
    YahooQuoteView,
    YahooStatusView,
    YahooSymbolSearchView,
)
from .views import PredictView
from .kite_views import (
    KiteAnalyzeView,
    KiteCallbackView,
    KiteDisconnectView,
    KiteInstrumentSearchView,
    KiteLoginView,
    KiteQuoteView,
    KiteStatusView,
)

urlpatterns = [
    path('predict', PredictView.as_view(), name='predict'),
    path('kite/login', KiteLoginView.as_view(), name='kite-login'),
    path('kite/callback', KiteCallbackView.as_view(), name='kite-callback'),
    path('kite/status', KiteStatusView.as_view(), name='kite-status'),
    path('kite/disconnect', KiteDisconnectView.as_view(), name='kite-disconnect'),
    path('kite/instruments', KiteInstrumentSearchView.as_view(), name='kite-instruments'),
    path('kite/quote', KiteQuoteView.as_view(), name='kite-quote'),
    path('predict/kite', KiteAnalyzeView.as_view(), name='kite-predict'),
    path('yahoo/status', YahooStatusView.as_view(), name='yahoo-status'),
    path('yahoo/symbols', YahooSymbolSearchView.as_view(), name='yahoo-symbols'),
    path('yahoo/quote', YahooQuoteView.as_view(), name='yahoo-quote'),
    path('predict/yahoo', YahooAnalyzeView.as_view(), name='yahoo-predict'),
]
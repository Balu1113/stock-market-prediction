from django.urls import path
from .alpha_views import (
    AlphaVantageAnalyzeView,
    AlphaVantageQuoteView,
    AlphaVantageStatusView,
    AlphaVantageSymbolSearchView,
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
    path('alpha-vantage/status', AlphaVantageStatusView.as_view(), name='alpha-vantage-status'),
    path('alpha-vantage/symbols', AlphaVantageSymbolSearchView.as_view(), name='alpha-vantage-symbols'),
    path('alpha-vantage/quote', AlphaVantageQuoteView.as_view(), name='alpha-vantage-quote'),
    path('predict/alpha-vantage', AlphaVantageAnalyzeView.as_view(), name='alpha-vantage-predict'),
]
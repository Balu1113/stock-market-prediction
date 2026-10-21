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
from .strategy_views import BacktestView
from .ranking_views import RankView
from .seasonality_views import SeasonalityView
from .screener_views import ScreenerBacktestView, ScreenerScanView, SavedScanView
from .alerts_views import AlertCheckView, AlertEventView, AlertView
from .market_views import MarketBreadthView
from .news_views import YahooNewsView
from .portfolio_views import HoldingView, PortfolioSummaryView
from .auth_views import LoginView, LogoutView, MeView, RegisterView

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
    path('yahoo/news', YahooNewsView.as_view(), name='yahoo-news'),
    path('yahoo/seasonality', SeasonalityView.as_view(), name='yahoo-seasonality'),
    path('predict/yahoo', YahooAnalyzeView.as_view(), name='yahoo-predict'),
    path('rank', RankView.as_view(), name='rank'),
    path('screener/scan', ScreenerScanView.as_view(), name='screener-scan'),
    path('screener/backtest', ScreenerBacktestView.as_view(), name='screener-backtest'),
    path('screener/scans', SavedScanView.as_view(), name='screener-scans'),
    path('backtest', BacktestView.as_view(), name='backtest'),
    path('alerts', AlertView.as_view(), name='alerts'),
    path('alerts/check', AlertCheckView.as_view(), name='alerts-check'),
    path('alerts/events', AlertEventView.as_view(), name='alerts-events'),
    path('market/breadth', MarketBreadthView.as_view(), name='market-breadth'),
    path('portfolio/holdings', HoldingView.as_view(), name='portfolio-holdings'),
    path('portfolio/summary', PortfolioSummaryView.as_view(), name='portfolio-summary'),
    path('auth/register', RegisterView.as_view(), name='auth-register'),
    path('auth/login', LoginView.as_view(), name='auth-login'),
    path('auth/logout', LogoutView.as_view(), name='auth-logout'),
    path('auth/me', MeView.as_view(), name='auth-me'),
]

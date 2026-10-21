"""Nifty 50 universe and sector map used by ranking, screener, and breadth."""

NIFTY50 = [
    'ADANIENT.NS', 'ADANIPORTS.NS', 'APOLLOHOSP.NS', 'ASIANPAINT.NS',
    'AXISBANK.NS', 'BAJAJ-AUTO.NS', 'BAJFINANCE.NS', 'BAJAJFINSV.NS',
    'BEL.NS', 'BHARTIARTL.NS', 'CIPLA.NS', 'COALINDIA.NS',
    'DRREDDY.NS', 'EICHERMOT.NS', 'ETERNAL.NS', 'GRASIM.NS',
    'HCLTECH.NS', 'HDFCBANK.NS', 'HDFCLIFE.NS', 'HEROMOTOCO.NS',
    'HINDALCO.NS', 'HINDUNILVR.NS', 'ICICIBANK.NS', 'INDUSINDBK.NS',
    'INFY.NS', 'ITC.NS', 'JIOFIN.NS', 'JSWSTEEL.NS', 'KOTAKBANK.NS',
    'LT.NS', 'M&M.NS', 'MARUTI.NS', 'NESTLEIND.NS', 'NTPC.NS',
    'ONGC.NS', 'POWERGRID.NS', 'RELIANCE.NS', 'SBILIFE.NS',
    'SBIN.NS', 'SHRIRAMFIN.NS', 'SUNPHARMA.NS', 'TATACONSUM.NS',
    'TATAMOTORS.NS', 'TATASTEEL.NS', 'TCS.NS', 'TECHM.NS',
    'TITAN.NS', 'TRENT.NS', 'ULTRACEMCO.NS', 'WIPRO.NS',
]

NIFTY_ETF = '^NSEI'

SECTOR_MAP = {
    'ADANIENT.NS': 'Diversified', 'ADANIPORTS.NS': 'Infrastructure',
    'APOLLOHOSP.NS': 'Healthcare', 'ASIANPAINT.NS': 'Consumer',
    'AXISBANK.NS': 'Banking', 'BAJAJ-AUTO.NS': 'Automobile',
    'BAJFINANCE.NS': 'Financials', 'BAJAJFINSV.NS': 'Financials',
    'BEL.NS': 'Defence', 'BHARTIARTL.NS': 'Telecom',
    'CIPLA.NS': 'Healthcare', 'COALINDIA.NS': 'Energy',
    'DRREDDY.NS': 'Healthcare', 'EICHERMOT.NS': 'Automobile',
    'ETERNAL.NS': 'Consumer', 'GRASIM.NS': 'Cement',
    'HCLTECH.NS': 'IT', 'HDFCBANK.NS': 'Banking',
    'HDFCLIFE.NS': 'Financials', 'HEROMOTOCO.NS': 'Automobile',
    'HINDALCO.NS': 'Metals', 'HINDUNILVR.NS': 'Consumer',
    'ICICIBANK.NS': 'Banking', 'INDUSINDBK.NS': 'Banking',
    'INFY.NS': 'IT', 'ITC.NS': 'Consumer', 'JIOFIN.NS': 'Financials',
    'JSWSTEEL.NS': 'Metals', 'KOTAKBANK.NS': 'Banking',
    'LT.NS': 'Infrastructure', 'M&M.NS': 'Automobile',
    'MARUTI.NS': 'Automobile', 'NESTLEIND.NS': 'Consumer',
    'NTPC.NS': 'Power', 'ONGC.NS': 'Energy', 'POWERGRID.NS': 'Power',
    'RELIANCE.NS': 'Diversified', 'SBILIFE.NS': 'Financials',
    'SBIN.NS': 'Banking', 'SHRIRAMFIN.NS': 'Financials',
    'SUNPHARMA.NS': 'Healthcare', 'TATACONSUM.NS': 'Consumer',
    'TATAMOTORS.NS': 'Automobile', 'TATASTEEL.NS': 'Metals',
    'TCS.NS': 'IT', 'TECHM.NS': 'IT', 'TITAN.NS': 'Consumer',
    'TRENT.NS': 'Consumer', 'ULTRACEMCO.NS': 'Cement', 'WIPRO.NS': 'IT',
}


def symbol_label(symbol):
    """RELIANCE.NS -> RELIANCE"""
    for suffix in ('.NS', '.BO'):
        if symbol.endswith(suffix):
            return symbol[: -len(suffix)]
    return symbol

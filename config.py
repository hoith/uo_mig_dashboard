"""
Configuration constants for the Portfolio Dashboard.
"""

# Country Risk Premiums (Damodaran estimates - can be updated)
CRP_DATA = {
    'US': 0.0, 'USA': 0.0,
    'GB': 0.6, 'UK': 0.6,
    'DE': 0.0, 'GERMANY': 0.0,
    'FR': 0.5, 'FRANCE': 0.5,
    'JP': 0.8, 'JAPAN': 0.8,
    'CN': 1.0, 'CHINA': 1.0,
    'IN': 2.5, 'INDIA': 2.5,
    'BR': 3.5, 'BRAZIL': 3.5,
    'MX': 2.0, 'MEXICO': 2.0,
    'KR': 0.8, 'SOUTH KOREA': 0.8,
    'AU': 0.0, 'AUSTRALIA': 0.0,
    'CA': 0.0, 'CANADA': 0.0,
    'CH': 0.0, 'SWITZERLAND': 0.0,
    'HK': 0.6, 'HONG KONG': 0.6,
    'SG': 0.0, 'SINGAPORE': 0.0,
}

# Ticker to country mapping (common US stocks default to US)
TICKER_COUNTRY_MAP = {
    'AAPL': 'US', 'MSFT': 'US', 'GOOGL': 'US', 'AMZN': 'US', 'NVDA': 'US',
    'META': 'US', 'TSLA': 'US', 'JPM': 'US', 'V': 'US', 'JNJ': 'US',
    'SPY': 'US', 'QQQ': 'US', 'IWM': 'US', 'DIA': 'US', 'VTI': 'US',
    'EWJ': 'JP', 'FXI': 'CN', 'EWG': 'DE', 'EWU': 'GB', 'EEM': 'EM',
    'BABA': 'CN', 'TSM': 'TW', 'ASML': 'NL', 'NVO': 'DK', 'SAP': 'DE',
    # User's portfolio tickers
    'ADBE': 'US', 'CWEN': 'US', 'IVV': 'US', 'PG': 'US', 'UNH': 'US',
    'CEG': 'US', 'MCD': 'US', 'CASH': 'US', 'LULU': 'US',
}

# Portfolio configurations - add your portfolios here
# Note: initial_cash is now read from the holdings file (INITIAL_CASH row)
PORTFOLIO_CONFIG = {
    'EMF Portfolio': {
        'holdings_file': 'holdings.csv',
        'transactions_file': 'transactions.csv',
    },
    'DADCO Portfolio': {
        'holdings_file': 'Transactions and Holdings Files/HoldingsDADCO.csv',
        'transactions_file': 'Transactions and Holdings Files/TransactionsDADCO.csv',
    },
}

# Trading days per year (for annualization)
TRADING_DAYS = 252

# Default risk-free rate
DEFAULT_RISK_FREE_RATE = 0.05

# Tech sector stocks for stress testing
TECH_STOCKS = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'META', 'AMZN', 'ADBE', 'CRM', 'ORCL', 'INTC']

# Emerging market stocks for stress testing
EM_STOCKS = ['BABA', 'FXI', 'EEM', 'TSM']

# Benchmark options
BENCHMARK_OPTIONS = ['SPY', 'QQQ', 'IWM', 'DIA', 'VTI', 'AGG', 'IEMG']

# IEMG (iShares Core MSCI Emerging Markets ETF) constituent weights (%)
# Source: iShares website — update periodically from:
#   https://www.ishares.com/us/products/244050/IEMG
# Last verified: March 2026
IEMG_WEIGHTS = {
    # Source: stockanalysis.com/etf/iemg/holdings/ — verified March 6, 2026
    'TSM':   11.63,  # Taiwan Semiconductor Mfg (largest holding)
    'BABA':   2.27,  # Alibaba Group (top-5 holding)
    'MELI':   0.21,  # MercadoLibre (est. — not in top 25)
    'RDY':    0.10,  # Dr. Reddy's Laboratories (est.)
    'WIT':    0.07,  # Wipro (est.)
    'TGLS':   0.00,  # Tecnoglass (not in IEMG)
    'IEMG':   0.00,  # The ETF itself — passive allocation, not a constituent weight
    'CASH':   0.00,
}

# SPY (SPDR S&P 500 ETF) constituent weights (%) — fallback hardcoded values.
# Fetched live at runtime via fetch_spy_weights() (uses IVV's iShares CSV endpoint
# since IVV and SPY track the same S&P 500 index).
# Last verified: March 2026 — update via iShares IVV holdings page:
#   https://www.ishares.com/us/products/239726/IVV
SPY_WEIGHTS = {
    # Source: approximate S&P 500 constituent weights — March 2026
    'AAPL':  7.10,   # Apple
    'MSFT':  6.70,   # Microsoft
    'GOOGL': 3.70,   # Alphabet Class A
    'META':  2.90,   # Meta Platforms
    'UNH':   1.20,   # UnitedHealth Group
    'PG':    0.80,   # Procter & Gamble
    'MCD':   0.50,   # McDonald's
    'ADBE':  0.35,   # Adobe
    'CEG':   0.25,   # Constellation Energy
    'CWEN':  0.00,   # Clearway Energy (not in S&P 500)
    'IVV':   0.00,   # iShares Core S&P 500 ETF — passive vehicle, not a constituent
    'CASH':  0.00,
}

# --- Additional runtime constants ---
BETA_TRAILING_DAYS = 90
EXANTE_TRAILING_DAYS = 252
DEFAULT_VAR_CONFIDENCE = 0.95
DEFAULT_MAX_WEIGHT = 0.25
DEFAULT_MIN_WEIGHT = 0.02

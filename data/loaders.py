# data/loaders.py
import os
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from config import PORTFOLIO_CONFIG, TICKER_COUNTRY_MAP


def load_portfolio_transactions(portfolio_name='Portfolio 1'):
    """Load transactions for the specified portfolio."""
    config = PORTFOLIO_CONFIG.get(portfolio_name, PORTFOLIO_CONFIG['EMF Portfolio'])
    default_path = os.path.join(os.path.dirname(__file__), '..', config['transactions_file'])

    if os.path.exists(default_path):
        try:
            df = pd.read_csv(default_path)
            # Standardize column names
            column_mapping = {
                'Date': 'date', 'Ticker': 'symbol', 'Action': 'side',
                'Shares': 'quantity', 'Price': 'price', 'Fees': 'fees', 'Name': 'name'
            }
            df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
            if 'side' in df.columns:
                df['side'] = df['side'].str.upper()
            return df.sort_values('date').reset_index(drop=True)
        except Exception as e:
            st.warning(f"Could not load {config['transactions_file']}: {e}")

    return generate_sample_transactions()


def load_portfolio_holdings(portfolio_name='Portfolio 1'):
    """Load holdings for the specified portfolio.

    Returns:
        tuple: (holdings_df, initial_cash) - Holdings DataFrame and initial cash from file
    """
    config = PORTFOLIO_CONFIG.get(portfolio_name, PORTFOLIO_CONFIG['EMF Portfolio'])

    # Try the configured file and fallback variations
    base_name = config['holdings_file'].replace('.csv', '')
    possible_paths = [
        os.path.join(os.path.dirname(__file__), '..', config['holdings_file']),
        os.path.join(os.path.dirname(__file__), '..', f'{base_name} (1).csv'),
        os.path.join(os.path.dirname(__file__), '..', f'{base_name}-1.csv'),
    ]

    for default_path in possible_paths:
        if os.path.exists(default_path):
            try:
                df = pd.read_csv(default_path)
                # Standardize column names
                column_mapping = {
                    'Ticker': 'symbol', 'ticker': 'symbol',
                    'Shares': 'quantity', 'shares': 'quantity',
                }
                df = df.rename(columns=column_mapping)

                # Extract INITIAL_CASH from holdings if present
                initial_cash = 0.0
                if 'symbol' in df.columns:
                    initial_cash_row = df[df['symbol'] == 'INITIAL_CASH']
                    if not initial_cash_row.empty:
                        initial_cash = float(initial_cash_row['quantity'].iloc[0])
                        df = df[df['symbol'] != 'INITIAL_CASH']  # Remove from holdings

                if 'cost_basis' not in df.columns:
                    df['cost_basis'] = 0.0

                if 'country' not in df.columns:
                    df['country'] = df['symbol'].map(lambda x: TICKER_COUNTRY_MAP.get(x, 'US'))

                return df, initial_cash
            except Exception as e:
                st.warning(f"Could not load holdings file: {e}")

    return generate_sample_holdings(), 0.0


def load_default_transactions():
    """Load transactions from the default CSV file."""
    default_path = os.path.join(os.path.dirname(__file__), '..', 'transactions.csv')

    if os.path.exists(default_path):
        try:
            df = pd.read_csv(default_path)
            # Standardize column names to match expected format
            column_mapping = {
                'Date': 'date',
                'Ticker': 'symbol',
                'Action': 'side',
                'Shares': 'quantity',
                'Price': 'price',
                'Fees': 'fees',
                'Name': 'name'
            }
            df = df.rename(columns=column_mapping)
            df['date'] = pd.to_datetime(df['date'])
            # Standardize side to uppercase
            df['side'] = df['side'].str.upper()
            return df.sort_values('date').reset_index(drop=True)
        except Exception as e:
            st.warning(f"Could not load transactions.csv: {e}")

    return generate_sample_transactions()


def load_default_holdings():
    """Load holdings from the default CSV file.

    Returns:
        tuple: (holdings_df, initial_cash) - Holdings DataFrame and initial cash from file
    """
    # Try different possible filenames
    possible_paths = [
        os.path.join(os.path.dirname(__file__), '..', 'holdings (1).csv'),
        os.path.join(os.path.dirname(__file__), '..', 'holdings-1.csv'),
        os.path.join(os.path.dirname(__file__), '..', 'holdings.csv'),
    ]

    for default_path in possible_paths:
        if os.path.exists(default_path):
            try:
                df = pd.read_csv(default_path)
                # Standardize column names
                column_mapping = {
                    'Ticker': 'symbol',
                    'Shares': 'quantity',
                    'ticker': 'symbol',
                    'shares': 'quantity',
                }
                df = df.rename(columns=column_mapping)

                # Extract INITIAL_CASH from holdings if present
                initial_cash = 0.0
                if 'symbol' in df.columns:
                    initial_cash_row = df[df['symbol'] == 'INITIAL_CASH']
                    if not initial_cash_row.empty:
                        initial_cash = float(initial_cash_row['quantity'].iloc[0])
                        df = df[df['symbol'] != 'INITIAL_CASH']  # Remove from holdings

                # Add cost_basis if not present (will be calculated from transactions or fetched)
                if 'cost_basis' not in df.columns:
                    df['cost_basis'] = 0.0  # Will be updated later

                # Add country if not present
                if 'country' not in df.columns:
                    df['country'] = df['symbol'].map(lambda x: TICKER_COUNTRY_MAP.get(x, 'US'))

                return df, initial_cash
            except Exception as e:
                st.warning(f"Could not load holdings file: {e}")

    return generate_sample_holdings(), 0.0


def generate_sample_transactions():
    """Generate sample transaction data for demonstration."""
    np.random.seed(42)
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'JPM', 'V', 'JNJ']

    transactions = []
    start_date = datetime(2023, 1, 1)

    for symbol in symbols:
        # Initial buy
        buy_date = start_date + timedelta(days=np.random.randint(0, 30))
        qty = np.random.randint(10, 100)
        price = np.random.uniform(50, 500)
        transactions.append({
            'date': buy_date.strftime('%Y-%m-%d'),
            'symbol': symbol,
            'side': 'BUY',
            'quantity': qty,
            'price': round(price, 2),
            'fees': round(qty * price * 0.001, 2)
        })

        # Additional transactions
        for _ in range(np.random.randint(1, 4)):
            tx_date = buy_date + timedelta(days=np.random.randint(30, 365))
            side = np.random.choice(['BUY', 'SELL'], p=[0.6, 0.4])
            tx_qty = np.random.randint(5, 30)
            tx_price = price * (1 + np.random.uniform(-0.2, 0.3))
            transactions.append({
                'date': tx_date.strftime('%Y-%m-%d'),
                'symbol': symbol,
                'side': side,
                'quantity': tx_qty,
                'price': round(tx_price, 2),
                'fees': round(tx_qty * tx_price * 0.001, 2)
            })

    df = pd.DataFrame(transactions)
    df['date'] = pd.to_datetime(df['date'])
    return df.sort_values('date').reset_index(drop=True)


def generate_sample_holdings():
    """Generate sample current holdings snapshot."""
    holdings = [
        {'symbol': 'AAPL', 'quantity': 75, 'cost_basis': 145.50, 'country': 'US'},
        {'symbol': 'MSFT', 'quantity': 50, 'cost_basis': 285.00, 'country': 'US'},
        {'symbol': 'GOOGL', 'quantity': 30, 'cost_basis': 125.00, 'country': 'US'},
        {'symbol': 'NVDA', 'quantity': 40, 'cost_basis': 420.00, 'country': 'US'},
        {'symbol': 'JPM', 'quantity': 60, 'cost_basis': 145.00, 'country': 'US'},
        {'symbol': 'V', 'quantity': 45, 'cost_basis': 235.00, 'country': 'US'},
        {'symbol': 'JNJ', 'quantity': 55, 'cost_basis': 158.00, 'country': 'US'},
    ]
    return pd.DataFrame(holdings)

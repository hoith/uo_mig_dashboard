# calculations/cost_basis.py
import pandas as pd
import numpy as np


def calculate_cost_basis_from_transactions(transactions_df, holdings_df):
    """Calculate cost basis for each holding from transaction history."""
    if transactions_df is None or transactions_df.empty:
        return holdings_df

    holdings_df = holdings_df.copy()

    for idx, row in holdings_df.iterrows():
        symbol = row['symbol']
        # Get all transactions for this symbol
        symbol_txns = transactions_df[transactions_df['symbol'] == symbol].copy()

        if symbol_txns.empty:
            continue

        # Calculate weighted average cost from BUY transactions
        buy_txns = symbol_txns[symbol_txns['side'] == 'BUY']

        if not buy_txns.empty:
            total_cost = (buy_txns['quantity'] * buy_txns['price']).sum()
            total_shares = buy_txns['quantity'].sum()
            avg_cost = total_cost / total_shares if total_shares > 0 else 0
            holdings_df.at[idx, 'cost_basis'] = round(avg_cost, 2)
        else:
            # If no BUY transactions, use SELL price as estimate (position was held before)
            sell_txns = symbol_txns[symbol_txns['side'] == 'SELL']
            if not sell_txns.empty:
                # Use earliest sell price as cost basis estimate
                earliest_sell = sell_txns.sort_values('date').iloc[0]
                holdings_df.at[idx, 'cost_basis'] = round(earliest_sell['price'], 2)

    return holdings_df


def estimate_cost_basis_from_prices(holdings_df, prices_df):
    """Estimate cost basis using the price at the beginning of the date range
    for positions without transaction history."""
    holdings_df = holdings_df.copy()

    for idx, row in holdings_df.iterrows():
        if row['cost_basis'] == 0 or pd.isna(row['cost_basis']):
            symbol = row['symbol']
            if symbol in prices_df.columns:
                historical_prices = prices_df[symbol].dropna()
                if len(historical_prices) > 0:
                    # Use the first price in the range as cost basis
                    holdings_df.at[idx, 'cost_basis'] = round(historical_prices.iloc[0], 2)

    return holdings_df
